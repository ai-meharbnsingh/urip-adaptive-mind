"""
URIP Scoring Configuration — Single source of truth.
All scoring constants in one place. Change here = changes everywhere.
In production, these would come from a database table or admin panel.
"""
from backend.config import settings

# Composite formula weights
CVSS_WEIGHT = float(getattr(settings, 'COMPOSITE_CVSS_WEIGHT', 0.55))
EPSS_WEIGHT = float(getattr(settings, 'COMPOSITE_EPSS_WEIGHT', 2.5))
KEV_BONUS = float(getattr(settings, 'COMPOSITE_KEV_BONUS', 2.0))

# Asset tier bonuses
TIER_BONUS = {
    1: float(getattr(settings, 'TIER_1_BONUS', 1.0)),
    2: float(getattr(settings, 'TIER_2_BONUS', 0.5)),
    3: float(getattr(settings, 'TIER_3_BONUS', 0.0)),
    4: float(getattr(settings, 'TIER_4_BONUS', -0.5)),
}

# EPSS defaults when no CVE data
EPSS_DEFAULTS = {
    "critical": float(getattr(settings, 'EPSS_DEFAULT_CRITICAL', 0.30)),
    "high": float(getattr(settings, 'EPSS_DEFAULT_HIGH', 0.20)),
    "medium": float(getattr(settings, 'EPSS_DEFAULT_MEDIUM', 0.10)),
    "low": float(getattr(settings, 'EPSS_DEFAULT_LOW', 0.05)),
}

# Exploit status thresholds
EXPLOIT_ACTIVE_THRESHOLD = float(getattr(settings, 'EXPLOIT_ACTIVE_THRESHOLD', 0.5))
EXPLOIT_POC_THRESHOLD = float(getattr(settings, 'EXPLOIT_POC_THRESHOLD', 0.1))

# CVSS severity breakpoints
CVSS_CRITICAL_THRESHOLD = float(getattr(settings, 'CVSS_CRITICAL_THRESHOLD', 9.0))
CVSS_HIGH_THRESHOLD = float(getattr(settings, 'CVSS_HIGH_THRESHOLD', 7.0))
CVSS_MEDIUM_THRESHOLD = float(getattr(settings, 'CVSS_MEDIUM_THRESHOLD', 4.0))

# SLA hours per severity
SLA_HOURS = {
    "critical": int(getattr(settings, 'SLA_HOURS_CRITICAL', 72)),
    "high": int(getattr(settings, 'SLA_HOURS_HIGH', 168)),
    "medium": int(getattr(settings, 'SLA_HOURS_MEDIUM', 720)),
    "low": int(getattr(settings, 'SLA_HOURS_LOW', 2160)),
}

# External API URLs
EPSS_API_URL = getattr(settings, 'EPSS_API_URL', 'https://api.first.org/data/v1/epss')
KEV_CATALOG_URL = getattr(settings, 'KEV_CATALOG_URL', 'https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json')
MITRE_ATTACK_URL = getattr(settings, 'MITRE_ATTACK_URL', 'https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json')

# Cache TTLs (seconds)
KEV_CACHE_TTL = int(getattr(settings, 'KEV_CACHE_TTL_SECONDS', 86400))
MITRE_CACHE_TTL = int(getattr(settings, 'MITRE_CACHE_TTL_SECONDS', 86400))

# Relevance scoring weights (threat intel)
RELEVANCE_BRAND_SCORE = float(getattr(settings, 'RELEVANCE_BRAND_SCORE', 40.0))
RELEVANCE_COUNTRY_SCORE = float(getattr(settings, 'RELEVANCE_COUNTRY_SCORE', 25.0))
RELEVANCE_SECTOR_SCORE = float(getattr(settings, 'RELEVANCE_SECTOR_SCORE', 20.0))
RELEVANCE_RANSOMWARE_SCORE = float(getattr(settings, 'RELEVANCE_RANSOMWARE_SCORE', 10.0))

# Acceptance review period
ACCEPTANCE_REVIEW_PERIOD_DAYS = int(getattr(settings, 'ACCEPTANCE_REVIEW_PERIOD_DAYS', 90))
