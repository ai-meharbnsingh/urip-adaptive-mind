import pytest


def test_severity_normalizer_crowdstrike_exprt_0_100_div10():
    from backend.services.severity_normalizer import SeverityNormalizer

    n = SeverityNormalizer()
    assert n.normalize(85, "crowdstrike") == 8.5
    assert n.normalize("0", "crowdstrike") == 0.0
    assert n.normalize(100, "crowdstrike") == 10.0


def test_severity_normalizer_armis_autodetect_0_10_vs_0_100():
    from backend.services.severity_normalizer import SeverityNormalizer

    n = SeverityNormalizer()
    assert n.normalize(7.5, "armis") == 7.5
    assert n.normalize(75, "armis") == 7.5
    assert n.normalize("10", "armis") == 10.0
    assert n.normalize(100, "armis") == 10.0


def test_severity_normalizer_vapt_cvss_direct():
    from backend.services.severity_normalizer import SeverityNormalizer

    n = SeverityNormalizer()
    assert n.normalize(8.5, "vapt") == 8.5


@pytest.mark.parametrize(
    ("label", "expected"),
    [("Critical", 9.0), ("High", 7.5), ("Medium", 5.0), ("Low", 3.0)],
)
def test_severity_normalizer_cert_in_map(label, expected):
    from backend.services.severity_normalizer import SeverityNormalizer

    n = SeverityNormalizer()
    assert n.normalize(label, "cert_in") == expected


def test_severity_normalizer_bug_bounty_priority_waterfall_modifiers():
    from backend.services.severity_normalizer import SeverityNormalizer

    n = SeverityNormalizer()

    # Base mapping
    assert n.normalize("P1", "bug_bounty") == 9.0
    assert n.normalize("P4", "bug_bounty") == 3.0

    # Waterfall (base + impact_modifier + exploit_modifier)
    raw = {"priority": "P2", "impact": "high", "exploit": "active"}
    # Expected: 7.0 base + 0.5 impact + 0.5 exploit = 8.0
    assert n.normalize(raw, "bug_bounty") == 8.0


@pytest.mark.parametrize(
    ("label", "expected"),
    [("Critical", 9.0), ("High", 7.5), ("Medium", 5.0), ("Low", 3.0)],
)
def test_severity_normalizer_soc_map(label, expected):
    from backend.services.severity_normalizer import SeverityNormalizer

    n = SeverityNormalizer()
    assert n.normalize(label, "soc") == expected


@pytest.mark.parametrize(
    ("label", "expected"),
    [("info", 1.0), ("low", 3.0), ("medium", 5.0), ("high", 7.5), ("critical", 9.0)],
)
def test_severity_normalizer_generic_string_severities(label, expected):
    from backend.services.severity_normalizer import SeverityNormalizer

    n = SeverityNormalizer()
    assert n.normalize(label, "generic") == expected


def test_severity_normalizer_unknown_source_raises_value_error():
    from backend.services.severity_normalizer import SeverityNormalizer

    n = SeverityNormalizer()
    with pytest.raises(ValueError):
        n.normalize("High", "totally_unknown_vendor")

