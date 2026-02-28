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
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class ChartDataResponse(BaseModel):
    """Chart data response with OHLCV and indicators"""
    ticker: str
    name: str
    timeframe: str
    scale: str
    ohlcv: List[ChartDataPoint]
    indicators: Optional[dict] = None
    weinstein: Optional[dict] = None
    darvas_boxes: Optional[List[dict]] = None
    signals: Optional[List[dict]] = None
