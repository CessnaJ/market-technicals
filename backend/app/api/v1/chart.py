from fastapi import APIRouter, Depends, Query, HTTPException, status, BackgroundTasks
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


# 백그라운드 태스크용 독립 세션 실행 함수 (중요: Request의 db 세션과 분리해야 함)
# ==========================================
# 1. 백그라운드 태스크 함수 (get_db 재활용) -> TODO: from app.core.database import async_session_maker  # 세션 팩토리가 있다고 가정 (경로에 맞게 수정 필요) 이거로 바꿔야되나?
# ==========================================
async def background_fetch_full_history(ticker: str, stock_id: int):
    from app.services.kis_api.price import kis_price_service
    from app.services.data_service import data_service
    from app.core.database import get_db

    # sessionmaker 이름 찾을 필요 없이 get_db()를 수동 순회하여 안전하게 세션 획득
    async for db in get_db():
        try:
            logger.info(f"🚀 [{ticker}] 백그라운드 1년치 풀데이터 수집 시작...")
            # 1년치 (365일) 요청
            full_data = await kis_price_service.get_daily_price(ticker, use_cache=False)
            if full_data:
                await data_service.save_ohlcv_daily(db, stock_id, full_data)
                await data_service.convert_daily_to_weekly(db, stock_id)
                logger.info(f"✅ [{ticker}] 백그라운드 데이터 수집 및 병합 완료!")
            break  # 세션 한 번만 쓰고 안전하게 종료
        except Exception as e:
            logger.error(f"❌[{ticker}] 백그라운드 수집 에러: {e}")
            break


# ==========================================
# 2. 차트 조회 엔드포인트
# ==========================================
@router.get("/{ticker}", response_model=ChartDataResponse)
async def get_chart_data(
        ticker: str,
        background_tasks: BackgroundTasks,  # 👈 백그라운드 주입
        timeframe: str = Query("daily", description="Timeframe: daily or weekly"),
        start_date: Optional[date] = Query(None, description="Start date"),
        end_date: Optional[date] = Query(None, description="End date"),
        scale: str = Query("linear", description="Scale: log or linear"),
        auto_fetch: bool = Query(True, description="Auto fetch data if not found"),
        force_refresh: bool = Query(False, description="Force refresh from KIS API"),
        db: AsyncSession = Depends(get_db),
):
    from app.services.kis_api.price import kis_price_service
    from app.services.data_service import data_service

    # 종목 조회
    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    stock = result.scalar_one_or_none()

    if not stock:
        if auto_fetch:
            current_price = await kis_price_service.get_current_price(ticker)
            if current_price:
                stock = await data_service.get_or_create_stock(
                    db,
                    ticker=ticker,
                    name=current_price.get("name", ticker),
                    market=current_price.get("market"),
                )
            else:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Stock {ticker} not found")
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Stock {ticker} not found")

    # DB에서 데이터 조회
    if timeframe == "weekly":
        result = await db.execute(
            select(OHLCWeekly).where(OHLCWeekly.stock_id == stock.id).order_by(OHLCWeekly.week_start.desc()).limit(365)
        )
        ohlcv_records = result.scalars().all()
        chart_data = [
            ChartDataPoint(
                date=record.week_start,
                open=float(record.open) if record.open else 0,
                high=float(record.high) if record.high else 0,
                low=float(record.low) if record.low else 0,
                close=float(record.close) if record.close else 0,
                volume=int(record.volume) if record.volume else 0,
            ) for record in ohlcv_records
        ]
    else:
        result = await db.execute(
            select(OHLCDaily).where(OHLCDaily.stock_id == stock.id).order_by(OHLCDaily.date.desc()).limit(365)
        )
        ohlcv_records = result.scalars().all()
        chart_data = [
            ChartDataPoint(
                date=record.date,
                open=float(record.open) if record.open else 0,
                high=float(record.high) if record.high else 0,
                low=float(record.low) if record.low else 0,
                close=float(record.close) if record.close else 0,
                volume=int(record.volume) if record.volume else 0,
            ) for record in ohlcv_records
        ]

    # ==========================================
    # 3. ★ 핵심: 지연 로딩 (Lazy Loading) 로직 ★
    # ==========================================
    # 데이터가 없거나, 100건 미만이거나, 강제 새로고침인 경우
    if (not chart_data or len(chart_data) < 100 or force_refresh) and auto_fetch:
        logger.info(f"🐤 [{ticker}] 데이터 부족 - 빠른 100일치 선행 수집 및 백그라운드 1년치 수집 트리거")

        # 1. 사용자가 덜 기다리게 최신 150일치(약 100거래일)만 빠르게 1번 API 호출
        quick_start_date = date.today() - timedelta(days=150)
        recent_data = await kis_price_service.get_daily_price(
            ticker, start_date=quick_start_date, use_cache=False
        )

        if recent_data:
            # 2. 가져온 100일치를 DB에 저장 (force_refresh 시 덮어쓰기)
            await data_service.save_ohlcv_daily(db, stock.id, recent_data, overwrite=force_refresh)
            if timeframe == "weekly":
                await data_service.convert_daily_to_weekly(db, stock.id)

            # 3. ★ 나머지 1년치는 백그라운드로 던져놓고 (여기서 대기 안함) ★
            background_tasks.add_task(background_fetch_full_history, ticker, stock.id)

            # 4. 방금 가져온 100일치만으로 즉시 응답 데이터 구성
            chart_data = [
                ChartDataPoint(
                    date=date.fromisoformat(r["date"]),
                    open=r["open"], high=r["high"], low=r["low"], close=r["close"], volume=r["volume"]
                ) for r in recent_data
            ]
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data fetch failed")

    if not chart_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No data for {ticker}")

    # ==========================================
    # 4. 보조지표 계산 및 리턴
    # ==========================================
    chart_data.sort(key=lambda x: x.date)  # 지표 계산을 위해 과거순 정렬 필수
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
                {"date": df.iloc[i]["date"], "value": float(df.iloc[i]["close"])}
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

    # Calculate VPCI (Volume Price Confirmation Indicator)
    # VPC (Volume Price Confirmation) - SMA of close weighted by volume
    df["vpc"] = (df["close"] * df["volume"]).rolling(window=14).sum() / df["volume"].rolling(window=14).sum()
    # VPR (Volume Price Ratio) - VPC / SMA
    df["vpr"] = df["vpc"] / df["close"].rolling(window=14).mean()
    # VM (Volume Moving Average)
    df["vm"] = df["volume"].rolling(window=14).mean()
    # VPCI = VPC * VPR / VM
    df["vpci"] = df["vpc"] * df["vpr"] / df["vm"]

    # Determine VPCI signal
    def get_vpci_signal(vpci: float) -> str:
        if pd.isna(vpci):
            return "NEUTRAL"
        if vpci > 0:
            if vpci > df["vpci"].rolling(window=14).mean().iloc[-1]:
                return "CONFIRM_BULL"
            else:
                return "DIVERGE_BULL"
        else:
            if vpci < df["vpci"].rolling(window=14).mean().iloc[-1]:
                return "CONFIRM_BEAR"
            else:
                return "DIVERGE_BEAR"

    df["vpci_signal"] = df["vpci"].apply(get_vpci_signal)

    indicators = {
        "sma": sma_values,
        "macd": [
            {
                "date": df.iloc[i]["date"],
                "value": float(df.iloc[i]["macd"]),
                "macd": float(df.iloc[i]["macd"]),
                "signal": float(df.iloc[i]["macd_signal"]),
                "histogram": float(df.iloc[i]["macd_histogram"]),
            }
            for i in range(26, len(df))
        ],
        "rsi": [
            {"date": df.iloc[i]["date"], "value": float(df.iloc[i]["rsi"])}
            for i in range(14, len(df))
        ],
        "bollinger": [
            {
                "date": df.iloc[i]["date"],
                "value": float(df.iloc[i]["bb_middle"]),
                "upper": float(df.iloc[i]["bb_upper"]),
                "middle": float(df.iloc[i]["bb_middle"]),
                "lower": float(df.iloc[i]["bb_lower"]),
            }
            for i in range(20, len(df))
        ],
        "vpci": [
            {
                "date": df.iloc[i]["date"],
                "value": float(df.iloc[i]["vpci"]) if pd.notna(df.iloc[i]["vpci"]) else None,
                "vpc": float(df.iloc[i]["vpc"]) if pd.notna(df.iloc[i]["vpc"]) else None,
                "vpr": float(df.iloc[i]["vpr"]) if pd.notna(df.iloc[i]["vpr"]) else None,
                "vm": float(df.iloc[i]["vm"]) if pd.notna(df.iloc[i]["vm"]) else None,
                "signal": str(df.iloc[i]["vpci_signal"]) if pd.notna(df.iloc[i]["vpci_signal"]) else None,
            }
            for i in range(14, len(df))
        ],
    }

    return indicators
