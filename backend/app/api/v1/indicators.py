from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from datetime import date

from app.core.database import get_db
from app.models import Stock, OHLCDaily, OHLCWeekly
from app.indicators.custom.weinstein import WeinsteinAnalysis
from app.indicators.custom.darvas_box import DarvasBox as DarvasBoxCalculator
from app.indicators.custom.fibonacci import FibonacciRetracement
import pandas as pd
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/indicators", tags=["indicators"])

# Initialize indicator calculators
weinstein_analyzer = WeinsteinAnalysis()
darvas_calculator = DarvasBoxCalculator()
fibonacci_calculator = FibonacciRetracement()


@router.get("/{ticker}/weinstein")
async def get_weinstein_indicator(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get Weinstein Stage Analysis for a stock

    Returns:
        Dictionary with weinstein analysis data
    """
    from fastapi import HTTPException, status

    # Get stock
    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    stock = result.scalar_one_or_none()

    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {ticker} not found",
        )

    # Get weekly OHLCV data (Weinstein uses 30-week MA)
    result = await db.execute(
        select(OHLCWeekly)
        .where(OHLCWeekly.stock_id == stock.id)
        .order_by(OHLCWeekly.week_start.desc())
        .limit(100)
    )
    weekly_records = result.scalars().all()

    if not weekly_records or len(weekly_records) < 30:
        # Return null if insufficient data
        return {"weinstein": None}

    # Convert to DataFrame with float values
    df = pd.DataFrame(
        [
            {
                "date": w.week_start,
                "open": float(w.open) if w.open else 0.0,
                "high": float(w.high) if w.high else 0.0,
                "low": float(w.low) if w.low else 0.0,
                "close": float(w.close) if w.close else 0.0,
                "volume": float(w.volume) if w.volume else 0.0,
            }
            for w in weekly_records
        ]
    )

    # Sort by date ascending for analysis
    df = df.sort_values("date").reset_index(drop=True)

    # Analyze
    analysis = weinstein_analyzer.analyze(df)

    if not analysis:
        return {"weinstein": None}

    # Get latest values
    latest_ma_30w = analysis.get("ma_30w").iloc[-1] if analysis.get("ma_30w") is not None else None
    latest_stage = analysis.get("stage").iloc[-1] if analysis.get("stage") is not None else None
    latest_slope = analysis.get("ma_slope").iloc[-1] if analysis.get("ma_slope") is not None else None

    # Get stage label
    stage_label = None
    if latest_stage is not None:
        stage_labels = {
            1: "BASING",
            2: "ADVANCING",
            3: "TOPPING",
            4: "DECLINING",
        }
        stage_label = stage_labels.get(latest_stage, "UNKNOWN")

    return {
        "weinstein": {
            "current_stage": int(latest_stage) if latest_stage is not None else None,
            "stage_label": stage_label,
            "ma_30w": float(latest_ma_30w) if latest_ma_30w is not None else None,
            "mansfield_rs": None,  # Requires benchmark data
        }
    }


@router.get("/{ticker}/darvas")
async def get_darvas_boxes(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get Darvas Boxes for a stock

    Returns:
        Dictionary with darvas boxes data
    """
    from fastapi import HTTPException, status

    # Get stock
    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    stock = result.scalar_one_or_none()

    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {ticker} not found",
        )

    # Get daily OHLCV data (Darvas uses daily data)
    result = await db.execute(
        select(OHLCDaily)
        .where(OHLCDaily.stock_id == stock.id)
        .order_by(OHLCDaily.date.desc())
        .limit(200)
    )
    daily_records = result.scalars().all()

    if not daily_records or len(daily_records) < 5:
        return {"darvas_boxes": []}

    # Convert to DataFrame with float values
    df = pd.DataFrame(
        [
            {
                "date": d.date,
                "open": float(d.open) if d.open else 0.0,
                "high": float(d.high) if d.high else 0.0,
                "low": float(d.low) if d.low else 0.0,
                "close": float(d.close) if d.close else 0.0,
                "volume": float(d.volume) if d.volume else 0.0,
            }
            for d in daily_records
        ]
    )

    # Sort by date ascending for analysis
    df = df.sort_values("date").reset_index(drop=True)

    # Calculate Darvas boxes
    boxes = darvas_calculator.get_all_boxes(df)

    # Convert to expected format
    darvas_boxes = []
    for box in boxes:
        # Convert pandas Timestamp to datetime string
        start_date = box["start_date"]
        end_date = box["end_date"]
        top = box["top"]
        bottom = box["bottom"]
        
        # Handle pandas Timestamp conversion
        if pd.notna(start_date) and hasattr(start_date, 'isoformat'):
            start_date_str = start_date.isoformat()
        elif pd.notna(start_date):
            start_date_str = str(start_date)
        else:
            start_date_str = None
            
        if pd.notna(end_date) and hasattr(end_date, 'isoformat'):
            end_date_str = end_date.isoformat()
        elif pd.notna(end_date):
            end_date_str = str(end_date)
        else:
            end_date_str = None
        
        # Handle NaN values for JSON serialization
        top_val = float(top) if pd.notna(top) else None
        bottom_val = float(bottom) if pd.notna(bottom) else None
        
        darvas_boxes.append({
            "start_date": start_date_str,
            "end_date": end_date_str,
            "top": top_val,
            "bottom": bottom_val,
            "status": box["status"],
        })

    return {"darvas_boxes": darvas_boxes}


@router.get("/{ticker}/fibonacci")
async def get_fibonacci_levels(
    ticker: str,
    trend: str = Query("UP", description="Trend direction: UP or DOWN"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get Fibonacci Retracement Levels for a stock

    Returns:
        Dictionary with fibonacci levels data
    """
    from fastapi import HTTPException, status

    # Get stock
    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    stock = result.scalar_one_or_none()

    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {ticker} not found",
        )

    # Get daily OHLCV data
    result = await db.execute(
        select(OHLCDaily)
        .where(OHLCDaily.stock_id == stock.id)
        .order_by(OHLCDaily.date.desc())
        .limit(120)
    )
    daily_records = result.scalars().all()

    if not daily_records or len(daily_records) < 20:
        return {"fibonacci": None}

    # Convert to DataFrame with float values
    df = pd.DataFrame(
        [
            {
                "date": d.date,
                "open": float(d.open) if d.open else 0.0,
                "high": float(d.high) if d.high else 0.0,
                "low": float(d.low) if d.low else 0.0,
                "close": float(d.close) if d.close else 0.0,
                "volume": float(d.volume) if d.volume else 0.0,
            }
            for d in daily_records
        ]
    )

    # Sort by date ascending for analysis
    df = df.sort_values("date").reset_index(drop=True)

    # Auto-detect swing high/low and calculate levels
    fib_result = fibonacci_calculator.auto_detect(df, trend=trend)

    if not fib_result:
        return {"fibonacci": None}

    # Convert levels to expected format
    levels = {}
    for level_name, price in fib_result.get("levels", {}).items():
        try:
            levels[level_name] = float(price)
        except (TypeError, ValueError):
            continue

    return {
        "fibonacci": {
            "swing_low": float(fib_result.get("swing_low", 0)),
            "swing_high": float(fib_result.get("swing_high", 0)),
            "levels": levels,
        }
    }
