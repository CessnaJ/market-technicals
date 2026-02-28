from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List


class FinancialDataBase(BaseModel):
    stock_id: int
    period_type: str  # ANNUAL, QUARTER
    period_date: date
    revenue: Optional[Decimal] = None
    operating_income: Optional[Decimal] = None
    net_income: Optional[Decimal] = None
    total_assets: Optional[Decimal] = None
    total_equity: Optional[Decimal] = None
    shares_outstanding: Optional[int] = None
    market_cap: Optional[Decimal] = None
    psr: Optional[Decimal] = None
    per: Optional[Decimal] = None
    pbr: Optional[Decimal] = None
    roe: Optional[Decimal] = None
    debt_ratio: Optional[Decimal] = None


class FinancialDataCreate(FinancialDataBase):
    pass


class FinancialData(FinancialDataBase):
    id: int
    fetched_at: datetime

    class Config:
        from_attributes = True


class FinancialMetrics(BaseModel):
    """Financial metrics summary for dashboard"""
    ticker: str
    name: str
    psr: Optional[Decimal] = None
    per: Optional[Decimal] = None
    pbr: Optional[Decimal] = None
    roe: Optional[Decimal] = None
    debt_ratio: Optional[Decimal] = None
    market_cap: Optional[Decimal] = None
    revenue: Optional[Decimal] = None
    operating_income: Optional[Decimal] = None
    net_income: Optional[Decimal] = None
