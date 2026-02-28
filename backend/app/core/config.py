from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # KIS API
    KIS_APP_KEY: str
    KIS_APP_SECRET: str
    KIS_ACCOUNT_NO: str
    KIS_BASE_URL: str = "https://openapi.koreainvestment.com:9443"

    # Benchmark Ticker (KOSPI for Mansfield RS)
    BENCHMARK_TICKER: str = "0001"

    # API Settings
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Technical Analysis Dashboard"

    # Cache TTL (seconds)
    CACHE_TTL_CURRENT: int = 300  # 5 minutes for current data
    CACHE_TTL_HISTORICAL: int = 86400  # 24 hours for historical data

    # Rate Limiting
    KIS_RATE_LIMIT: int = 20  # requests per second
    KIS_RETRY_COUNT: int = 3
    KIS_RETRY_DELAY: float = 0.5  # seconds

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
