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
