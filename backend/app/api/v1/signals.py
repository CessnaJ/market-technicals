from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional, List
from datetime import date, timedelta

from app.core.database import get_db
from app.models import Stock, Signal
from app.schemas import Signal as SignalSchema
from app.indicators.signal_detector import SignalDetector
import pandas as pd
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/signals", tags=["signals"])

detector = SignalDetector()


@router.get("/{ticker}")
async def get_signals(
    ticker: str,
    limit: int = Query(100, description="Number of recent signals"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get signal history for a stock

    Args:
        ticker: Stock ticker
        limit: Maximum number of signals to return

    Returns:
        List of signals
    """
    # Get stock
    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    stock = result.scalar_one_or_none()

    if not stock:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {ticker} not found",
        )

    # Get signals
    result = await db.execute(
        select(Signal)
        .where(Signal.stock_id == stock.id)
        .order_by(Signal.signal_date.desc())
        .limit(limit)
    )
    signals = result.scalars().all()

    return [
        {
            "id": s.id,
            "signal_type": s.signal_type,
            "signal_date": s.signal_date.isoformat(),
            "direction": s.direction,
            "strength": float(s.strength) if s.strength else None,
            "is_false_signal": s.is_false_signal,
            "details": s.details,
        }
        for s in signals
    ]


@router.get("/{ticker}/latest")
async def get_latest_signals(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get latest signals for a stock

    Returns the most recent signals of each type
    """
    # Get stock
    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    stock = result.scalar_one_or_none()

    if not stock:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {ticker} not found",
        )

    # Get OHLCV data for analysis
    from app.models import OHLCDaily, OHLCWeekly
    daily_result = await db.execute(
        select(OHLCDaily)
        .where(OHLCDaily.stock_id == stock.id)
        .order_by(OHLCDaily.date.desc())
        .limit(200)
    )
    daily_data = result.scalars().all()

    weekly_result = await db.execute(
        select(OHLCWeekly)
        .where(OHLCWeekly.stock_id == stock.id)
        .order_by(OHLCWeekly.week_start.desc())
        .limit(100)
    )
    weekly_data = result.scalars().all()

    if not daily_data or not weekly_data:
        return {"signals": []}

    # Convert to DataFrames
    df_daily = pd.DataFrame(
        [
            {
                "date": d.date,
                "open": d.open,
                "high": d.high,
                "low": d.low,
                "close": d.close,
                "volume": d.volume,
            }
            for d in daily_data
        ]
    )

    df_weekly = pd.DataFrame(
        [
            {
                "date": w.week_start,
                "open": w.open,
                "high": w.high,
                "low": w.low,
                "close": w.close,
                "volume": w.volume,
            }
            for w in weekly_data
        ]
    )

    # Analyze for signals
    signals = []

    # Check for latest breakout
    if len(df_weekly) >= 30:
        latest_date = df_weekly["date"].iloc[0]
        breakout_result = detector.analyze_breakout(
            df_daily, df_weekly, latest_date
        )
        if breakout_result.get("confidence", 0) > 0.5:
            signals.append({
                "signal_type": "BREAKOUT",
                "signal_date": latest_date.isoformat(),
                "direction": breakout_result.get("signal_type"),
                "strength": breakout_result.get("confidence"),
                "details": {
                    "checklist": breakout_result.get("checklist"),
                    "warnings": breakout_result.get("warnings"),
                },
            })

    # Check for divergences
    divergence_result = detector.detect_divergence(df_daily)
    for div in divergence_result:
        signals.append({
            "signal_type": "DIVERGENCE",
            "signal_date": div["date"].isoformat(),
            "direction": div["type"],
            "strength": div.get("strength"),
            "details": {
                "weinstein_stage": div.get("weinstein_stage"),
                "stage_label": div.get("stage_label"),
                "significance": div.get("significance"),
            },
        })

    # Sort by date descending
    signals.sort(key=lambda x: x["signal_date"], reverse=True)

    return {"signals": signals[:10]}  # Return top 10
