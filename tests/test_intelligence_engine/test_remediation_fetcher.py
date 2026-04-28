import pytest


def test_fetch_remediation_cve_uses_nvd(monkeypatch):
    from backend.services import remediation_fetcher as svc

    monkeypatch.setattr(svc, "_fetch_nvd_remediation", lambda cve_id: ["Apply vendor patch"])

    finding = svc.NormalizedFinding(
        source="crowdstrike",
        finding_type="cve",
        cve_id="CVE-2024-9999",
        advisory_text="Apply patch KB5002099. Disable anonymous access. Enable MFA.",
    )
    steps = svc.fetch_remediation(finding)
    assert any("patch" in s.lower() for s in steps)


def test_fetch_remediation_cert_in_parses_action_items():
    from backend.services.remediation_fetcher import NormalizedFinding, fetch_remediation

    finding = NormalizedFinding(
        source="cert_in",
        finding_type="cert_in",
        advisory_text="Update OpenSSL to 3.1.4. Restart affected services. Verify with openssl version.",
    )
    steps = fetch_remediation(finding)
    assert any("update" in s.lower() for s in steps)
    assert any("restart" in s.lower() for s in steps)


def test_fetch_remediation_vapt_uses_recommendation_field():
    from backend.services.remediation_fetcher import NormalizedFinding, fetch_remediation

    finding = NormalizedFinding(
        source="vapt",
        finding_type="vapt",
        remediation_recommendation="Sanitize user input on /api/upload.",
    )
    assert fetch_remediation(finding) == ["Sanitize user input on /api/upload."]


def test_fetch_remediation_bug_bounty_uses_researcher_recommendation():
    from backend.services.remediation_fetcher import NormalizedFinding, fetch_remediation

    finding = NormalizedFinding(
        source="bug_bounty",
        finding_type="bug_bounty",
        researcher_recommendation="Fix IDOR by adding authorization checks.",
    )
    assert fetch_remediation(finding) == ["Fix IDOR by adding authorization checks."]


def test_fetch_remediation_soc_alert_playbook_map():
    from backend.services.remediation_fetcher import NormalizedFinding, fetch_remediation

    finding = NormalizedFinding(
        source="soc",
        finding_type="soc_alert",
        alert_type="rogue_device",
    )
    steps = fetch_remediation(finding)
    assert any("isolate" in s.lower() for s in steps)


def test_fetch_remediation_ioc_match_standard_playbook():
    from backend.services.remediation_fetcher import NormalizedFinding, fetch_remediation

    finding = NormalizedFinding(
        source="threat_intel",
        finding_type="ioc_match",
        indicator_type="ip",
        indicator_value="1.2.3.4",
    )
    steps = fetch_remediation(finding)
    assert any("block" in s.lower() for s in steps)


def test_fetch_remediation_ssl_expired_fixed_text():
    from backend.services.remediation_fetcher import NormalizedFinding, fetch_remediation

    finding = NormalizedFinding(source="scanner", finding_type="ssl_expired")
    steps = fetch_remediation(finding)
    assert any("renew" in s.lower() for s in steps)


def test_fetch_remediation_missing_dmarc_fixed_text():
    from backend.services.remediation_fetcher import NormalizedFinding, fetch_remediation

    finding = NormalizedFinding(
        source="scanner",
        finding_type="missing_dmarc",
        dmarc_rua_email="admin@example.com",
    )
    steps = fetch_remediation(finding)
    assert any("dmarc" in s.lower() for s in steps)

