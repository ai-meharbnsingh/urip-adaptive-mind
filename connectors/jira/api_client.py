"""
Async HTTPX client for Jira Cloud and Jira Data Center REST API v3.

Authentication
--------------
- Jira Cloud (Atlassian-hosted):  Basic auth — base64(email:api_token)
- Jira Data Center / Server:       Bearer token — Personal Access Token (PAT)

The constructor decides the auth mode by which credential is provided:
  - ``email`` + ``api_token`` → Cloud Basic auth
  - ``bearer_token``          → DC/Server Bearer auth

All methods are async and use httpx.AsyncClient.

Jira REST API v3 reference:
  https://developer.atlassian.com/cloud/jira/platform/rest/v3/
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Optional

import httpx

from connectors.base.connector import ConnectorAuthError, ConnectorFetchError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0

# ─────────────────────────────────────────────────────────────────────────────
# ADF helpers
# ─────────────────────────────────────────────────────────────────────────────


def _plain_text_to_adf(text: str) -> dict[str, Any]:
    """
    Convert a plain-text string to Atlassian Document Format (ADF).

    Jira Cloud's /rest/api/3/ endpoints require description in ADF; the v2
    API accepted plain strings but v3 does not.  We produce the minimal valid
    ADF structure: a doc > paragraph > text node.

    For multi-line input we split on newlines and insert hardBreak nodes.
    """
    lines = (text or "").split("\n")
    inline_content: list[dict[str, Any]] = []
    for i, line in enumerate(lines):
        if line:
            inline_content.append({"type": "text", "text": line})
        if i < len(lines) - 1:
            inline_content.append({"type": "hardBreak"})

    # Ensure paragraph has at least one text node so ADF is valid.
    if not inline_content:
        inline_content = [{"type": "text", "text": ""}]

    return {
        "version": 1,
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": inline_content,
            }
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Client
# ─────────────────────────────────────────────────────────────────────────────


class JiraAPIClient:
    """
    Thin async HTTPX wrapper for Jira REST API v3.

    Parameters
    ----------
    base_url : str
        Root URL of the Jira instance.
        Cloud:  https://your-org.atlassian.net
        DC/Server: https://jira.your-domain.com
    email : str, optional
        Atlassian account email — Cloud Basic auth only.
    api_token : str, optional
        Atlassian API token — Cloud Basic auth only.
    bearer_token : str, optional
        Personal Access Token (PAT) — DC/Server Bearer auth.
    timeout : float
        HTTP request timeout in seconds (default 30).

    Raises
    ------
    ValueError
        If neither (email + api_token) nor bearer_token is supplied.
    """

    def __init__(
        self,
        base_url: str,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
        bearer_token: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self.bearer_token = bearer_token
        self.timeout = timeout

        # Decide auth mode
        if bearer_token:
            self._auth_mode = "bearer"
        elif email and api_token:
            self._auth_mode = "basic"
            _raw = f"{email}:{api_token}".encode()
            self._basic_header = "Basic " + base64.b64encode(_raw).decode()
        else:
            raise ValueError(
                "JiraAPIClient requires either (email + api_token) for Cloud "
                "or bearer_token for Data Center / Server."
            )

        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _auth_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._auth_mode == "basic":
            headers["Authorization"] = self._basic_header
        else:  # bearer
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send a request and handle common error codes."""
        url = f"{self.base_url}{path}"
        headers = self._auth_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        logger.debug("Jira API %s %s", method, url)
        response = await self._client.request(method, url, headers=headers, **kwargs)

        if response.status_code in (401, 403):
            raise ConnectorAuthError(
                f"Jira auth failed — HTTP {response.status_code} for {url}. "
                "Check credentials and permissions."
            )
        if response.status_code >= 500:
            raise ConnectorFetchError(
                f"Jira server error — HTTP {response.status_code} for {url}: "
                f"{response.text[:300]}"
            )

        return response

    # ─────────────────────────────────────────────────────────────────────────
    # Public API methods
    # ─────────────────────────────────────────────────────────────────────────

    async def search_issues(
        self,
        jql: str,
        fields: Optional[list[str]] = None,
        max_results: int = 50,
    ) -> dict[str, Any]:
        """
        Search for issues using JQL.

        POST /rest/api/3/search

        Parameters
        ----------
        jql : str
            Jira Query Language string.
        fields : list[str], optional
            Subset of fields to return.  Defaults to common set if not provided.
        max_results : int
            Maximum number of issues to return (default 50, max 100 per Jira docs).

        Returns
        -------
        dict
            Raw Jira search response JSON.
        """
        if fields is None:
            fields = [
                "summary", "status", "priority", "created",
                "updated", "description", "labels", "assignee", "reporter",
            ]

        body: dict[str, Any] = {
            "jql": jql,
            "fields": fields,
            "maxResults": max_results,
        }

        resp = await self._request("POST", "/rest/api/3/search", json=body)
        resp.raise_for_status()
        return resp.json()

    async def get_issue(self, issue_key: str) -> dict[str, Any]:
        """
        Fetch a single issue by key.

        GET /rest/api/3/issue/{key}

        Returns
        -------
        dict
            Raw Jira issue JSON.
        """
        resp = await self._request("GET", f"/rest/api/3/issue/{issue_key}")
        resp.raise_for_status()
        return resp.json()

    async def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
        priority: Optional[str] = None,
        labels: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Create a new Jira issue.

        POST /rest/api/3/issue

        The description is automatically converted from plain text to Atlassian
        Document Format (ADF) which is required by Jira Cloud REST API v3.

        Parameters
        ----------
        project_key : str
            Jira project key (e.g. "SEC", "OPS").
        summary : str
            One-line issue title.
        description : str
            Plain-text description — converted to ADF internally.
        issue_type : str
            Jira issue type name (default "Task").
        priority : str, optional
            Jira priority name (e.g. "High", "Medium").  Omitted if None.
        labels : list[str], optional
            Labels to attach (e.g. ["urip", "security"]).

        Returns
        -------
        dict
            Created issue JSON with ``id``, ``key``, and ``self`` fields.
        """
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary,
            "description": _plain_text_to_adf(description),
            "issuetype": {"name": issue_type},
        }

        if priority:
            fields["priority"] = {"name": priority}

        if labels:
            fields["labels"] = labels

        body = {"fields": fields}

        resp = await self._request("POST", "/rest/api/3/issue", json=body)
        resp.raise_for_status()
        return resp.json()

    async def transition_issue(
        self,
        issue_key: str,
        transition_id: str,
    ) -> None:
        """
        Transition an issue to a new status.

        POST /rest/api/3/issue/{key}/transitions

        Parameters
        ----------
        issue_key : str
            Jira issue key (e.g. "SEC-42").
        transition_id : str
            Target transition ID (numeric string from GET .../transitions).
        """
        body = {"transition": {"id": transition_id}}
        resp = await self._request(
            "POST", f"/rest/api/3/issue/{issue_key}/transitions", json=body
        )
        resp.raise_for_status()

    async def get_myself(self) -> dict[str, Any]:
        """
        Retrieve the authenticated user's profile.

        GET /rest/api/3/myself

        Used by health_check() and authenticate() to verify credentials are
        valid before storing them.

        Returns
        -------
        dict
            User account JSON (accountId, displayName, emailAddress, active).
        """
        resp = await self._request("GET", "/rest/api/3/myself")
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        """Close the underlying httpx.AsyncClient."""
        await self._client.aclose()

    async def __aenter__(self) -> "JiraAPIClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
