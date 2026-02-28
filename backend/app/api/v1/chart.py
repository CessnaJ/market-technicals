from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from datetime import date, timedelta

from app.core.database import get_db
from app.models import Stock, OHLCDaily, OHLCWeekly
from app.schemas import ChartDataResponse, ChartDataPoint
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chart", tags=["chart"])


@router.get("/{ticker}", response_model=ChartDataResponse)
async def get_chart_data(
    ticker: str,
    timeframe: str = Query("daily", description="Timeframe: daily or weekly"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    scale: str = Query("linear", description="Scale: log or linear"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get chart data for a stock

    Returns OHLCV data with basic indicators
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

    # Get OHLCV data
    if timeframe == "weekly":
        result = await db.execute(
            select(OHLCWeekly)
            .where(OHLCWeekly.stock_id == stock.id)
            .order_by(OHLCWeekly.week_start.desc())
        )
        ohlcv_records = result.scalars().all()

        chart_data = [
            ChartDataPoint(
                date=record.week_start,
                open=record.open,
                high=record.high,
                low=record.low,
                close=record.close,
                volume=record.volume,
            )
            for record in ohlcv_records
        ]
    else:
        result = await db.execute(
            select(OHLCDaily)
            .where(OHLCDaily.stock_id == stock.id)
            .order_by(OHLCDaily.date.desc())
        )
        ohlcv_records = result.scalars().all()

        chart_data = [
            ChartDataPoint(
                date=record.date,
                open=record.open,
                high=record.high,
                low=record.low,
                close=record.close,
                volume=record.volume,
            )
            for record in ohlcv_records
        ]

    # Calculate basic indicators
    indicators = await _calculate_basic_indicators(chart_data)

    return ChartDataResponse(
        ticker=ticker,
        name=stock.name,
        timeframe=timeframe,
        scale=scale,
        ohlcv=chart_data,
        indicators=indicators,
    )


async def _calculate_basic_indicators(
    data: List[ChartDataPoint],
) -> dict:
    """
    Calculate basic technical indicators

    Returns SMA, EMA for common periods
    """
    if not data:
        return {}

    # Convert to DataFrame for calculations
    df = pd.DataFrame(
        [
            {
                "date": d.date,
                "open": d.open,
                "high": d.high,
                "low": d.low,
                "close": d.close,
                "volume": d.volume,
            }
            for d in data
        ]
    )
    df = df.sort_values("date").reset_index(drop=True)

    # Calculate SMAs
    periods = [5, 10, 20, 60, 120]
    sma_values = {}
    for period in periods:
        if len(df) >= period:
            sma_values[str(period)] = [
                {"date": df.iloc[i]["date"], "value": df.iloc[i]["close"]}
                for i in range(period, len(df))
            ]
        else:
            sma_values[str(period)] = []

    # Calculate EMAs (for MACD)
    df["ema_12"] = df["close"].ewm(span=12, adjust=False).mean()
    df["ema_26"] = df["close"].ewm(span=26, adjust=False).mean()

    # Calculate MACD
    df["macd"] = df["ema_12"] - df["ema_26"]
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_histogram"] = df["macd"] - df["macd_signal"]

    # Calculate RSI (14-period)
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    # Calculate Bollinger Bands (20-period, 2 std)
    df["bb_middle"] = df["close"].rolling(window=20).mean()
    bb_std = df["close"].rolling(window=20).std()
    df["bb_upper"] = df["bb_middle"] + (bb_std * 2)
    df["bb_lower"] = df["bb_middle"] - (bb_std * 2)

    indicators = {
        "sma": sma_values,
        "macd": [
            {
                "date": df.iloc[i]["date"],
                "macd": df.iloc[i]["macd"],
                "signal": df.iloc[i]["macd_signal"],
                "histogram": df.iloc[i]["macd_histogram"],
            }
            for i in range(26, len(df))
        ],
        "rsi": [
            {"date": df.iloc[i]["date"], "value": df.iloc[i]["rsi"]}
            for i in range(14, len(df))
        ],
        "bollinger": [
            {
                "date": df.iloc[i]["date"],
                "upper": df.iloc[i]["bb_upper"],
                "middle": df.iloc[i]["bb_middle"],
                "lower": df.iloc[i]["bb_lower"],
            }
            for i in range(20, len(df))
        ],
    }

    return indicators
