"""
Tests for the composite scoring formula and related functions.
These verify the EXACT calculations documented in BLUEPRINT.md.

No database required — these test pure functions only.
"""
import pytest
from backend.services.exploitability_service import compute_composite, derive_exploit_status
from backend.services.asset_criticality_service import classify_asset, get_asset_bonus
from backend.services.sla_service import compute_sla_deadline


class TestCompositeFormula:
    """Test: composite = max(0, min(10, 0.55*CVSS + 2.5*EPSS + KEV_bonus + asset_bonus))"""

    def test_blueprint_scenario_1_panos(self):
        """CVE-2024-3400: CVSS 10.0, EPSS 0.97, KEV=True, Tier 1 -> 10.0"""
        score = compute_composite(10.0, 0.97, True, "critical", asset_tier=1)
        # 5.5 + 2.425 + 2.0 + 1.0 = 10.925 -> capped at 10.0
        assert score == 10.0

    def test_blueprint_scenario_2_cisco(self):
        """CVE-2023-20198: CVSS 7.2, EPSS 0.95, KEV=True, Tier 1 -> 9.3"""
        score = compute_composite(7.2, 0.95, True, "high", asset_tier=1)
        # 3.96 + 2.375 + 2.0 + 1.0 = 9.335 -> 9.3
        assert score == 9.3

    def test_blueprint_scenario_3_putty(self):
        """CVE-2024-31497: CVSS 5.9, EPSS 0.02, KEV=False, Tier 4 -> 2.8"""
        score = compute_composite(5.9, 0.02, False, "medium", asset_tier=4)
        # 3.245 + 0.05 + 0 + (-0.5) = 2.795 -> 2.8
        assert score == 2.8

    def test_blueprint_scenario_4_easm(self):
        """EASM-EXP-001: CVSS 7.5, EPSS=None (fallback 0.20), KEV=False, Tier 2 -> 5.1"""
        score = compute_composite(7.5, None, False, "high", asset_tier=2)
        # 4.125 + 0.5 + 0 + 0.5 = 5.125 -> 5.1
        assert score == 5.1

    def test_floor_protection_tier4_low_cvss(self):
        """Tier 4 + low CVSS should floor at 0.0, never negative"""
        score = compute_composite(0.1, 0.01, False, "low", asset_tier=4)
        # 0.055 + 0.025 + 0 + (-0.5) = -0.42 -> floored to 0.0
        assert score == 0.0

    def test_cap_at_10(self):
        """Even with all maxes, score caps at 10.0"""
        score = compute_composite(10.0, 1.0, True, "critical", asset_tier=1)
        # 5.5 + 2.5 + 2.0 + 1.0 = 11.0 -> capped at 10.0
        assert score == 10.0

    def test_zero_cvss(self):
        """CVSS 0.0 should still produce a valid score"""
        score = compute_composite(0.0, 0.0, False, "low", asset_tier=3)
        # 0 + 0 + 0 + 0 = 0.0
        assert score == 0.0

    def test_epss_none_uses_severity_default(self):
        """When EPSS is None, use severity-based default"""
        critical = compute_composite(9.0, None, False, "critical", asset_tier=3)
        low = compute_composite(9.0, None, False, "low", asset_tier=3)
        # Critical default 0.30 -> 2.5*0.30 = 0.75 extra
        # Low default 0.05 -> 2.5*0.05 = 0.125 extra
        assert critical > low

    def test_kev_bonus_applied(self):
        """KEV=True adds exactly 2.0 to the score"""
        without_kev = compute_composite(7.0, 0.5, False, "high", asset_tier=3)
        with_kev = compute_composite(7.0, 0.5, True, "high", asset_tier=3)
        assert round(with_kev - without_kev, 1) == 2.0

    def test_asset_tier_impact(self):
        """Same CVE on different tiers produces different scores"""
        tier1 = compute_composite(8.0, 0.5, False, "high", asset_tier=1)
        tier3 = compute_composite(8.0, 0.5, False, "high", asset_tier=3)
        tier4 = compute_composite(8.0, 0.5, False, "high", asset_tier=4)
        assert tier1 > tier3 > tier4
        assert round(tier1 - tier3, 1) == 1.0  # Tier 1 bonus = +1.0
        assert round(tier3 - tier4, 1) == 0.5  # Tier 4 penalty = -0.5

    def test_input_clamping_cvss_above_10(self):
        """CVSS > 10.0 should be clamped to 10.0"""
        normal = compute_composite(10.0, 0.5, False, "critical", asset_tier=3)
        clamped = compute_composite(15.0, 0.5, False, "critical", asset_tier=3)
        assert normal == clamped

    def test_input_clamping_epss_above_1(self):
        """EPSS > 1.0 should be clamped to 1.0"""
        normal = compute_composite(8.0, 1.0, False, "high", asset_tier=3)
        clamped = compute_composite(8.0, 2.0, False, "high", asset_tier=3)
        assert normal == clamped

    def test_input_clamping_negative_cvss(self):
        """Negative CVSS should be clamped to 0.0"""
        score = compute_composite(-5.0, 0.5, False, "low", asset_tier=3)
        zero_score = compute_composite(0.0, 0.5, False, "low", asset_tier=3)
        assert score == zero_score

    def test_input_clamping_invalid_asset_tier(self):
        """Invalid asset_tier should be clamped to valid range"""
        tier1 = compute_composite(8.0, 0.5, False, "high", asset_tier=1)
        clamped_low = compute_composite(8.0, 0.5, False, "high", asset_tier=0)
        clamped_high = compute_composite(8.0, 0.5, False, "high", asset_tier=99)
        assert clamped_low == tier1  # 0 clamped to 1
        tier4 = compute_composite(8.0, 0.5, False, "high", asset_tier=4)
        assert clamped_high == tier4  # 99 clamped to 4

    def test_asset_name_classification(self):
        """Asset name-based tier classification works"""
        score_sap = compute_composite(8.0, 0.5, False, "high", asset_name="SAP ERP Production")
        score_test = compute_composite(8.0, 0.5, False, "high", asset_name="Test Server Dev")
        assert score_sap > score_test  # SAP = Tier 1 (+1.0), Test = Tier 4 (-0.5)


class TestExploitStatus:
    """Test exploit status derivation"""

    def test_kev_is_weaponized(self):
        assert derive_exploit_status(0.01, True) == "weaponized"
        assert derive_exploit_status(None, True) == "weaponized"
        assert derive_exploit_status(0.99, True) == "weaponized"  # KEV always wins

    def test_high_epss_is_active(self):
        assert derive_exploit_status(0.5, False) == "active"
        assert derive_exploit_status(0.99, False) == "active"

    def test_medium_epss_is_poc(self):
        assert derive_exploit_status(0.1, False) == "poc"
        assert derive_exploit_status(0.49, False) == "poc"

    def test_low_epss_is_none(self):
        assert derive_exploit_status(0.09, False) == "none"
        assert derive_exploit_status(0.0, False) == "none"
        assert derive_exploit_status(None, False) == "none"

    def test_input_clamping(self):
        """EPSS > 1.0 should still work (clamped)"""
        assert derive_exploit_status(2.0, False) == "active"
        assert derive_exploit_status(-1.0, False) == "none"


class TestAssetClassification:
    """Test asset tier keyword classification"""

    def test_tier1_keywords(self):
        assert classify_asset("SAP ERP Production SAP-PRD-01") == 1
        assert classify_asset("Chennai Plant HMI Controller") == 1
        assert classify_asset("Assembly Line SCADA") == 1
        assert classify_asset("Paint Shop PLC PLC-PAINT-03") == 1
        assert classify_asset("Domain Admin Group") == 1
        assert classify_asset("CyberArk PAM Vault") == 1

    def test_tier2_keywords(self):
        assert classify_asset("Dealer Portal") == 2
        assert classify_asset("VPN Gateway Primary") == 2
        assert classify_asset("Firewall FW-DMZ-01") == 2
        assert classify_asset("CRM Salesforce System") == 2

    def test_tier3_default(self):
        assert classify_asset("Marketing MacBook") == 3
        assert classify_asset("Some Random Asset") == 3
        assert classify_asset("") == 3

    def test_tier4_keywords(self):
        assert classify_asset("Test Server QA-01") == 4
        assert classify_asset("QA Lab Machine") == 4
        assert classify_asset("Staging Environment") == 4
        assert classify_asset("Showroom Kiosk") == 4

    def test_tier1_priority_over_tier4(self):
        """If asset has both Tier 1 and Tier 4 keywords, Tier 1 wins"""
        assert classify_asset("SAP Test Server") == 1  # SAP is Tier 1, checked first

    def test_bonus_values(self):
        assert get_asset_bonus(1) == 1.0
        assert get_asset_bonus(2) == 0.5
        assert get_asset_bonus(3) == 0.0
        assert get_asset_bonus(4) == -0.5


class TestSLADeadlines:
    """Test SLA deadline computation"""

    def test_critical_72h(self):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        deadline = compute_sla_deadline("critical", now)
        expected = now + timedelta(hours=72)
        assert abs((deadline - expected).total_seconds()) < 1

    def test_high_7d(self):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        deadline = compute_sla_deadline("high", now)
        expected = now + timedelta(hours=168)
        assert abs((deadline - expected).total_seconds()) < 1

    def test_medium_30d(self):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        deadline = compute_sla_deadline("medium", now)
        expected = now + timedelta(hours=720)
        assert abs((deadline - expected).total_seconds()) < 1

    def test_low_90d(self):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        deadline = compute_sla_deadline("low", now)
        expected = now + timedelta(hours=2160)
        assert abs((deadline - expected).total_seconds()) < 1
