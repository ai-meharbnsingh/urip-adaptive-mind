"""
Pydantic v2 models for HashiCorp Vault HTTP API v1 responses.

Covers:
- VaultHealth    — /v1/sys/health
- VaultAuditDevice — one entry from /v1/sys/audit
- VaultAuthMethod  — one entry from /v1/sys/auth
- VaultMount       — one entry from /v1/sys/mounts
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────


class VaultHealth(BaseModel):
    """
    Response from GET /v1/sys/health.

    Fields are optional because Vault returns different subsets depending on
    the node state (sealed nodes return fewer fields).
    """

    model_config = ConfigDict(extra="allow")

    initialized: bool = False
    sealed: bool = True
    standby: bool = False
    performance_standby: bool = False
    replication_performance_mode: Optional[str] = None
    replication_dr_mode: Optional[str] = None
    server_time_utc: Optional[int] = None
    version: Optional[str] = None
    cluster_name: Optional[str] = None

    # URIP-injected fields (added by VaultAPIClient.healthcheck())
    urip_health_status: str = "unknown"
    urip_http_status: Optional[int] = None


# ─────────────────────────────────────────────────────────────────────────────
# Audit Devices
# ─────────────────────────────────────────────────────────────────────────────


class VaultAuditDevice(BaseModel):
    """
    One audit device from the /v1/sys/audit response map.

    path        : mount path (e.g. "file/")
    type        : audit backend type (e.g. "file", "syslog", "socket")
    description : human-readable label
    options     : backend-specific configuration options
    """

    model_config = ConfigDict(extra="allow")

    path: str
    type: str
    description: str = ""
    options: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Auth Methods
# ─────────────────────────────────────────────────────────────────────────────


class VaultAuthMethod(BaseModel):
    """
    One auth method from the /v1/sys/auth response map.

    path        : mount path (e.g. "userpass/", "approle/", "token/")
    type        : auth backend type (e.g. "userpass", "approle", "github")
    accessor    : unique accessor ID assigned by Vault
    description : human-readable label
    """

    model_config = ConfigDict(extra="allow")

    path: str
    type: str
    accessor: str = ""
    description: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Secret Engine Mounts
# ─────────────────────────────────────────────────────────────────────────────


class VaultMount(BaseModel):
    """
    One secret engine mount from the /v1/sys/mounts response map.

    path        : mount path (e.g. "secret/", "kv/", "pki/")
    type        : engine type (e.g. "kv", "pki", "transit", "aws")
    description : human-readable label
    options     : engine-specific options — for kv, includes "version" ("1" or "2")
    """

    model_config = ConfigDict(extra="allow")

    path: str
    type: str
    description: str = ""
    options: dict[str, Any] = Field(default_factory=dict)
