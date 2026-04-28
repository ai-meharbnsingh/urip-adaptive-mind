"""Auto-remediation executors — unit tests with mocked HTTP / subprocess."""
from __future__ import annotations

import dataclasses
import subprocess
from typing import Any

import httpx
import pytest

from backend.services.auto_remediation.ansible import AnsibleExecutor
from backend.services.auto_remediation.crowdstrike_rtr import CrowdStrikeRTRExecutor
from backend.services.auto_remediation.cyberark import CyberArkExecutor
from backend.services.auto_remediation.fortinet import FortinetExecutor


@dataclasses.dataclass
class FakeRisk:
    risk_id: str = "RISK-X"
    asset: str = "device-01"
    cve_id: str | None = "CVE-2024-1234"
    finding: str = "RCE in OpenSSL"
    source: str = "crowdstrike"
    indicator_value: str | None = None
    cyberark_account_id: str | None = None


def _mock_transport(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


# --------------------------------------------------------------------------- #
# CrowdStrike RTR
# --------------------------------------------------------------------------- #
def test_crowdstrike_dry_run_does_not_call_api():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(500)

    client = _mock_transport(handler)
    ex = CrowdStrikeRTRExecutor(client=client)
    result = ex.execute(FakeRisk(), dry_run=True)
    assert result.success
    assert result.dry_run
    assert calls == []


def test_crowdstrike_live_succeeds_on_2xx():
    def handler(request: httpx.Request) -> httpx.Response:
        # Falcon OAuth2 token exchange happens before any RTR call.
        if request.url.path == "/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "tok-abc", "expires_in": 1799, "token_type": "bearer"},
            )
        if "sessions" in request.url.path:
            return httpx.Response(201, json={"resources": [{"session_id": "sess1"}]})
        if "admin-command" in request.url.path:
            return httpx.Response(201, json={"resources": [{"task_id": "t1"}]})
        return httpx.Response(404)

    client = _mock_transport(handler)
    ex = CrowdStrikeRTRExecutor(client=client, client_id="id", client_secret="secret")
    result = ex.execute(FakeRisk(), dry_run=False)
    assert result.success
    assert "sess1" in (result.output_log or "")


def test_crowdstrike_live_fails_on_500():
    def handler(request: httpx.Request) -> httpx.Response:
        # OAuth2 succeeds; RTR session call returns 500.
        if request.url.path == "/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "tok-abc", "expires_in": 1799, "token_type": "bearer"},
            )
        return httpx.Response(500, text="internal error")

    client = _mock_transport(handler)
    ex = CrowdStrikeRTRExecutor(client=client, client_id="id", client_secret="secret")
    result = ex.execute(FakeRisk(), dry_run=False)
    assert not result.success
    assert "500" in (result.error or "")


def test_crowdstrike_implication_check_reports_no_downtime():
    ex = CrowdStrikeRTRExecutor()
    impl = ex.implication_check(FakeRisk())
    assert impl.expected_downtime_minutes == 0
    assert "device-01" in impl.services_affected


# --------------------------------------------------------------------------- #
# Ansible
# --------------------------------------------------------------------------- #
def test_ansible_dry_run_does_not_invoke_subprocess():
    invoked = {"count": 0}

    def runner(cmd, timeout):
        invoked["count"] += 1
        return subprocess.CompletedProcess(cmd, 0, "ok", "")

    ex = AnsibleExecutor(playbook_path="/tmp/play.yml", runner=runner)
    result = ex.execute(FakeRisk(), dry_run=True)
    assert result.success
    assert result.dry_run
    assert invoked["count"] == 0


def test_ansible_live_calls_subprocess_with_playbook_path():
    captured: dict[str, Any] = {}

    def runner(cmd, timeout):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "PLAY [...] OK\n", "")

    ex = AnsibleExecutor(playbook_path="/tmp/patch.yml", runner=runner)
    result = ex.execute(FakeRisk(), dry_run=False)
    assert result.success
    assert "ansible-playbook" in captured["cmd"][0]
    assert "/tmp/patch.yml" in captured["cmd"]


def test_ansible_live_returncode_nonzero_marks_failure():
    def runner(cmd, timeout):
        return subprocess.CompletedProcess(cmd, 2, "", "OOM")

    ex = AnsibleExecutor(playbook_path="/tmp/p.yml", runner=runner)
    result = ex.execute(FakeRisk(), dry_run=False)
    assert not result.success
    assert "exited with 2" in (result.error or "")


def test_ansible_timeout_returns_failure_without_raising():
    def runner(cmd, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout, output="partial")

    ex = AnsibleExecutor(playbook_path="/tmp/p.yml", runner=runner, timeout_seconds=1)
    result = ex.execute(FakeRisk(), dry_run=False)
    assert not result.success
    assert "timed out" in (result.error or "").lower()


# --------------------------------------------------------------------------- #
# Fortinet
# --------------------------------------------------------------------------- #
def test_fortinet_blocks_ip_in_addrgrp():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.read().decode()
        return httpx.Response(200, json={"status": "ok"})

    client = _mock_transport(handler)
    ex = FortinetExecutor(base_url="https://fg.test", api_token="tok", client=client)
    risk = FakeRisk(indicator_value="1.2.3.4", source="threat_intel")
    result = ex.execute(risk, dry_run=False)
    assert result.success
    assert "addrgrp" in captured["url"]
    assert "1.2.3.4" in captured["body"]


def test_fortinet_dry_run_returns_would_have_blocked():
    ex = FortinetExecutor(base_url="https://fg.test", api_token="tok")
    risk = FakeRisk(indicator_value="1.2.3.4", source="threat_intel")
    result = ex.execute(risk, dry_run=True)
    assert result.success
    assert result.dry_run
    assert result.after_state["blocked"] == "would-have-blocked"


# --------------------------------------------------------------------------- #
# CyberArk
# --------------------------------------------------------------------------- #
def test_cyberark_rotates_account():
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"status": "ok"})

    client = _mock_transport(handler)
    ex = CyberArkExecutor(base_url="https://ca.test", auth_token="tok", client=client)
    risk = FakeRisk(cyberark_account_id="acct-123", source="pam")
    result = ex.execute(risk, dry_run=False)
    assert result.success
    assert "acct-123" in captured["url"]


def test_cyberark_implication_check_predicts_5min_downtime():
    ex = CyberArkExecutor()
    impl = ex.implication_check(FakeRisk(asset="acct-1"))
    assert impl.expected_downtime_minutes == 5
