"""
Tests for AWS CSPM connector.

Uses unittest.mock to patch boto3.client.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from connectors.aws_cspm.connector import AwsCspmConnector
from connectors.base.connector import (
    ConnectorAuthError,
    ConnectorFetchError,
    ConnectorSession,
)


@pytest.fixture
def aws_connector() -> AwsCspmConnector:
    return AwsCspmConnector()


@pytest.fixture
def valid_creds() -> dict:
    return {
        "access_key": "AKIAIOSFODNN7EXAMPLE",
        "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "region": "us-east-1",
    }


# ---------------------------------------------------------------------------
# authenticate
# ---------------------------------------------------------------------------

def test_authenticate_success(aws_connector: AwsCspmConnector, valid_creds: dict):
    with patch("connectors.aws_cspm.api_client.boto3.client") as mock_boto:
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789"}
        mock_boto.return_value = mock_sts

        session = aws_connector.authenticate(valid_creds)
        assert isinstance(session, ConnectorSession)
        assert session.connector_name == "aws_cspm"


def test_authenticate_missing_credentials(aws_connector: AwsCspmConnector):
    with pytest.raises(ConnectorAuthError) as exc_info:
        aws_connector.authenticate({"region": "us-east-1"})
    assert "access_key" in str(exc_info.value)


def test_authenticate_invalid_credentials(aws_connector: AwsCspmConnector, valid_creds: dict):
    with patch("connectors.aws_cspm.api_client.boto3.client") as mock_boto:
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = Exception("Invalid credentials")
        mock_boto.return_value = mock_sts

        with pytest.raises(ConnectorAuthError):
            aws_connector.authenticate(valid_creds)


# ---------------------------------------------------------------------------
# fetch_findings
# ---------------------------------------------------------------------------

def test_fetch_findings_config(aws_connector: AwsCspmConnector, valid_creds: dict):
    with patch("connectors.aws_cspm.api_client.boto3.client") as mock_boto:
        mock_config = MagicMock()
        # describe_config_rules paginator
        mock_config.get_paginator.side_effect = lambda op: MagicMock(
            paginate=MagicMock(return_value=[
                {"ConfigRules": [{"ConfigRuleName": "rule1"}]},
            ] if op == "describe_config_rules" else [
                {"ComplianceByConfigRules": [
                    {"ConfigRuleName": "rule1", "Compliance": {"ComplianceType": "NON_COMPLIANT"}}
                ]},
            ])
        )

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123"}

        def side_effect(**kwargs):
            if kwargs.get("service_name") == "sts":
                return mock_sts
            return mock_config

        mock_boto.side_effect = side_effect
        aws_connector.authenticate(valid_creds)

        findings = aws_connector.fetch_findings(datetime.now(timezone.utc), tenant_id="t1")
        assert len(findings) >= 1
        assert any("config" in f.id for f in findings)


def test_fetch_findings_securityhub(aws_connector: AwsCspmConnector, valid_creds: dict):
    with patch("connectors.aws_cspm.api_client.boto3.client") as mock_boto:
        mock_sh = MagicMock()
        mock_sh.get_paginator.return_value.paginate.return_value = [
            {"Findings": [{"Id": "sh-1", "Title": "Finding"}]},
        ]
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123"}

        def side_effect(**kwargs):
            if kwargs.get("service_name") == "sts":
                return mock_sts
            return mock_sh

        mock_boto.side_effect = side_effect
        aws_connector.authenticate(valid_creds)
        findings = aws_connector.fetch_findings(datetime.now(timezone.utc), tenant_id="t1")
        assert any("securityhub" in f.id for f in findings)


def test_fetch_findings_guardduty(aws_connector: AwsCspmConnector, valid_creds: dict):
    with patch("connectors.aws_cspm.api_client.boto3.client") as mock_boto:
        mock_gd = MagicMock()
        mock_gd.list_detectors.return_value = {"DetectorIds": ["d1"]}
        mock_gd.get_paginator.return_value.paginate.return_value = [
            {"FindingIds": ["f1"]},
        ]
        mock_gd.get_findings.return_value = {
            "Findings": [{"Id": "gd-1", "Title": "GD Finding"}]
        }
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123"}

        def side_effect(**kwargs):
            if kwargs.get("service_name") == "sts":
                return mock_sts
            return mock_gd

        mock_boto.side_effect = side_effect
        aws_connector.authenticate(valid_creds)
        findings = aws_connector.fetch_findings(datetime.now(timezone.utc), tenant_id="t1")
        assert any("guardduty" in f.id for f in findings)


def test_fetch_findings_access_analyzer(aws_connector: AwsCspmConnector, valid_creds: dict):
    with patch("connectors.aws_cspm.api_client.boto3.client") as mock_boto:
        mock_aa = MagicMock()
        mock_aa.list_analyzers.return_value = {"analyzers": [{"arn": "arn:aws:accessanalyzer::123:analyzer/test"}]}
        mock_aa.get_paginator.return_value.paginate.return_value = [
            {"findings": [{"id": "aa-1", "isPublic": True}]},
        ]
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123"}

        def side_effect(**kwargs):
            if kwargs.get("service_name") == "sts":
                return mock_sts
            return mock_aa

        mock_boto.side_effect = side_effect
        aws_connector.authenticate(valid_creds)
        findings = aws_connector.fetch_findings(datetime.now(timezone.utc), tenant_id="t1")
        assert any("accessanalyzer" in f.id for f in findings)


def test_fetch_findings_not_authenticated(aws_connector: AwsCspmConnector):
    with pytest.raises(ConnectorFetchError) as exc_info:
        aws_connector.fetch_findings(datetime.now(timezone.utc))
    assert "not authenticated" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------

def test_normalize_config_noncompliant(aws_connector: AwsCspmConnector):
    from connectors.base.connector import RawFinding
    raw = RawFinding(
        id="config:test",
        source="aws_cspm",
        raw_data={
            "type": "config",
            "data": {
                "ConfigRuleName": "test-rule",
                "ComplianceType": "NON_COMPLIANT",
                "ConfigRuleArn": "arn:aws:config:us-east-1:123:config-rule/test",
            },
        },
        fetched_at=datetime.now(timezone.utc),
        tenant_id="t1",
    )
    record = aws_connector.normalize(raw)
    assert record.severity == "high"
    assert record.source == "aws_cspm"
    assert record.domain == "cloud"


def test_normalize_config_compliant(aws_connector: AwsCspmConnector):
    from connectors.base.connector import RawFinding
    raw = RawFinding(
        id="config:test",
        source="aws_cspm",
        raw_data={
            "type": "config",
            "data": {
                "ConfigRuleName": "test-rule",
                "ComplianceType": "COMPLIANT",
                "ConfigRuleArn": "arn:aws:config:us-east-1:123:config-rule/test",
            },
        },
        fetched_at=datetime.now(timezone.utc),
        tenant_id="t1",
    )
    record = aws_connector.normalize(raw)
    assert record.severity == "low"


def test_normalize_securityhub(aws_connector: AwsCspmConnector):
    from connectors.base.connector import RawFinding
    raw = RawFinding(
        id="securityhub:sh-1",
        source="aws_cspm",
        raw_data={
            "type": "securityhub",
            "data": {
                "Id": "sh-1",
                "Title": "Critical Finding",
                "Description": "Test",
                "Severity": {"Label": "CRITICAL"},
                "Resources": [{"Id": "arn:aws:s3:::bucket"}],
            },
        },
        fetched_at=datetime.now(timezone.utc),
        tenant_id="t1",
    )
    record = aws_connector.normalize(raw)
    assert record.severity == "critical"
    assert record.asset == "arn:aws:s3:::bucket"


def test_normalize_guardduty(aws_connector: AwsCspmConnector):
    from connectors.base.connector import RawFinding
    raw = RawFinding(
        id="guardduty:gd-1",
        source="aws_cspm",
        raw_data={
            "type": "guardduty",
            "data": {
                "Id": "gd-1",
                "Title": "GD Finding",
                "Description": "Test",
                "Severity": 8.5,
                "Resource": {"ResourceType": "EC2"},
            },
        },
        fetched_at=datetime.now(timezone.utc),
        tenant_id="t1",
    )
    record = aws_connector.normalize(raw)
    assert record.severity == "high"
    assert "GD Finding" in record.finding


def test_normalize_access_analyzer(aws_connector: AwsCspmConnector):
    from connectors.base.connector import RawFinding
    raw = RawFinding(
        id="accessanalyzer:aa-1",
        source="aws_cspm",
        raw_data={
            "type": "accessanalyzer",
            "data": {
                "id": "aa-1",
                "isPublic": True,
                "resourceType": "S3Bucket",
                "resource": "arn:aws:s3:::bucket",
                "principal": {"AWS": "*"},
                "action": {"S3:GetObject": {}},
            },
        },
        fetched_at=datetime.now(timezone.utc),
        tenant_id="t1",
    )
    record = aws_connector.normalize(raw)
    assert record.severity == "high"
    assert "public access" in record.finding.lower()


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------

def test_health_check_ok(aws_connector: AwsCspmConnector):
    h = aws_connector.health_check()
    assert h.status == "ok"
    assert h.connector_name == "aws_cspm"


def test_health_check_degraded(aws_connector: AwsCspmConnector):
    aws_connector._error_count = 2
    h = aws_connector.health_check()
    assert h.status == "degraded"


def test_health_check_error(aws_connector: AwsCspmConnector):
    aws_connector._error_count = 10
    h = aws_connector.health_check()
    assert h.status == "error"
