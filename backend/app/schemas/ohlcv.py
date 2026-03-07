from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List


class OHLCDailyBase(BaseModel):
    stock_id: int
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    adj_close: Optional[Decimal] = None


class OHLCDailyCreate(OHLCDailyBase):
    pass


class OHLCDaily(OHLCDailyBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class OHLCWeeklyBase(BaseModel):
    stock_id: int
    week_start: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class OHLCWeeklyCreate(OHLCWeeklyBase):
    pass


class OHLCWeekly(OHLCWeeklyBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ChartDataPoint(BaseModel):
    """Single data point for chart"""
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class ChartHistoryMetadata(BaseModel):
    """Metadata for the currently returned chart window"""
    oldest_date: Optional[date] = None
    newest_date: Optional[date] = None
    has_more_before: bool = False
    loaded_count: int = 0


class ChartDataResponse(BaseModel):
    """Chart data response with OHLCV and indicators"""
    ticker: str
    name: str
    timeframe: str
    scale: str
    ohlcv: List[ChartDataPoint]
    history: ChartHistoryMetadata
    indicators: Optional[dict] = None
