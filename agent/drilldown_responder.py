"""
agent/drilldown_responder.py — long-poll responder for cloud-initiated raw fetches.

Lifecycle
---------
1. User clicks "View Details" in the cloud UI.
2. Cloud creates a DrilldownRequest with a one-time token, opens an SSE stream
   to the user's browser.
3. This responder periodically GETs /api/agent-ingest/pending-requests over the
   signed channel.  If anything is pending, it dispatches the request_type
   handler (e.g. fetch_risk_by_id) against the LOCAL DB.
4. The result is POSTed back to /api/agent-ingest/drilldown-response/{token}.
5. Cloud forwards the result over the SSE stream and immediately wipes its
   temp storage — the raw payload is never persisted in the cloud DB.

Decisions
---------
- Polling chosen over WebSocket for simplicity: no inbound port required on
  the customer network, no long-lived TCP state to debug, plays nicely with
  reverse proxies / NAT / corporate firewalls.  At a 2-second poll interval
  the worst-case user-facing latency is ~2.5 s, well within "feels live".
  WebSocket can be added later as an upgrade if customers need sub-second.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Optional

import httpx

from agent.reporter import EncryptedReporter, sign_payload

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL_SECONDS = 2.0


# A handler is an async callable that accepts (request_type, request_payload)
# and returns the raw response dict.  The agent registers handlers for each
# supported request_type (e.g. "fetch_risk_by_id", "fetch_evidence_file").
RawHandler = Callable[[str, dict], Awaitable[dict]]


class DrilldownResponder:
    """Polls /pending-requests, dispatches, posts response."""

    def __init__(
        self,
        reporter: EncryptedReporter,
        handlers: dict[str, RawHandler],
        *,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self._reporter = reporter
        self._handlers = handlers
        self._poll_interval = poll_interval_seconds
        self._http = http_client

    # ─────────────────────────────────────────────────────────────────────
    # GET /pending-requests  (signed)
    # ─────────────────────────────────────────────────────────────────────

    def _signed_get(self, path: str) -> httpx.Response:
        import time

        url = f"{self._reporter.cloud_portal_url}{path}"
        body = b""  # GET — empty body
        timestamp = str(int(time.time()))
        signature = sign_payload(self._reporter.shared_secret, timestamp, path, body)
        headers = {
            "X-Agent-Tenant": self._reporter.tenant_slug,
            "X-Agent-Version": self._reporter.agent_version,
            "X-Timestamp": timestamp,
            "X-Signature": signature,
        }
        client = self._http or httpx.Client(timeout=self._reporter.timeout_seconds)
        close_after = self._http is None
        try:
            return client.get(url, headers=headers)
        finally:
            if close_after:
                client.close()

    async def fetch_pending(self) -> list[dict]:
        """Return the list of pending DrilldownRequests for this tenant."""
        # Run sync httpx call in a thread to avoid blocking the event loop.
        response = await asyncio.to_thread(
            self._signed_get, "/api/agent-ingest/pending-requests"
        )
        if response.status_code != 200:
            logger.warning("pending-requests returned %d: %s", response.status_code, response.text)
            return []
        return response.json().get("pending", [])

    async def fulfil(self, pending: dict) -> bool:
        """Run the handler for one pending request and POST the response."""
        token = pending["token"]
        request_type = pending["request_type"]
        request_payload = pending.get("request_payload", {})

        handler = self._handlers.get(request_type)
        if handler is None:
            logger.warning("No handler for request_type=%s — skipping", request_type)
            error_payload = {"error": f"unsupported request_type: {request_type}"}
            self._reporter.report_to_cloud(
                f"drilldown-response/{token}", error_payload
            )
            return False

        try:
            raw = await handler(request_type, request_payload)
        except Exception as exc:
            logger.exception("Handler %s failed: %s", request_type, exc)
            raw = {"error": f"handler failed: {exc!r}"}

        # Post back over the signed channel.  This is the ONLY case where the
        # payload may contain raw findings — legitimate, on-demand drill-down
        # requested by an authenticated user via the SSE stream.  The cloud
        # holds the response only briefly and wipes it after forwarding.
        # Therefore we send via a low-level signed POST (not via the
        # leak-checker that report_to_cloud uses for metadata).
        await asyncio.to_thread(
            self._raw_signed_post,
            f"/api/agent-ingest/drilldown-response/{token}",
            raw,
        )
        return True

    def _raw_signed_post(self, path: str, payload: dict) -> httpx.Response:
        """Signed POST that bypasses the metadata leak-check (drill-down only)."""
        import time

        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        timestamp = str(int(time.time()))
        signature = sign_payload(self._reporter.shared_secret, timestamp, path, body)
        url = f"{self._reporter.cloud_portal_url}{path}"
        headers = {
            "Content-Type": "application/json",
            "X-Agent-Tenant": self._reporter.tenant_slug,
            "X-Agent-Version": self._reporter.agent_version,
            "X-Timestamp": timestamp,
            "X-Signature": signature,
        }
        client = self._http or httpx.Client(timeout=self._reporter.timeout_seconds)
        close_after = self._http is None
        try:
            return client.post(url, headers=headers, content=body)
        finally:
            if close_after:
                client.close()

    # ─────────────────────────────────────────────────────────────────────
    # Long-running loop
    # ─────────────────────────────────────────────────────────────────────

    async def run_forever(self) -> None:
        logger.info(
            "DrilldownResponder starting (poll_interval=%.1fs, handlers=%s)",
            self._poll_interval,
            list(self._handlers.keys()),
        )
        while True:
            try:
                pending = await self.fetch_pending()
                for p in pending:
                    await self.fulfil(p)
            except Exception as exc:
                logger.exception("Drilldown loop hiccup: %s", exc)
            await asyncio.sleep(self._poll_interval)
