from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker, get_db
from app.models import Stock
from app.schemas import ChartDataPoint, ChartDataResponse, ChartHistoryMetadata
from app.services.market_data_service import market_data_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chart", tags=["chart"])

DEFAULT_SMA_PERIODS = [5, 10, 20, 60, 120]
TIMEFRAME_LIMITS = {
    "daily": 365,
    "weekly": 104,
    "monthly": 60,
}
OLDER_HISTORY_LIMITS = {
    "daily": 240,
    "weekly": 120,
    "monthly": 72,
}
MIN_POINTS_BY_TIMEFRAME = {
    "daily": 100,
    "weekly": 30,
    "monthly": 12,
}


def _parse_sma_periods(raw_value: Optional[str]) -> list[int]:
    if not raw_value:
        return DEFAULT_SMA_PERIODS

    parsed: list[int] = []
    for chunk in raw_value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            value = int(chunk)
        except ValueError:
            continue

        if 2 <= value <= 240 and value not in parsed:
            parsed.append(value)

    return sorted(parsed)[:6] or DEFAULT_SMA_PERIODS


async def background_fetch_full_history(ticker: str, stock_id: int):
    from app.services.data_service import data_service
    from app.services.kis_api.price import kis_price_service

    async with async_session_maker() as db:
        try:
            logger.info("🚀 [%s] 백그라운드 2년치 풀데이터 수집 시작...", ticker)
            full_data = await kis_price_service.get_daily_price(
                ticker,
                start_date=date.today() - timedelta(days=730),
                use_cache=False,
            )
            if full_data:
                await data_service.save_ohlcv_daily(db, stock_id, full_data)
                await data_service.convert_daily_to_weekly(db, stock_id)
                logger.info("✅ [%s] 백그라운드 데이터 수집 및 병합 완료!", ticker)
        except Exception as exc:
            logger.error("❌[%s] 백그라운드 수집 에러: %s", ticker, exc)


@router.get("/{ticker}", response_model=ChartDataResponse)
async def get_chart_data(
    ticker: str,
    background_tasks: BackgroundTasks,
    timeframe: str = Query("daily", description="Timeframe: daily, weekly or monthly"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    before_date: Optional[date] = Query(None, description="Load history strictly before this date"),
    limit: Optional[int] = Query(None, description="Maximum number of points to return"),
    scale: str = Query("linear", description="Scale: log or linear"),
    auto_fetch: bool = Query(True, description="Auto fetch data if not found"),
    force_refresh: bool = Query(False, description="Force refresh from KIS API"),
    sma_periods: Optional[str] = Query(None, description="Comma-separated SMA periods"),
    db: AsyncSession = Depends(get_db),
):
    from app.services.data_service import data_service
    from app.services.kis_api.price import kis_price_service

    if timeframe not in {"daily", "weekly", "monthly"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="timeframe must be one of: daily, weekly, monthly",
        )

    periods = _parse_sma_periods(sma_periods)
    requested_limit = limit or (
        OLDER_HISTORY_LIMITS[timeframe] if before_date else TIMEFRAME_LIMITS[timeframe]
    )

    if auto_fetch:
        stock = await market_data_service.ensure_stock_history(
            db,
            ticker,
            force_refresh=False,
            min_daily_records=MIN_POINTS_BY_TIMEFRAME["daily"],
        )
    else:
        result = await db.execute(select(Stock).where(Stock.ticker == ticker))
        stock = result.scalar_one_or_none()

    if stock is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {ticker} not found",
        )

    chart_data = await market_data_service.load_chart_points(
        db,
        stock.id,
        timeframe,
        start_date=start_date,
        end_date=end_date,
        before_date=before_date,
        limit=requested_limit,
    )

    needs_refresh = (
        before_date is None
        and (
            not chart_data
            or len(chart_data) < MIN_POINTS_BY_TIMEFRAME[timeframe]
            or force_refresh
        )
    )

    if needs_refresh and auto_fetch:
        logger.info("🐤 [%s] 데이터 부족 - 최근 데이터 선행 수집 및 백그라운드 보강", ticker)
        recent_data = await kis_price_service.get_daily_price(
            ticker=ticker,
            start_date=date.today() - timedelta(days=400),
            use_cache=not force_refresh,
        )

        if not recent_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Data fetch failed",
            )

        await data_service.save_ohlcv_daily(
            db,
            stock.id,
            recent_data,
            overwrite=force_refresh,
        )
        await data_service.convert_daily_to_weekly(db, stock.id)
        background_tasks.add_task(background_fetch_full_history, ticker, stock.id)
        chart_data = await market_data_service.load_chart_points(
            db,
            stock.id,
            timeframe,
            start_date=start_date,
            end_date=end_date,
            before_date=before_date,
            limit=requested_limit,
        )

    if before_date is not None and auto_fetch and len(chart_data) < requested_limit:
        await market_data_service.fetch_history_before(
            db,
            ticker,
            stock.id,
            timeframe,
            before_date=before_date,
            required_points=requested_limit,
        )
        chart_data = await market_data_service.load_chart_points(
            db,
            stock.id,
            timeframe,
            start_date=start_date,
            end_date=end_date,
            before_date=before_date,
            limit=requested_limit,
        )

    if not chart_data and before_date is not None:
        return ChartDataResponse(
            ticker=ticker,
            name=stock.name,
            timeframe=timeframe,
            scale=scale,
            ohlcv=[],
            history=ChartHistoryMetadata(
                oldest_date=None,
                newest_date=None,
                has_more_before=False,
                loaded_count=0,
            ),
            indicators={},
        )

    if not chart_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data for {ticker}",
        )

    indicators = await _calculate_basic_indicators(chart_data, sma_periods=periods)
    oldest_date = chart_data[0].date
    newest_date = chart_data[-1].date
    has_more_before = await market_data_service.has_points_before(
        db,
        stock.id,
        timeframe,
        oldest_date,
    )

    return ChartDataResponse(
        ticker=ticker,
        name=stock.name,
        timeframe=timeframe,
        scale=scale,
        ohlcv=chart_data,
        history=ChartHistoryMetadata(
            oldest_date=oldest_date,
            newest_date=newest_date,
            has_more_before=has_more_before,
            loaded_count=len(chart_data),
        ),
        indicators=indicators,
    )


async def _calculate_basic_indicators(
    data: list[ChartDataPoint],
    sma_periods: Optional[list[int]] = None,
) -> dict:
    if not data:
        return {}

    periods = sma_periods or DEFAULT_SMA_PERIODS

    df = pd.DataFrame(
        [
            {
                "date": item.date,
                "open": item.open,
                "high": item.high,
                "low": item.low,
                "close": item.close,
                "volume": item.volume,
            }
            for item in data
        ]
    ).sort_values("date").reset_index(drop=True)

    sma_values: dict[str, list[dict[str, float | date]]] = {}
    for period in periods:
        sma_series = df["close"].rolling(window=period).mean()
        sma_values[str(period)] = [
            {"date": df.iloc[index]["date"], "value": float(sma_series.iloc[index])}
            for index in range(len(df))
            if pd.notna(sma_series.iloc[index])
        ]

    df["ema_12"] = df["close"].ewm(span=12, adjust=False).mean()
    df["ema_26"] = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = df["ema_12"] - df["ema_26"]
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_histogram"] = df["macd"] - df["macd_signal"]

    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    df["bb_middle"] = df["close"].rolling(window=20).mean()
    bb_std = df["close"].rolling(window=20).std()
    df["bb_upper"] = df["bb_middle"] + (bb_std * 2)
    df["bb_lower"] = df["bb_middle"] - (bb_std * 2)

    df["vpc"] = (df["close"] * df["volume"]).rolling(window=14).sum() / df["volume"].rolling(window=14).sum()
    df["vpr"] = df["vpc"] / df["close"].rolling(window=14).mean()
    df["vm"] = df["volume"].rolling(window=14).mean()
    df["vpci"] = df["vpc"] * df["vpr"] / df["vm"]
    df["vpci_ma"] = df["vpci"].rolling(window=14).mean()

    def get_vpci_signal(row: pd.Series) -> str:
        vpci_value = row["vpci"]
        vpci_mean = row["vpci_ma"]
        if pd.isna(vpci_value):
            return "NEUTRAL"
        if vpci_value > 0:
            return "CONFIRM_BULL" if pd.isna(vpci_mean) or vpci_value >= vpci_mean else "DIVERGE_BULL"
        return "CONFIRM_BEAR" if pd.isna(vpci_mean) or vpci_value <= vpci_mean else "DIVERGE_BEAR"

    df["vpci_signal"] = df.apply(get_vpci_signal, axis=1)

    return {
        "sma": sma_values,
        "macd": [
            {
                "date": df.iloc[index]["date"],
                "value": float(df.iloc[index]["macd"]),
                "macd": float(df.iloc[index]["macd"]),
                "signal": float(df.iloc[index]["macd_signal"]),
                "histogram": float(df.iloc[index]["macd_histogram"]),
            }
            for index in range(len(df))
            if pd.notna(df.iloc[index]["macd_signal"])
        ],
        "rsi": [
            {"date": df.iloc[index]["date"], "value": float(df.iloc[index]["rsi"])}
            for index in range(len(df))
            if pd.notna(df.iloc[index]["rsi"])
        ],
        "bollinger": [
            {
                "date": df.iloc[index]["date"],
                "value": float(df.iloc[index]["bb_middle"]),
                "upper": float(df.iloc[index]["bb_upper"]),
                "middle": float(df.iloc[index]["bb_middle"]),
                "lower": float(df.iloc[index]["bb_lower"]),
            }
            for index in range(len(df))
            if pd.notna(df.iloc[index]["bb_middle"])
        ],
        "vpci": [
            {
                "date": df.iloc[index]["date"],
                "value": float(df.iloc[index]["vpci"]),
                "vpc": float(df.iloc[index]["vpc"]),
                "vpr": float(df.iloc[index]["vpr"]),
                "vm": float(df.iloc[index]["vm"]),
                "signal": str(df.iloc[index]["vpci_signal"]),
            }
            for index in range(len(df))
            if pd.notna(df.iloc[index]["vpci"])
        ],
    }
