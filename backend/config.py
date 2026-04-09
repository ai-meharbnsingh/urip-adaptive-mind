from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://urip:urip_dev@localhost:5432/urip"
    DATABASE_URL_SYNC: str = "postgresql://urip:urip_dev@localhost:5432/urip"
    REDIS_URL: str = "redis://localhost:6379/0"
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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
