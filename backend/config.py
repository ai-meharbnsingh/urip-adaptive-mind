from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://urip:urip_dev@localhost:5432/urip"
    DATABASE_URL_SYNC: str = "postgresql://urip:urip_dev@localhost:5432/urip"
    JWT_SECRET_KEY: str = "urip-dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 8
    URIP_FERNET_KEY: str = ""
    CORS_ORIGINS: str = "http://localhost:8000,http://localhost:3000"

    # Connector API Keys (populated when RE provides access)
    CROWDSTRIKE_CLIENT_ID: str = ""
    CROWDSTRIKE_CLIENT_SECRET: str = ""
    ARMIS_API_KEY: str = ""
    ZSCALER_API_KEY: str = ""
    CYBERARK_API_KEY: str = ""
    OTX_API_KEY: str = ""
    VIRUSTOTAL_API_KEY: str = ""
    JIRA_URL: str = ""
    JIRA_API_TOKEN: str = ""
    SERVICENOW_URL: str = ""
    SERVICENOW_API_TOKEN: str = ""

    # ─── Scoring Configuration (overridable via env vars) ─────
    # Composite formula weights
    COMPOSITE_CVSS_WEIGHT: float = 0.55
    COMPOSITE_EPSS_WEIGHT: float = 2.5
    COMPOSITE_KEV_BONUS: float = 2.0

    # Asset tier bonuses
    TIER_1_BONUS: float = 1.0
    TIER_2_BONUS: float = 0.5
    TIER_3_BONUS: float = 0.0
    TIER_4_BONUS: float = -0.5

    # EPSS defaults when no CVE data
    EPSS_DEFAULT_CRITICAL: float = 0.30
    EPSS_DEFAULT_HIGH: float = 0.20
    EPSS_DEFAULT_MEDIUM: float = 0.10
    EPSS_DEFAULT_LOW: float = 0.05

    # Exploit status thresholds
    EXPLOIT_ACTIVE_THRESHOLD: float = 0.5
    EXPLOIT_POC_THRESHOLD: float = 0.1

    # CVSS severity breakpoints
    CVSS_CRITICAL_THRESHOLD: float = 9.0
    CVSS_HIGH_THRESHOLD: float = 7.0
    CVSS_MEDIUM_THRESHOLD: float = 4.0

    # SLA hours per severity
    SLA_HOURS_CRITICAL: int = 72
    SLA_HOURS_HIGH: int = 168
    SLA_HOURS_MEDIUM: int = 720
    SLA_HOURS_LOW: int = 2160

    # External API URLs
    EPSS_API_URL: str = "https://api.first.org/data/v1/epss"
    KEV_CATALOG_URL: str = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    MITRE_ATTACK_URL: str = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"

    # Cache TTLs (seconds)
    KEV_CACHE_TTL_SECONDS: int = 86400
    MITRE_CACHE_TTL_SECONDS: int = 86400

    # Relevance scoring weights (threat intel)
    RELEVANCE_BRAND_SCORE: float = 40.0
    RELEVANCE_COUNTRY_SCORE: float = 25.0
    RELEVANCE_SECTOR_SCORE: float = 20.0
    RELEVANCE_RANSOMWARE_SCORE: float = 10.0

    # Acceptance review period
    ACCEPTANCE_REVIEW_PERIOD_DAYS: int = 90

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
