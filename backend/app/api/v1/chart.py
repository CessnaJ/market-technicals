from datetime import date, timedelta
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker, get_db
from app.models import OHLCDaily, OHLCWeekly, Stock
from app.schemas import ChartDataPoint, ChartDataResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chart", tags=["chart"])


async def background_fetch_full_history(ticker: str, stock_id: int):
    from app.services.data_service import data_service
    from app.services.kis_api.price import kis_price_service

    async with async_session_maker() as db:
        try:
            logger.info("🚀 [%s] 백그라운드 1년치 풀데이터 수집 시작...", ticker)
            full_data = await kis_price_service.get_daily_price(ticker, use_cache=False)
            if full_data:
                await data_service.save_ohlcv_daily(db, stock_id, full_data)
                await data_service.convert_daily_to_weekly(db, stock_id)
                logger.info("✅ [%s] 백그라운드 데이터 수집 및 병합 완료!", ticker)
        except Exception as exc:
            logger.error("❌[%s] 백그라운드 수집 에러: %s", ticker, exc)


async def _load_chart_data(
    db: AsyncSession,
    stock_id: int,
    timeframe: str,
    start_date: Optional[date],
    end_date: Optional[date],
) -> list[ChartDataPoint]:
    if timeframe == "weekly":
        query = (
            select(OHLCWeekly)
            .where(OHLCWeekly.stock_id == stock_id)
            .order_by(OHLCWeekly.week_start.desc())
        )
        if start_date:
            query = query.where(OHLCWeekly.week_start >= start_date)
        if end_date:
            query = query.where(OHLCWeekly.week_start <= end_date)
        query = query.limit(365)
        result = await db.execute(query)
        records = result.scalars().all()
        return [
            ChartDataPoint(
                date=record.week_start,
                open=float(record.open),
                high=float(record.high),
                low=float(record.low),
                close=float(record.close),
                volume=int(record.volume),
            )
            for record in records
        ]

    query = (
        select(OHLCDaily)
        .where(OHLCDaily.stock_id == stock_id)
        .order_by(OHLCDaily.date.desc())
    )
    if start_date:
        query = query.where(OHLCDaily.date >= start_date)
    if end_date:
        query = query.where(OHLCDaily.date <= end_date)
    query = query.limit(365)
    result = await db.execute(query)
    records = result.scalars().all()
    return [
        ChartDataPoint(
            date=record.date,
            open=float(record.open),
            high=float(record.high),
            low=float(record.low),
            close=float(record.close),
            volume=int(record.volume),
        )
        for record in records
    ]


@router.get("/{ticker}", response_model=ChartDataResponse)
async def get_chart_data(
    ticker: str,
    background_tasks: BackgroundTasks,
    timeframe: str = Query("daily", description="Timeframe: daily or weekly"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    scale: str = Query("linear", description="Scale: log or linear"),
    auto_fetch: bool = Query(True, description="Auto fetch data if not found"),
    force_refresh: bool = Query(False, description="Force refresh from KIS API"),
    db: AsyncSession = Depends(get_db),
):
    from app.services.data_service import data_service
    from app.services.kis_api.price import kis_price_service

    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    stock = result.scalar_one_or_none()

    if not stock:
        if not auto_fetch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stock {ticker} not found",
            )

        current_price = await kis_price_service.get_current_price(ticker)
        if not current_price:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stock {ticker} not found",
            )

        stock = await data_service.get_or_create_stock(
            db,
            ticker=ticker,
            name=current_price.get("name", ticker),
            market=current_price.get("market"),
        )

    chart_data = await _load_chart_data(db, stock.id, timeframe, start_date, end_date)

    if (not chart_data or len(chart_data) < 100 or force_refresh) and auto_fetch:
        logger.info("🐤 [%s] 데이터 부족 - 최근 데이터 선행 수집 및 백그라운드 1년치 수집", ticker)
        quick_start_date = date.today() - timedelta(days=150)
        recent_data = await kis_price_service.get_daily_price(
            ticker=ticker,
            start_date=quick_start_date,
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
        chart_data = await _load_chart_data(db, stock.id, timeframe, start_date, end_date)

    if not chart_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data for {ticker}",
        )

    chart_data.sort(key=lambda item: item.date)
    indicators = await _calculate_basic_indicators(chart_data)

    return ChartDataResponse(
        ticker=ticker,
        name=stock.name,
        timeframe=timeframe,
        scale=scale,
        ohlcv=chart_data,
        indicators=indicators,
    )


async def _calculate_basic_indicators(data: list[ChartDataPoint]) -> dict:
    if not data:
        return {}

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

    periods = [5, 10, 20, 60, 120]
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
