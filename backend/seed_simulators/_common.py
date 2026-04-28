"""
backend/seed_simulators/_common.py — shared helpers for URIP-side simulators.
"""
from __future__ import annotations

import hashlib
import random
import uuid
from datetime import datetime, timezone, timedelta


def make_rng(seed: int = 42) -> random.Random:
    return random.Random(seed)


def stable_uuid(*parts: str) -> str:
    """Deterministic UUID4-shaped string from parts."""
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return str(uuid.UUID(h[:32]))


def stable_uuid_obj(*parts: str) -> uuid.UUID:
    """Deterministic UUID object."""
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return uuid.UUID(h[:32])


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# extended connector list — matches connectors/extended_simulator.EXTENDED_SOURCES
EXTENDED_CONNECTORS = [
    "zscaler",
    "netskope",
    "sentinelone",
    "ms_entra",
    "sharepoint",
    "manageengine_sdp",
    "manageengine_ec",
    "manageengine_mdm",
    "tenable",
    "burpsuite",
    "gtb_dlp",
    "cloudsek",
    "extended_simulator",  # The synthetic source itself
]


# Realistic dummy credential shapes per connector
DUMMY_CREDENTIALS_BY_CONNECTOR = {
    "zscaler": {
        "base_url": "https://zsapi.zscalerthree.net",
        "api_key": "obfuscated-zscaler-key-DEMO",
        "username": "svc-urip@example.com",
        "password": "DUMMY-NEVER-USED",
    },
    "netskope": {
        "tenant_url": "https://acme.goskope.com",
        "api_token": "DEMO-netskope-bearer-token",
    },
    "sentinelone": {
        "console_url": "https://acme.sentinelone.net",
        "api_token": "DEMO-s1-token-readonly",
    },
    "ms_entra": {
        "tenant_id": "DEMO-tenant-uuid-here",
        "client_id": "DEMO-app-id-here",
        "client_secret": "DEMO-secret-rotate-on-deploy",
    },
    "sharepoint": {
        "tenant": "acme",
        "client_id": "DEMO-spo-app-id",
        "client_secret": "DEMO-spo-secret",
    },
    "manageengine_sdp": {
        "base_url": "https://sdp.example.com",
        "api_key": "DEMO-sdp-api-key",
    },
    "manageengine_ec": {
        "base_url": "https://ec.example.com",
        "api_key": "DEMO-ec-api-key",
    },
    "manageengine_mdm": {
        "base_url": "https://mdm.example.com",
        "api_key": "DEMO-mdm-api-key",
    },
    "tenable": {
        "access_key": "DEMO-tenable-access-key",
        "secret_key": "DEMO-tenable-secret-key",
        "base_url": "https://cloud.tenable.com",
    },
    "burpsuite": {
        "ent_url": "https://burp.example.com",
        "api_key": "DEMO-burp-enterprise-key",
    },
    "gtb_dlp": {
        "console_url": "https://dlp.example.com",
        "api_key": "DEMO-gtb-api-key",
    },
    "cloudsek": {
        "tenant_url": "https://platform.cloudsek.com/api",
        "api_token": "DEMO-cloudsek-token",
    },
    "extended_simulator": {
        "tenant_id": "acme-demo",
        "mode": "synthetic",
    },
}


# User activity scenarios — actions a CISO/IT team would perform
ACTIVITY_TEMPLATES = [
    # (action, resource_type, weight)
    ("login", "session", 0.20),
    ("view_dashboard", "dashboard", 0.15),
    ("view_risk", "risk", 0.15),
    ("comment_on_risk", "risk", 0.10),
    ("accept_risk", "acceptance_request", 0.05),
    ("create_remediation", "remediation_task", 0.08),
    ("update_remediation_status", "remediation_task", 0.07),
    ("export_report", "report", 0.05),
    ("view_audit_log", "audit_log", 0.05),
    ("update_settings", "tenant", 0.03),
    ("invite_user", "user", 0.02),
    ("rotate_connector_credential", "connector", 0.02),
    ("logout", "session", 0.03),
]
