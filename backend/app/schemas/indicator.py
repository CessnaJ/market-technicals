from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any


class IndicatorValue(BaseModel):
    """Single indicator value with date"""
    date: date
    value: Decimal


class IndicatorCacheCreate(BaseModel):
    stock_id: int
    indicator_name: str
    timeframe: str
    parameters: Dict[str, Any] = {}
    date: date
    value: Dict[str, Any]


class IndicatorCache(IndicatorCacheCreate):
    id: int
    computed_at: datetime

    class Config:
        from_attributes = True


# Weinstein Stage Analysis
class WeinsteinStage(BaseModel):
    ma_30w: Optional[Decimal] = None
    ma_slope: Optional[str] = None  # RISING, FALLING, FLAT
    stage: Optional[int] = None  # 1, 2, 3, 4
    stage_label: Optional[str] = None  # BASING, ADVANCING, TOPPING, DECLINING
    mansfield_rs: Optional[Decimal] = None


# VPCI
class VPCIValue(BaseModel):
    vpci: Decimal
    vpc: Decimal
    vpr: Decimal
    vm: Decimal
    signal: str  # CONFIRM_BULL, CONFIRM_BEAR, DIVERGE_BULL, DIVERGE_BEAR


# Darvas Box
class DarvasBox(BaseModel):
    start_date: date
    end_date: Optional[date] = None
    top: Decimal
    bottom: Decimal
    status: str  # FORMING, ACTIVE, BROKEN_UP, BROKEN_DOWN


# Fibonacci
class FibonacciLevels(BaseModel):
    swing_low: Decimal
    swing_high: Decimal
    levels: Dict[str, Decimal]


# Signal
class SignalCreate(BaseModel):
    stock_id: int
    signal_type: str
    signal_date: date
    direction: str  # BULLISH, BEARISH, WARNING
    strength: Optional[float] = None
    is_false_signal: Optional[bool] = None
    details: Optional[Dict[str, Any]] = None


class Signal(SignalCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class BreakoutChecklist(BaseModel):
    """Breakout confidence checklist"""
    weinstein_breakout: bool
    vpci_confirmed: bool
    volume_sufficient: bool
    mansfield_positive: bool
    darvas_breakout: bool
    confidence: float  # 0-1
    warnings: List[str] = []
