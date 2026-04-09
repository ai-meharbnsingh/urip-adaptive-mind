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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
