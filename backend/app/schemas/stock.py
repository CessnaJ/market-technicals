from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal, Optional


class StockBase(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    name: str = Field(..., description="Stock name")
    market: Optional[str] = Field(None, description="Market: KOSPI, KOSDAQ")
    sector: Optional[str] = Field(None, description="Sector")
    industry: Optional[str] = Field(None, description="Industry")


class StockCreate(StockBase):
    pass


class StockUpdate(BaseModel):
    name: Optional[str] = None
    market: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    is_active: Optional[bool] = None


class Stock(StockBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StockSearchSuggestion(BaseModel):
    ticker: str
    name: str
    market: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    match_type: Literal[
        "ticker_exact",
        "ticker_prefix",
        "name_exact",
        "name_prefix",
        "name_contains",
        "initials_prefix",
        "initials_contains",
    ]


class StockSearchResponse(BaseModel):
    master_ready: bool
    suggestions: list[StockSearchSuggestion]


class StockTheme(BaseModel):
    code: str
    name: str


class RelatedThemeGroup(BaseModel):
    theme_code: str
    theme_name: str
    stocks: list[StockSearchSuggestion]


class StockProfileResponse(BaseModel):
    ticker: str
    name: str
    market: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    themes: list[StockTheme]
    related_by_sector: list[StockSearchSuggestion]
    related_by_theme: list[RelatedThemeGroup]


class StockMasterSyncResponse(BaseModel):
    kospi_count: int
    kosdaq_count: int
    theme_links: int
    updated_at: str


class PricePreloadSeedRequest(BaseModel):
    target_days: int = Field(730, ge=30, le=3650)
    markets: Optional[list[str]] = None
    limit: Optional[int] = Field(None, ge=1, le=10000)
    reset_existing: bool = False


class PricePreloadSeedResponse(BaseModel):
    target_days: int
    markets: list[str]
    seeded: int
    updated: int
    skipped: int
    total_jobs: int


class PricePreloadRunRequest(BaseModel):
    batch_size: int = Field(25, ge=1, le=500)
    markets: Optional[list[str]] = None
    statuses: Optional[list[Literal["PENDING", "FAILED"]]] = None
    use_cache: bool = False
    force_refresh: bool = False
    sleep_ms: int = Field(100, ge=0, le=5000)


class PricePreloadRunItem(BaseModel):
    ticker: str
    name: str
    status: Literal["COMPLETED", "FAILED", "SKIPPED"]
    daily_records: int = 0
    weekly_records: int = 0
    error: Optional[str] = None


class PricePreloadRunResponse(BaseModel):
    requested: int
    processed: int
    completed: int
    failed: int
    skipped: int
    results: list[PricePreloadRunItem]


class PricePreloadFailure(BaseModel):
    ticker: str
    name: str
    attempts: int
    last_error: Optional[str] = None
    updated_at: Optional[datetime] = None


class PricePreloadStatusResponse(BaseModel):
    total_jobs: int
    status_counts: dict[str, int]
    recent_failures: list[PricePreloadFailure]
    is_running: bool = False
    max_attempts: int = 3
    last_started_at: Optional[datetime] = None
    last_finished_at: Optional[datetime] = None


class PricePreloadAutoSyncRequest(BaseModel):
    current_ticker: Optional[str] = None
    benchmark_ticker: Optional[str] = None
    sync_master: bool = True
    batch_size: int = Field(25, ge=1, le=500)
    sleep_ms: int = Field(100, ge=0, le=5000)
    universe_target_days: int = Field(730, ge=30, le=3650)
    major_target_days: int = Field(3650, ge=365, le=3650)
    major_limit: int = Field(200, ge=1, le=1000)


class PricePreloadAutoSyncResponse(BaseModel):
    started: bool
    already_running: bool = False
    message: str
    total_jobs: int
    major_ticker_count: int
    is_running: bool
    last_started_at: Optional[datetime] = None
