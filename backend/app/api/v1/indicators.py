from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.indicators.custom.darvas_box import DarvasBox as DarvasBoxCalculator
from app.indicators.custom.fibonacci import FibonacciRetracement
from app.indicators.custom.weinstein import WeinsteinAnalysis
from app.services.market_data_service import market_data_service

router = APIRouter(prefix="/indicators", tags=["indicators"])

weinstein_analyzer = WeinsteinAnalysis()
darvas_calculator = DarvasBoxCalculator()
fibonacci_calculator = FibonacciRetracement()

DEFAULT_BENCHMARK_TICKER = "069500"
RS_PERIODS = {
    "daily": 252,
    "weekly": 52,
    "monthly": 12,
}


def _points_to_dataframe(points: list) -> pd.DataFrame:
    rows = [
        {
            "date": point.date,
            "open": float(point.open),
            "high": float(point.high),
            "low": float(point.low),
            "close": float(point.close),
            "volume": float(point.volume),
        }
        for point in points
    ]
    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def _build_stage_payload(
    df_weekly: pd.DataFrame,
    analysis: dict,
    mansfield_by_date: Optional[pd.Series] = None,
) -> dict:
    history: list[dict] = []
    transitions: list[dict] = []
    previous_stage: Optional[int] = None

    for index in range(len(df_weekly)):
        stage_value = analysis["stage"].iloc[index]
        if pd.isna(stage_value) or int(stage_value) == 0:
            continue

        stage_int = int(stage_value)
        date_value = df_weekly.iloc[index]["date"]
        mansfield_value = None
        if mansfield_by_date is not None and date_value in mansfield_by_date.index:
            raw_mansfield = mansfield_by_date.loc[date_value]
            if pd.notna(raw_mansfield):
                mansfield_value = float(raw_mansfield * 100)

        history.append(
            {
                "date": date_value,
                "stage": stage_int,
                "stage_label": analysis["stage_label"].iloc[index],
                "close": float(df_weekly.iloc[index]["close"]),
                "ma_30w": float(analysis["ma_30w"].iloc[index]) if pd.notna(analysis["ma_30w"].iloc[index]) else None,
                "slope": analysis["ma_slope"].iloc[index],
                "slope_pct": float(analysis["ma_slope_pct"].iloc[index]) if pd.notna(analysis["ma_slope_pct"].iloc[index]) else None,
                "distance_to_ma": float(analysis["distance_to_ma"].iloc[index]) if pd.notna(analysis["distance_to_ma"].iloc[index]) else None,
                "mansfield_rs": mansfield_value,
            }
        )

        if previous_stage is not None and previous_stage != stage_int:
            transitions.append(
                {
                    "date": date_value,
                    "from_stage": previous_stage,
                    "to_stage": stage_int,
                    "label": analysis["stage_label"].iloc[index],
                }
            )
        previous_stage = stage_int

    if not history:
        return {}

    current = history[-1]
    description = weinstein_analyzer.describe_stage(current["stage"])

    return {
        "current_stage": current["stage"],
        "stage_label": current["stage_label"],
        "ma_30w": current["ma_30w"],
        "mansfield_rs": current["mansfield_rs"],
        "description": description,
        "stage_history": history,
        "transitions": transitions[-12:],
    }


async def _load_price_frame(
    db: AsyncSession,
    ticker: str,
    timeframe: str,
    *,
    min_daily_records: int = 120,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> tuple[object, pd.DataFrame]:
    stock = await market_data_service.ensure_stock_history(
        db,
        ticker,
        min_daily_records=min_daily_records,
    )
    if stock is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {ticker} not found",
        )

    limit = None
    if start_date is None and end_date is None:
        limit = 160 if timeframe == "weekly" else 400
        if timeframe == "monthly":
            limit = 120

    points = await market_data_service.load_chart_points(
        db,
        stock.id,
        timeframe,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return stock, _points_to_dataframe(points)


@router.get("/{ticker}/weinstein")
async def get_weinstein_indicator(
    ticker: str,
    benchmark_ticker: Optional[str] = Query(DEFAULT_BENCHMARK_TICKER, description="Benchmark ticker for Mansfield RS"),
    start_date: Optional[date] = Query(None, description="Start date aligned to chart window"),
    end_date: Optional[date] = Query(None, description="End date aligned to chart window"),
    db: AsyncSession = Depends(get_db),
):
    stock, df_weekly = await _load_price_frame(
        db,
        ticker,
        "weekly",
        min_daily_records=260,
        start_date=start_date,
        end_date=end_date,
    )

    if df_weekly.empty or len(df_weekly) < 30:
        return {"weinstein": None}

    analysis = weinstein_analyzer.analyze(df_weekly)
    if not analysis:
        return {"weinstein": None}

    mansfield_by_date = None
    benchmark_name = None

    if benchmark_ticker:
        try:
            benchmark_stock, benchmark_weekly = await _load_price_frame(
                db,
                benchmark_ticker,
                "weekly",
                min_daily_records=260,
                start_date=start_date,
                end_date=end_date,
            )
            benchmark_name = benchmark_stock.name

            merged = pd.merge(
                df_weekly[["date", "close"]],
                benchmark_weekly[["date", "close"]],
                on="date",
                how="inner",
                suffixes=("_stock", "_benchmark"),
            )
            if len(merged) >= RS_PERIODS["weekly"]:
                mansfield_series = weinstein_analyzer.calc_mansfield_rs(
                    merged["close_stock"],
                    merged["close_benchmark"],
                )
                mansfield_by_date = pd.Series(mansfield_series.values, index=merged["date"])
        except HTTPException:
            benchmark_name = None

    payload = _build_stage_payload(df_weekly, analysis, mansfield_by_date)
    if not payload:
        return {"weinstein": None}

    payload.update(
        {
            "ticker": stock.ticker,
            "benchmark_ticker": benchmark_ticker,
            "benchmark_name": benchmark_name,
        }
    )
    return {"weinstein": payload}


@router.get("/{ticker}/darvas")
async def get_darvas_boxes(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    _, df_daily = await _load_price_frame(db, ticker, "daily", min_daily_records=120)

    if df_daily.empty or len(df_daily) < 5:
        return {"darvas_boxes": []}

    boxes = darvas_calculator.get_all_boxes(df_daily)

    darvas_boxes = []
    for box in boxes:
        start_date = box["start_date"]
        end_date = box["end_date"]
        top = box["top"]
        bottom = box["bottom"]

        if pd.notna(start_date) and hasattr(start_date, "isoformat"):
            start_date_str = start_date.isoformat()
        elif pd.notna(start_date):
            start_date_str = str(start_date)
        else:
            start_date_str = None

        if pd.notna(end_date) and hasattr(end_date, "isoformat"):
            end_date_str = end_date.isoformat()
        elif pd.notna(end_date):
            end_date_str = str(end_date)
        else:
            end_date_str = None

        darvas_boxes.append(
            {
                "start_date": start_date_str,
                "end_date": end_date_str,
                "top": float(top) if pd.notna(top) else None,
                "bottom": float(bottom) if pd.notna(bottom) else None,
                "status": box["status"],
            }
        )

    return {"darvas_boxes": darvas_boxes}


@router.get("/{ticker}/fibonacci")
async def get_fibonacci_levels(
    ticker: str,
    trend: str = Query("UP", description="Trend direction: UP or DOWN"),
    mode: str = Query("auto", description="Fibonacci mode: auto or manual"),
    swing_low: Optional[float] = Query(None, description="Manual swing low"),
    swing_high: Optional[float] = Query(None, description="Manual swing high"),
    db: AsyncSession = Depends(get_db),
):
    _, df_daily = await _load_price_frame(db, ticker, "daily", min_daily_records=120)

    if df_daily.empty or len(df_daily) < 20:
        return {"fibonacci": None}

    if mode == "manual":
        if swing_low is None or swing_high is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="swing_low and swing_high are required when mode=manual",
            )
        fib_result = fibonacci_calculator.calculate_levels(
            swing_low=swing_low,
            swing_high=swing_high,
            trend=trend,
        )
    else:
        fib_result = fibonacci_calculator.auto_detect(df_daily, trend=trend)

    if not fib_result:
        return {"fibonacci": None}

    return {
        "fibonacci": {
            "mode": mode,
            "trend": trend,
            "swing_low": float(fib_result.get("swing_low", 0)),
            "swing_high": float(fib_result.get("swing_high", 0)),
            "levels": {
                level_name: float(price)
                for level_name, price in fib_result.get("levels", {}).items()
            },
            "extensions": {
                level_name: float(price)
                for level_name, price in fib_result.get("extensions", {}).items()
            },
        }
    }


@router.get("/{ticker}/relative-strength")
async def get_relative_strength(
    ticker: str,
    benchmark_ticker: str = Query(DEFAULT_BENCHMARK_TICKER, description="Benchmark ticker"),
    timeframe: str = Query("weekly", description="daily, weekly or monthly"),
    start_date: Optional[date] = Query(None, description="Optional start date for aligned chart window"),
    end_date: Optional[date] = Query(None, description="Optional end date for aligned chart window"),
    db: AsyncSession = Depends(get_db),
):
    if timeframe not in {"daily", "weekly", "monthly"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="timeframe must be one of: daily, weekly, monthly",
        )

    min_daily_records = 320 if timeframe == "daily" else 260
    stock, stock_df = await _load_price_frame(
        db,
        ticker,
        timeframe,
        min_daily_records=min_daily_records,
        start_date=start_date,
        end_date=end_date,
    )
    benchmark_stock, benchmark_df = await _load_price_frame(
        db,
        benchmark_ticker,
        timeframe,
        min_daily_records=min_daily_records,
        start_date=start_date,
        end_date=end_date,
    )

    if stock_df.empty or benchmark_df.empty:
        return {"relative_strength": None}

    merged = pd.merge(
        stock_df[["date", "close"]],
        benchmark_df[["date", "close"]],
        on="date",
        how="inner",
        suffixes=("_stock", "_benchmark"),
    )

    if len(merged) < 2:
        return {"relative_strength": None}

    merged["stock_performance"] = merged["close_stock"] / merged["close_stock"].iloc[0] * 100
    merged["benchmark_performance"] = merged["close_benchmark"] / merged["close_benchmark"].iloc[0] * 100
    merged["relative_spread"] = merged["stock_performance"] - merged["benchmark_performance"]
    merged["relative_ratio"] = merged["close_stock"] / merged["close_benchmark"]
    merged["relative_ratio_index"] = merged["relative_ratio"] / merged["relative_ratio"].iloc[0] * 100

    lookback = RS_PERIODS[timeframe]
    if len(merged) >= lookback:
        merged["mansfield_rs"] = (
            (merged["close_stock"] / merged["close_stock"].shift(lookback)) - 1
        ) - (
            (merged["close_benchmark"] / merged["close_benchmark"].shift(lookback)) - 1
        )
        merged["mansfield_rs"] = merged["mansfield_rs"] * 100
    else:
        merged["mansfield_rs"] = None

    series = [
        {
            "date": row["date"],
            "stock_performance": float(row["stock_performance"]),
            "benchmark_performance": float(row["benchmark_performance"]),
            "relative_spread": float(row["relative_spread"]),
            "relative_ratio": float(row["relative_ratio_index"]),
            "mansfield_rs": float(row["mansfield_rs"]) if pd.notna(row["mansfield_rs"]) else None,
        }
        for _, row in merged.iterrows()
    ]

    return {
        "relative_strength": {
            "ticker": stock.ticker,
            "benchmark_ticker": benchmark_stock.ticker,
            "benchmark_name": benchmark_stock.name,
            "timeframe": timeframe,
            "current_relative_return": float(merged["relative_spread"].iloc[-1]),
            "current_mansfield_rs": float(merged["mansfield_rs"].iloc[-1]) if pd.notna(merged["mansfield_rs"].iloc[-1]) else None,
            "series": series,
        }
    }
