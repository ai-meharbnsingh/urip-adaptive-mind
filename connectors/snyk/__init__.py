"""
connectors/snyk — Snyk SCA / Container / IaC / Code connector for URIP.

Exposes:
    SnykConnector   — registered under "snyk" in the global registry
    SnykAPIClient   — async HTTPX client for Snyk REST API v2024-10-15
    SnykIssue       — Pydantic v2 model for a Snyk issue
    SnykProject     — Pydantic v2 model for a Snyk project
"""

from connectors.snyk.api_client import SnykAPIClient
from connectors.snyk.connector import SnykConnector
from connectors.snyk.schemas import SnykIssue, SnykProject

__all__ = ["SnykAPIClient", "SnykConnector", "SnykIssue", "SnykProject"]
