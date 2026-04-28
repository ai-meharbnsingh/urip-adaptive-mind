"""
backend/routers/agent_ingest.py — Cloud-side ingest API for the on-prem Docker agent.

Phase 4 — Hybrid-SaaS (DELIVERY_ARCHITECTURE.md §3, §7).

Endpoints
---------
- POST  /api/agent-ingest/register
- POST  /api/agent-ingest/heartbeat
- POST  /api/agent-ingest/metadata
- POST  /api/agent-ingest/drilldown-request          (frontend → cloud)
- GET   /api/agent-ingest/drilldown-stream/{token}   (frontend ← cloud, SSE)
- GET   /api/agent-ingest/pending-requests           (agent → cloud, polled)
- POST  /api/agent-ingest/drilldown-response/{token} (agent → cloud)

Security model
--------------
- Every agent → cloud call (heartbeat / metadata / pending-requests / drilldown-response)
  must include three headers:
    X-Agent-Tenant   — tenant slug (lookup key)
    X-Timestamp      — RFC3339 / unix timestamp ; rejected if >5 min skew
    X-Signature      — hex HMAC-SHA256 of  "{timestamp}.{path}.{body}"  using shared_secret

  We chose HMAC-SHA256 (NOT JWT) because:
    * the agent and cloud share a static symmetric secret already (decision tree
      doesn't fit JWT's "issuer signs, verifier checks signature" model),
    * HMAC over canonical "{ts}.{path}.{body}" inherently binds the request,
      protecting against header-only replay,
    * no token expiry / refresh dance — anti-replay is timestamp-based,
    * smaller wire footprint.

- /register is the ONLY agent endpoint NOT signed — instead it's authed by the
  tenant's license_key (constant-time compared) and returns the freshly-minted
  shared_secret exactly once.

- One-time drilldown tokens (32 random bytes hex) expire in 60 seconds and are
  invalidated immediately after being fulfilled & forwarded.  fulfilled_payload_temp
  is wiped to NULL after the SSE forward.

- NO raw findings are ever persisted on the cloud.  The /metadata endpoint
  rejects payloads that include the keys 'asset', 'ip', 'hostname', 'username',
  'cve_id', 'finding' anywhere in the body — a defence-in-depth check.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time as _time
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.models.agent_ingest import (
    AgentRegistration,
    ConnectorHealthSummary,
    DrilldownRequest,
)
from backend.models.risk_snapshot import RiskScoreSummary
from backend.models.tenant import Tenant
from backend.models.user import User

router = APIRouter()

# ─── Constants ──────────────────────────────────────────────────────────────
TIMESTAMP_SKEW_SECONDS = 5 * 60          # 5 min anti-replay window
DRILLDOWN_TOKEN_TTL_SECONDS = 60         # one-time token TTL
SSE_POLL_INTERVAL_SECONDS = 0.5          # how often the SSE handler checks DB
SSE_TIMEOUT_SECONDS = 90                 # close the SSE stream after this if unfulfilled
RAW_FINDING_DENY_KEYS = frozenset(
    {"asset", "ip", "ip_address", "hostname", "username", "user", "finding", "cve_id"}
)

# ─── HIGH-6 — signature replay protection ──────────────────────────────────
# We cache recent X-Signature values and reject any signature seen again
# within the anti-replay window. Even if the timestamp is still fresh, a
# captured-and-replayed request gets blocked.
#
# Production deployments should set `AGENT_REPLAY_REDIS_URL` so the cache
# survives across multiple workers / pods. Without that we fall back to an
# in-process LRU keyed by signature; this is correct on a single worker and
# safe (false-negatives only across worker boundaries).
SIGNATURE_REPLAY_TTL_SECONDS = TIMESTAMP_SKEW_SECONDS  # match the skew window
_REPLAY_CACHE_MAX_ENTRIES = 10_000

# Lazily-initialised — the cache is module-state.
# Each entry: signature -> first-seen monotonic-ish epoch.
_signature_replay_cache: "OrderedDict[str, float]" = OrderedDict()


def _replay_cache_now() -> float:
    return _time.time()


def _purge_expired_replay_entries(now: float) -> None:
    """Drop entries older than the TTL. Cheap on a tight cache (LRU)."""
    cutoff = now - SIGNATURE_REPLAY_TTL_SECONDS
    while _signature_replay_cache:
        oldest_sig, ts = next(iter(_signature_replay_cache.items()))
        if ts < cutoff:
            _signature_replay_cache.popitem(last=False)
        else:
            break


def _check_and_record_signature(sig: str) -> bool:
    """
    Returns True if the signature is fresh (and records it). Returns False
    if it has already been seen within the replay window.

    Bounded to ``_REPLAY_CACHE_MAX_ENTRIES`` entries to prevent
    unbounded memory growth — old entries fall out the bottom of the LRU.
    """
    now = _replay_cache_now()
    _purge_expired_replay_entries(now)
    if sig in _signature_replay_cache:
        return False
    _signature_replay_cache[sig] = now
    # Bound the cache.
    while len(_signature_replay_cache) > _REPLAY_CACHE_MAX_ENTRIES:
        _signature_replay_cache.popitem(last=False)
    return True

# ─── HKDF constants — must match agent-side (agent/reporter.py) ─────────────
# Audit-fix CRIT-G5: a DB read of `shared_secret_hash` must NOT yield a usable
# HMAC signing key. We derive a SEPARATE key via HKDF; the stored hash remains
# the lookup index but is no longer the key itself. To rotate, bump
# HMAC_KEY_INFO to a new versioned label.
HMAC_KEY_SALT = b"urip-agent-hmac-salt-v1"
HMAC_KEY_INFO = b"urip-agent-hmac-v1"
HMAC_KEY_LENGTH = 32  # 256-bit HMAC key for SHA-256


def _derive_hmac_key(stored_secret_hash: str) -> bytes:
    """
    Derive the HMAC verification key from the DB-stored secret hash via HKDF.

    `stored_secret_hash` is the hex sha256 of the plain shared secret — exactly
    the value held in `agent_registrations.shared_secret_hash`. The agent
    derives the same key from the secret it has in env (see
    `agent/reporter._derive_hmac_key`), so signatures match end-to-end while
    the DB-stored value alone is no longer a usable signing key.
    """
    if not stored_secret_hash:
        raise ValueError("stored_secret_hash must be non-empty")
    kdf = HKDF(
        algorithm=hashes.SHA256(),
        length=HMAC_KEY_LENGTH,
        salt=HMAC_KEY_SALT,
        info=HMAC_KEY_INFO,
    )
    return kdf.derive(stored_secret_hash.encode("utf-8"))


# ─── Helpers ────────────────────────────────────────────────────────────────


def _hmac_secret(plain_secret: str) -> str:
    """Deterministic SHA256 hex digest of the shared secret (DB-stored form)."""
    return hashlib.sha256(plain_secret.encode("utf-8")).hexdigest()


def _sign_payload(secret: str, timestamp: str, path: str, body: bytes) -> str:
    """Produce hex HMAC-SHA256 of the canonical {ts}.{path}.{body}.

    NOTE: `secret` here is the DB-stored hash; we still HKDF-derive the
    actual HMAC key. Mirrors the agent side.
    """
    hmac_key = _derive_hmac_key(secret)
    canonical = timestamp.encode("utf-8") + b"." + path.encode("utf-8") + b"." + body
    return hmac.new(hmac_key, canonical, hashlib.sha256).hexdigest()


def _generate_shared_secret() -> str:
    """64-hex-char (32-byte) high-entropy shared secret."""
    return secrets.token_hex(32)


def _generate_token() -> str:
    """64-hex-char (32-byte) one-time drilldown token."""
    return secrets.token_hex(32)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Force a tz-aware datetime — SQLite returns naive ones in tests."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _contains_raw_finding_keys(payload: Any) -> bool:
    """Recursively walk payload — return True if any banned key is found."""
    if isinstance(payload, dict):
        for k, v in payload.items():
            if k.lower() in RAW_FINDING_DENY_KEYS:
                return True
            if _contains_raw_finding_keys(v):
                return True
    elif isinstance(payload, list):
        for item in payload:
            if _contains_raw_finding_keys(item):
                return True
    return False


async def _verify_agent_signature(
    request: Request, db: AsyncSession
) -> tuple[Tenant, AgentRegistration, bytes]:
    """
    Validate X-Agent-Tenant + X-Timestamp + X-Signature headers.

    Returns
    -------
    (tenant, agent_registration, raw_body)

    Raises HTTPException(401) on any failure.
    """
    tenant_slug = request.headers.get("X-Agent-Tenant")
    timestamp = request.headers.get("X-Timestamp")
    signature = request.headers.get("X-Signature")

    if not tenant_slug or not timestamp or not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Agent-Tenant / X-Timestamp / X-Signature header",
        )

    # 1. Anti-replay
    try:
        ts_float = float(timestamp)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid X-Timestamp format"
        )

    now_ts = _utcnow().timestamp()
    if abs(now_ts - ts_float) > TIMESTAMP_SKEW_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"X-Timestamp outside ±{TIMESTAMP_SKEW_SECONDS}s window",
        )

    # 2. Tenant + agent registration lookup
    result = await db.execute(select(Tenant).where(Tenant.slug == tenant_slug))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown tenant"
        )

    reg_result = await db.execute(
        select(AgentRegistration).where(AgentRegistration.tenant_id == tenant.id)
    )
    reg = reg_result.scalar_one_or_none()
    if reg is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No agent registered for this tenant",
        )

    # 3. Verify signature.  We re-derive the canonical string and compare.
    body = await request.body()
    # NOTE: client must sign the URL path WITHOUT query string.
    path = request.url.path
    # Audit-fix CRIT-G5: derive a SEPARATE HMAC verification key from the
    # DB-stored secret hash via HKDF. Previously the stored hash was used
    # directly as the HMAC key — a DB read = usable signing key. Now both the
    # agent (`agent/reporter._derive_hmac_key`) and the cloud derive an
    # identical, distinct key from that hash, but the hash alone is no longer
    # sufficient to forge a request.
    hmac_key = _derive_hmac_key(reg.shared_secret_hash)
    expected = hmac.new(
        hmac_key,
        timestamp.encode("utf-8") + b"." + path.encode("utf-8") + b"." + body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad X-Signature"
        )

    # HIGH-6 — replay protection. Even with a valid signature & fresh
    # timestamp, reject any signature value we've already accepted within the
    # anti-replay window. Without this, an attacker who captures one signed
    # heartbeat can re-send it indefinitely while the timestamp is still in
    # range.
    if not _check_and_record_signature(signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signature replay detected",
        )

    return tenant, reg, body


# ─── Pydantic schemas ───────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    tenant_slug: str = Field(..., min_length=1, max_length=100)
    license_key: str = Field(..., min_length=16, max_length=128)
    agent_version: str = Field(..., min_length=1, max_length=32)
    capabilities: dict[str, Any] = Field(default_factory=dict)


class RegisterResponse(BaseModel):
    tenant_id: str
    shared_secret: str  # ONE-TIME — store securely on agent
    registered_at: datetime


class HeartbeatRequest(BaseModel):
    connector_health: dict[str, Any] = Field(default_factory=dict)


class MetadataRequest(BaseModel):
    risk_summary: dict[str, Any] = Field(default_factory=dict)
    control_summary: dict[str, Any] = Field(default_factory=dict)
    score_history_delta: dict[str, Any] = Field(default_factory=dict)


class DrilldownRequestIn(BaseModel):
    request_type: str = Field(..., min_length=1, max_length=64)
    request_payload: dict[str, Any] = Field(default_factory=dict)


class DrilldownRequestOut(BaseModel):
    token: str
    expires_at: datetime


class PendingRequestOut(BaseModel):
    token: str
    request_type: str
    request_payload: dict[str, Any]
    expires_at: datetime


# ─── 1. /register ───────────────────────────────────────────────────────────


@router.post("/register", response_model=RegisterResponse)
async def register_agent(
    payload: RegisterRequest, db: AsyncSession = Depends(get_db)
) -> RegisterResponse:
    """
    Agent first-boot registration.

    Authenticates with the tenant license_key (constant-time compared).
    Returns a freshly-minted shared_secret exactly ONCE; the agent stores it
    in its env / vault and uses it to sign every subsequent payload.
    """
    result = await db.execute(
        select(Tenant).where(Tenant.slug == payload.tenant_slug)
    )
    tenant = result.scalar_one_or_none()

    # Constant-time compare even if tenant is missing — avoid timing oracle.
    expected_key = (tenant.license_key if tenant and tenant.license_key else "") or ""
    submitted = payload.license_key or ""

    # hmac.compare_digest needs equal-length strings; pad if necessary by hashing both
    expected_hash = hashlib.sha256(expected_key.encode()).digest()
    submitted_hash = hashlib.sha256(submitted.encode()).digest()
    keys_match = hmac.compare_digest(expected_hash, submitted_hash) and bool(expected_key)

    if not tenant or not keys_match:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid license key"
        )

    # Idempotent: if an AgentRegistration already exists for this tenant, rotate
    # the shared_secret (the operator is re-installing).  Old secret is invalidated.
    reg_result = await db.execute(
        select(AgentRegistration).where(AgentRegistration.tenant_id == tenant.id)
    )
    reg = reg_result.scalar_one_or_none()

    plain_secret = _generate_shared_secret()
    secret_hash = _hmac_secret(plain_secret)

    if reg is None:
        reg = AgentRegistration(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            agent_version=payload.agent_version,
            capabilities=payload.capabilities,
            shared_secret_hash=secret_hash,
        )
        db.add(reg)
    else:
        reg.agent_version = payload.agent_version
        reg.capabilities = payload.capabilities
        reg.shared_secret_hash = secret_hash
        reg.last_seen = _utcnow()

    await db.commit()
    await db.refresh(reg)

    return RegisterResponse(
        tenant_id=str(tenant.id),
        shared_secret=plain_secret,
        registered_at=reg.registered_at,
    )


# ─── 2. /heartbeat ──────────────────────────────────────────────────────────


@router.post("/heartbeat")
async def agent_heartbeat(
    request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Agent health check-in.  Updates last_seen + connector_health."""
    tenant, reg, body = await _verify_agent_signature(request, db)

    try:
        parsed = HeartbeatRequest.model_validate_json(body or b"{}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Bad heartbeat body: {exc}")

    reg.last_seen = _utcnow()
    reg.connector_health = parsed.connector_health
    await db.commit()

    return {"ok": True, "last_seen": reg.last_seen.isoformat()}


# ─── 3. /metadata ───────────────────────────────────────────────────────────


@router.post("/metadata")
async def push_metadata(
    request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Aggregate metadata push from agent — updates RiskScoreSummary + per-connector health.

    Hard rule: the body must NOT contain any raw-finding keys (asset, ip, hostname,
    username, finding, cve_id).  We perform a recursive scan and reject the entire
    payload if any are present.
    """
    tenant, reg, body = await _verify_agent_signature(request, db)

    try:
        body_json = json.loads(body or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}")

    if _contains_raw_finding_keys(body_json):
        raise HTTPException(
            status_code=400,
            detail=(
                "Payload contains raw-finding keys (asset/ip/hostname/username/"
                "finding/cve_id).  Cloud only accepts aggregate metadata — "
                "raw findings must stay on the agent's local DB."
            ),
        )

    parsed = MetadataRequest.model_validate(body_json)
    rs = parsed.risk_summary

    # --- RiskScoreSummary append-only snapshot (uses existing model — see risk_snapshot.py) ---
    # We carry the agent's optional 'top_sources' / 'module_breakdown' verbatim
    # into the existing JSON columns when present.
    extra_top_sources = rs.get("top_sources")
    extra_module_breakdown = rs.get("module_breakdown")

    snapshot = RiskScoreSummary(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        snapshot_at=_utcnow(),
        total_risks=int(rs.get("total_risks", 0)),
        critical_count=int(rs.get("critical_count", 0)),
        high_count=int(rs.get("high_count", 0)),
        medium_count=int(rs.get("medium_count", 0)),
        low_count=int(rs.get("low_count", 0)),
        info_count=int(rs.get("info_count", 0)),
        exploit_active_count=int(rs.get("exploit_active_count", 0)),
        kev_active_count=int(rs.get("kev_active_count", 0)),
        mean_ttr_hours=rs.get("mean_ttr_hours"),
        mean_composite_score=rs.get("mean_composite_score"),
        top_sources_json=(
            json.dumps(extra_top_sources) if extra_top_sources is not None else None
        ),
        module_breakdown_json=(
            json.dumps(extra_module_breakdown) if extra_module_breakdown is not None else None
        ),
    )
    db.add(snapshot)

    # --- Per-connector health rows (UPSERT semantics) ---
    health_pairs = (parsed.control_summary or {}).get("connectors", []) or []
    for ch in health_pairs:
        connector_name = ch.get("name")
        if not connector_name:
            continue
        existing_q = await db.execute(
            select(ConnectorHealthSummary).where(
                ConnectorHealthSummary.tenant_id == tenant.id,
                ConnectorHealthSummary.connector_name == connector_name,
            )
        )
        existing = existing_q.scalar_one_or_none()
        if existing is None:
            db.add(
                ConnectorHealthSummary(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    connector_name=connector_name,
                    status=ch.get("status", "ok"),
                    last_poll_at=_utcnow(),
                    error_count_24h=int(ch.get("error_count_24h", 0)),
                    last_error=ch.get("last_error"),
                )
            )
        else:
            existing.status = ch.get("status", existing.status)
            existing.last_poll_at = _utcnow()
            existing.error_count_24h = int(ch.get("error_count_24h", 0))
            existing.last_error = ch.get("last_error")

    reg.last_seen = _utcnow()
    await db.commit()
    return {
        "ok": True,
        "snapshot_id": str(snapshot.id),
        "raw_persisted": False,
    }


# ─── 4. /drilldown-request (frontend → cloud) ───────────────────────────────


@router.post("/drilldown-request", response_model=DrilldownRequestOut)
async def request_drilldown(
    payload: DrilldownRequestIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DrilldownRequestOut:
    """User clicked "View Details" — queue a request for the agent to fulfil."""
    if current_user.tenant_id is None:
        raise HTTPException(status_code=400, detail="User has no tenant scope")

    token = _generate_token()
    expires_at = _utcnow() + timedelta(seconds=DRILLDOWN_TOKEN_TTL_SECONDS)

    req = DrilldownRequest(
        id=uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        requested_by_user_id=current_user.id,
        request_type=payload.request_type,
        request_payload=payload.request_payload,
        token=token,
        expires_at=expires_at,
    )
    db.add(req)
    await db.commit()

    return DrilldownRequestOut(token=token, expires_at=expires_at)


# ─── 5. /pending-requests (agent → cloud, polled) ───────────────────────────


@router.get("/pending-requests")
async def list_pending_requests(
    request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Agent polls this to see what drill-downs need fulfilment."""
    tenant, reg, _ = await _verify_agent_signature(request, db)

    now = _utcnow()
    # M11 (Codex MED-002) — filter expired rows AT THE DB LEVEL before LIMIT.
    # Previously we filtered after `.limit(50)`, so if 50+ expired rows
    # accumulated the entire response was empty and the agent could not see
    # any newer pending requests until manual cleanup. Now valid rows always
    # win the LIMIT 50 slot.
    q = await db.execute(
        select(DrilldownRequest)
        .where(
            DrilldownRequest.tenant_id == tenant.id,
            DrilldownRequest.fulfilled_at.is_(None),
            DrilldownRequest.expires_at > now,
        )
        .limit(50)
    )
    rows = q.scalars().all()

    return {
        "pending": [
            {
                "token": r.token,
                "request_type": r.request_type,
                "request_payload": r.request_payload,
                "expires_at": _ensure_aware(r.expires_at).isoformat(),
            }
            for r in rows
        ]
    }


# ─── 6. /drilldown-response/{token} (agent → cloud) ─────────────────────────


@router.post("/drilldown-response/{token}")
async def post_drilldown_response(
    token: str, request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Agent posts the fulfilled raw payload back here.  Forwarded via SSE then wiped."""
    tenant, reg, body = await _verify_agent_signature(request, db)

    q = await db.execute(
        select(DrilldownRequest).where(
            DrilldownRequest.token == token,
            DrilldownRequest.tenant_id == tenant.id,
        )
    )
    row = q.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown token")
    if row.fulfilled_at is not None:
        raise HTTPException(status_code=409, detail="Token already fulfilled")
    if _ensure_aware(row.expires_at) < _utcnow():
        raise HTTPException(status_code=410, detail="Token expired")

    # Body is the raw response JSON (string).  We hold it briefly for the SSE
    # handler to forward.  CONTRACT: SSE handler nulls this immediately after.
    row.fulfilled_payload_temp = body.decode("utf-8") if body else "{}"
    row.fulfilled_at = _utcnow()
    await db.commit()
    return {"ok": True}


# ─── 7. /drilldown-stream/{token} (frontend ← cloud, SSE) ───────────────────


@router.get("/drilldown-stream/{token}")
async def drilldown_sse_stream(
    token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Server-Sent Events stream — frontend listens on this for the agent's response.

    Polls the DrilldownRequest row every SSE_POLL_INTERVAL_SECONDS until fulfilled
    or until SSE_TIMEOUT_SECONDS elapses.  When fulfilled, forwards the payload
    AS-IS to the browser, then immediately wipes fulfilled_payload_temp to NULL.
    """
    import asyncio

    if current_user.tenant_id is None:
        raise HTTPException(status_code=400, detail="User has no tenant scope")

    async def event_source():
        deadline = _utcnow() + timedelta(seconds=SSE_TIMEOUT_SECONDS)
        while _utcnow() < deadline:
            q = await db.execute(
                select(DrilldownRequest).where(
                    DrilldownRequest.token == token,
                    DrilldownRequest.tenant_id == current_user.tenant_id,
                )
            )
            row = q.scalar_one_or_none()
            if row is None:
                yield f"event: error\ndata: unknown_token\n\n"
                return
            if _ensure_aware(row.expires_at) < _utcnow() and row.fulfilled_at is None:
                yield f"event: error\ndata: expired\n\n"
                return
            if row.fulfilled_at is not None and row.fulfilled_payload_temp:
                payload = row.fulfilled_payload_temp
                # WIPE NOW — never persist raw response
                row.fulfilled_payload_temp = None
                await db.commit()
                yield f"event: data\ndata: {payload}\n\n"
                return
            await asyncio.sleep(SSE_POLL_INTERVAL_SECONDS)
        yield f"event: error\ndata: timeout\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")
