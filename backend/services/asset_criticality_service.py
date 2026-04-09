"""
Asset Criticality Service
Auto-assigns tier from asset name keywords + manual override support.

Tier 1 (Critical):  +1.0 bonus — business-critical, revenue/safety impact
Tier 2 (High):      +0.5 bonus — customer-facing, perimeter, OT
Tier 3 (Medium):    +0.0 bonus — internal tools, workstations
Tier 4 (Low):       -0.5 bonus — test/dev, isolated, replaceable
"""
import re

from backend.services.scoring_config import TIER_BONUS

# Keyword patterns per tier (case-insensitive)
# Order matters: Tier 1 checked first, Tier 4 last
TIER_KEYWORDS: dict[int, list[str]] = {
    1: [
        r"\bsap\b", r"\berp\b", r"\bprd\b", r"\bprod\b",
        r"payment", r"domain.?admin", r"root.?aws", r"\bpam\b", r"\bvault\b",
        r"\bsso\b", r"\bokta\b", r"\bldap\b",
        r"\bhmi\b", r"\bscada\b", r"\bplc\b", r"\bics\b",  # OT/ICS = Tier 1 for manufacturing
        r"\bot\b", r"armis",                                 # RE-specific: OT is safety-critical
        r"finance", r"core.?switch", r"domain.?controller",
    ],
    2: [
        r"dealer", r"\bvpn\b", r"firewall", r"\bwaf\b",
        r"load.?balancer", r"e-?commerce", r"mobile.?app",
        r"\bcrm\b", r"salesforce", r"\bapi\b", r"portal",
        r"\brtu\b", r"conveyor", r"compressor", r"welding",  # OT secondary devices
        r"assembly", r"paint.?shop", r"engine.?test",
        r"\bcdn\b", r"\bids\b", r"\bips\b", r"proxy",
        r"email", r"\bsmtp\b", r"\bdns\b",
    ],
    4: [
        r"\btest\b", r"\bdev\b", r"\blab\b", r"\bstaging\b",
        r"sandbox", r"\bkiosk\b", r"showroom", r"\bpoc\b",
        r"demo", r"temp", r"backup",
    ],
    # Tier 3 is the default — no keywords needed
}

# Compiled patterns for performance
_compiled: dict[int, list[re.Pattern]] = {
    tier: [re.compile(p, re.IGNORECASE) for p in patterns]
    for tier, patterns in TIER_KEYWORDS.items()
}


def classify_asset(asset_name: str) -> int:
    """
    Auto-classify asset into tier 1-4 based on name keywords.
    Tier 1 patterns checked first (highest priority).
    Returns tier number (1-4), default 3.
    """
    if not asset_name:
        return 3

    # Check tiers in priority order: 1 → 4 → 2 → default 3
    for tier in [1, 4, 2]:
        for pattern in _compiled[tier]:
            if pattern.search(asset_name):
                return tier
    return 3


def get_asset_bonus(tier: int) -> float:
    """Get the additive bonus for a given tier."""
    return TIER_BONUS.get(tier, 0.0)


def classify_and_get_bonus(asset_name: str) -> tuple[int, float]:
    """Convenience: returns (tier, bonus) for an asset name."""
    tier = classify_asset(asset_name)
    return tier, get_asset_bonus(tier)
