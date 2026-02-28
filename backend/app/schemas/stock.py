from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


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
