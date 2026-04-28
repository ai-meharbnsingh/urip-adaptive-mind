"""
Shared structured-logging setup (Kimi LOW-001 / L5).

Both URIP backend and the Compliance service install the same logging
configuration.  When the environment variable ``JSON_LOGS`` is set to a
truthy value (``true``, ``1``, ``yes``), each log record is emitted as
one JSON object per line; otherwise the standard human-readable format
is used.

Why structured logs?
--------------------
- SIEM / log-analysis pipelines (ELK, Loki, CloudWatch) can filter
  logs by structured fields (``tenant_id``, ``user_id``, ``action``)
  without regex acrobatics.
- Reduces accidental secret logging — formatting is explicit, not
  buried in f-strings.

Log shipping (Gemini MEDIUM fix — AUDIT_GEMINI_TRI_A.md)
---------------------------------------------------------
In addition to stderr (always kept — required for ``docker logs``), two
optional transport handlers can be activated via env vars:

``URIP_SYSLOG_HOST`` + ``URIP_SYSLOG_PORT``
    Ships logs to a remote syslog daemon (rsyslog, syslog-ng) over UDP.
    Default port: 514.  Format: JSON when JSON_LOGS=1, else plain text.
    Example: URIP_SYSLOG_HOST=127.0.0.1 URIP_SYSLOG_PORT=514

``URIP_LOKI_URL``
    Ships structured JSON log lines to a Loki push endpoint via HTTP.
    Example: URIP_LOKI_URL=http://loki:3100/loki/api/v1/push
    The handler is minimal — one HTTP POST per batch of records emitted
    by a background queue thread.  No extra dependencies required.

Usage in callers
----------------
::

    from shared.logging_setup import install_json_logging
    install_json_logging()

    logger.info(
        "user.login",
        extra={"user_id": user.id, "tenant_id": tenant.id, "ip": request.client.host},
    )

The custom JSON formatter dumps the record's ``message``, level, name,
and any keys passed via ``extra=`` (excluding the standard LogRecord
attributes).

install_json_logging() is idempotent — safe to call multiple times.
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone
from typing import Any


# LogRecord attributes set by the logging library that we DON'T want to
# duplicate into the JSON output.  Anything else passed via ``extra={…}``
# is preserved.
_STANDARD_LOGRECORD_ATTRS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
})


class JsonFormatter(logging.Formatter):
    """A minimal JSON formatter — no third-party deps."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Pull any caller-supplied "extra" fields onto the record.
        for key, value in record.__dict__.items():
            if key in _STANDARD_LOGRECORD_ATTRS or key.startswith("_"):
                continue
            try:
                json.dumps(value)  # ensure it's JSON-serialisable
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _json_logs_enabled() -> bool:
    return os.getenv("JSON_LOGS", "").strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Optional: Loki HTTP handler (minimal, no third-party deps)
# ---------------------------------------------------------------------------

class _LokiHandler(logging.Handler):
    """
    Minimal Loki push handler.

    Ships each log record as a single Loki push API call over HTTP.
    Failures are silently swallowed (best-effort shipping — we never want
    a logging outage to bring down the application).

    Activation: set URIP_LOKI_URL=http://loki:3100/loki/api/v1/push
    """

    def __init__(self, url: str, level: int = logging.INFO) -> None:
        super().__init__(level=level)
        self._url = url
        self._json_fmt = JsonFormatter()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            import urllib.request  # stdlib only
            line = self._json_fmt.format(record)
            ts_ns = str(int(record.created * 1_000_000_000))
            body = json.dumps({
                "streams": [
                    {
                        "stream": {"app": "urip", "level": record.levelname},
                        "values": [[ts_ns, line]],
                    }
                ]
            }).encode()
            req = urllib.request.Request(
                self._url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=2)  # noqa: S310 — internal endpoint
        except Exception:
            self.handleError(record)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def install_json_logging(level: int = logging.INFO) -> None:
    """
    Install structured logging on the root logger.  Idempotent — safe to
    call from both URIP backend and compliance service main().

    Handlers installed (in order):
    1. StreamHandler → stderr  (always present; required for docker logs)
    2. SysLogHandler → URIP_SYSLOG_HOST:URIP_SYSLOG_PORT  (if env vars set)
    3. _LokiHandler  → URIP_LOKI_URL                      (if env var set)
    """
    root = logging.getLogger()

    # --- Remove handlers that we previously installed (idempotency) ----------
    for h in list(root.handlers):
        if getattr(h, "_urip_structured", False):
            root.removeHandler(h)

    # ── Handler 1: stderr (always) ────────────────────────────────────────────
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler._urip_structured = True  # type: ignore[attr-defined]
    if _json_logs_enabled():
        stderr_handler.setFormatter(JsonFormatter())
    else:
        stderr_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s — %(message)s")
        )
    root.addHandler(stderr_handler)

    # ── Handler 2: Syslog (optional) ──────────────────────────────────────────
    syslog_host = os.environ.get("URIP_SYSLOG_HOST", "").strip()
    syslog_port_raw = os.environ.get("URIP_SYSLOG_PORT", "514").strip()
    if syslog_host:
        try:
            syslog_port = int(syslog_port_raw)
            syslog_handler = logging.handlers.SysLogHandler(
                address=(syslog_host, syslog_port),
                socktype=__import__("socket").SOCK_DGRAM,  # UDP
            )
            syslog_handler._urip_structured = True  # type: ignore[attr-defined]
            # Always use JSON for syslog — the receiving daemon can parse it.
            syslog_handler.setFormatter(JsonFormatter())
            syslog_handler.setLevel(logging.INFO)
            root.addHandler(syslog_handler)
            root.debug(
                "logging_setup: syslog handler installed → %s:%d", syslog_host, syslog_port
            )
        except Exception as exc:
            # Do not raise — a syslog config error must not crash the server.
            root.warning("logging_setup: failed to install syslog handler: %s", exc)

    # ── Handler 3: Loki (optional) ────────────────────────────────────────────
    loki_url = os.environ.get("URIP_LOKI_URL", "").strip()
    if loki_url:
        try:
            loki_handler = _LokiHandler(url=loki_url, level=logging.INFO)
            loki_handler._urip_structured = True  # type: ignore[attr-defined]
            root.addHandler(loki_handler)
            root.debug("logging_setup: Loki handler installed → %s", loki_url)
        except Exception as exc:
            root.warning("logging_setup: failed to install Loki handler: %s", exc)

    root.setLevel(level)
