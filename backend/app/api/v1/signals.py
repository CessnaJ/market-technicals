from __future__ import annotations

from datetime import date
from decimal import Decimal
import logging
import math

from fastapi import APIRouter, Depends, Query
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.indicators.signal_detector import SignalDetector
from app.models import OHLCDaily, OHLCWeekly, Stock
from app.schemas import SignalDTO, SignalsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/signals", tags=["signals"])

detector = SignalDetector()


def _json_safe(value):
    if value is None or isinstance(value, (str, int, bool)):
        return value

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]

    if hasattr(value, "item") and callable(getattr(value, "item")):
        try:
            return _json_safe(value.item())
        except Exception:  # pragma: no cover - defensive fallback
            return str(value)

    return value


def _records_to_dataframe(records: list, date_field: str) -> pd.DataFrame:
    rows = [
        {
            "date": getattr(record, date_field),
            "open": float(record.open),
            "high": float(record.high),
            "low": float(record.low),
            "close": float(record.close),
            "volume": float(record.volume),
        }
        for record in records
    ]
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    return df.set_index("date", drop=False)


def _build_signals(df_daily: pd.DataFrame, df_weekly: pd.DataFrame, limit: int) -> list[SignalDTO]:
    if df_daily.empty or df_weekly.empty:
        return []

    signals: list[SignalDTO] = []

    if len(df_weekly) >= 30 and len(df_daily) >= 30:
        breakout_result = detector.analyze_breakout(
            df_daily=df_daily,
            df_weekly=df_weekly,
            breakout_date=df_daily.index[-1],
        )
        if breakout_result.get("signal_type") != "WEAK_SIGNAL":
            direction = "BULLISH"
            if breakout_result.get("signal_type") == "FALSE_BREAKOUT":
                direction = "WARNING"

            signals.append(
                SignalDTO(
                    signal_type=breakout_result["signal_type"],
                    signal_date=df_daily.index[-1].date()
                    if hasattr(df_daily.index[-1], "date")
                    else df_daily.index[-1],
                    direction=direction,
                    strength=float(breakout_result.get("confidence", 0.0)),
                    details={
                        "checklist": _json_safe(breakout_result.get("checklist", {})),
                        "warnings": _json_safe(breakout_result.get("warnings", [])),
                    },
                )
            )

    divergence_results = detector.detect_divergence(df_daily, df_weekly=df_weekly)
    for divergence in divergence_results:
        signal_date = divergence["date"].date() if hasattr(divergence["date"], "date") else divergence["date"]
        strength = divergence.get("strength")
        signals.append(
            SignalDTO(
                signal_type="DIVERGENCE",
                signal_date=signal_date,
                direction=divergence.get("type", "WARNING"),
                strength=float(strength) if strength is not None else None,
                details={
                    "weinstein_stage": _json_safe(divergence.get("weinstein_stage")),
                    "stage_label": _json_safe(divergence.get("stage_label")),
                    "significance": _json_safe(divergence.get("significance")),
                },
            )
        )

    signals.sort(key=lambda item: (item.signal_date, item.signal_type), reverse=True)
    return signals[:limit]


async def _get_computed_signals(
    ticker: str,
    limit: int,
    db: AsyncSession,
) -> SignalsResponse:
    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    stock = result.scalar_one_or_none()
    if stock is None:
        return SignalsResponse(signals=[])

    daily_result = await db.execute(
        select(OHLCDaily)
        .where(OHLCDaily.stock_id == stock.id)
        .order_by(OHLCDaily.date.desc())
        .limit(240)
    )
    daily_records = daily_result.scalars().all()

    weekly_result = await db.execute(
        select(OHLCWeekly)
        .where(OHLCWeekly.stock_id == stock.id)
        .order_by(OHLCWeekly.week_start.desc())
        .limit(120)
    )
    weekly_records = weekly_result.scalars().all()

    df_daily = _records_to_dataframe(daily_records, "date")
    df_weekly = _records_to_dataframe(weekly_records, "week_start")
    return SignalsResponse(signals=_build_signals(df_daily, df_weekly, limit))


@router.get("/{ticker}", response_model=SignalsResponse)
async def get_signals(
    ticker: str,
    limit: int = Query(10, description="Maximum number of computed signals"),
    db: AsyncSession = Depends(get_db),
):
    return await _get_computed_signals(ticker=ticker, limit=limit, db=db)


@router.get("/{ticker}/latest", response_model=SignalsResponse)
async def get_latest_signals(
    ticker: str,
    limit: int = Query(10, description="Maximum number of computed signals"),
    db: AsyncSession = Depends(get_db),
):
    return await _get_computed_signals(ticker=ticker, limit=limit, db=db)
