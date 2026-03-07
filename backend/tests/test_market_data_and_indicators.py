from datetime import date, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest

from app.api.v1.chart import _calculate_basic_indicators
from app.api.v1.indicators import get_fibonacci_levels, get_relative_strength, get_weinstein_indicator
from app.schemas import ChartDataPoint
from app.services.market_data_service import market_data_service


def _daily_points_for_months():
    return [
        ChartDataPoint(date=date(2025, 1, 2), open=100, high=110, low=95, close=108, volume=1000),
        ChartDataPoint(date=date(2025, 1, 31), open=109, high=120, low=104, close=118, volume=1500),
        ChartDataPoint(date=date(2025, 2, 3), open=117, high=125, low=115, close=123, volume=1200),
        ChartDataPoint(date=date(2025, 2, 28), open=124, high=130, low=119, close=127, volume=1700),
    ]


def _weekly_frame(start_close: float, close_step: float, count: int = 80):
    start = date(2024, 1, 1)
    rows = []
    for index in range(count):
        current_date = start + timedelta(days=index * 7)
        close = start_close + (close_step * index)
        rows.append(
            {
                "date": current_date,
                "open": close - 2,
                "high": close + 2,
                "low": close - 4,
                "close": close,
                "volume": 1000 + (index * 10),
            }
        )
    return pd.DataFrame(rows)


def _stock_stub(ticker: str, name: str):
    return SimpleNamespace(ticker=ticker, name=name)


def test_monthly_aggregation_builds_correct_ohlcv():
    """월봉 집계가 월별 OHLCV를 정확히 합산하는지 검증한다."""
    monthly = market_data_service.aggregate_points(_daily_points_for_months(), "monthly")

    print("\n[월봉 집계 테스트] 1월 OHLCV:", monthly[0])
    print("[월봉 집계 테스트] 2월 OHLCV:", monthly[1])

    assert len(monthly) == 2
    assert monthly[0].date == date(2025, 1, 1)
    assert monthly[0].open == 100
    assert monthly[0].high == 120
    assert monthly[0].low == 95
    assert monthly[0].close == 118
    assert monthly[0].volume == 2500
    assert monthly[1].date == date(2025, 2, 1)
    assert monthly[1].close == 127
    assert monthly[1].volume == 2900


@pytest.mark.asyncio
async def test_calculate_basic_indicators_respects_custom_sma_periods():
    """가변 SMA 요청 시 요청한 period만 반환하는지 검증한다."""
    data = [
        ChartDataPoint(
            date=date(2025, 1, 1) + timedelta(days=index),
            open=100 + index,
            high=101 + index,
            low=99 + index,
            close=100 + index,
            volume=1000 + index,
        )
        for index in range(20)
    ]

    indicators = await _calculate_basic_indicators(data, sma_periods=[3, 7])

    print("\n[가변 SMA 테스트] 반환 period:", list(indicators["sma"].keys()))
    assert sorted(indicators["sma"].keys()) == ["3", "7"]


@pytest.mark.asyncio
async def test_get_weinstein_indicator_returns_history_and_description(monkeypatch):
    """Weinstein 응답에 현재 stage, 설명, 히스토리 strip 데이터가 포함되는지 검증한다."""

    async def fake_load_price_frame(db, ticker, timeframe, min_daily_records=120):
        if ticker == "069500":
            return _stock_stub("069500", "KODEX 200"), _weekly_frame(90, 0.6)
        return _stock_stub("010950", "S-Oil"), _weekly_frame(100, 1.2)

    monkeypatch.setattr("app.api.v1.indicators._load_price_frame", fake_load_price_frame)

    response = await get_weinstein_indicator(ticker="010950", benchmark_ticker="069500", db=None)
    weinstein = response["weinstein"]

    print("\n[STAGE 히스토리 테스트] 현재 stage:", weinstein["current_stage"])
    print("[STAGE 히스토리 테스트] 설명 제목:", weinstein["description"]["title"])
    print("[STAGE 히스토리 테스트] 히스토리 길이:", len(weinstein["stage_history"]))

    assert weinstein["current_stage"] in {2, 3}
    assert weinstein["description"]["title"]
    assert len(weinstein["stage_history"]) > 10


@pytest.mark.asyncio
async def test_get_relative_strength_returns_benchmark_comparison_series(monkeypatch):
    """RS API가 벤치마크 비교 시계열과 Mansfield 값을 반환하는지 검증한다."""

    async def fake_load_price_frame(db, ticker, timeframe, min_daily_records=120):
        if ticker == "069500":
            return _stock_stub("069500", "KODEX 200"), _weekly_frame(90, 0.6)
        return _stock_stub("010950", "S-Oil"), _weekly_frame(100, 1.2)

    monkeypatch.setattr("app.api.v1.indicators._load_price_frame", fake_load_price_frame)

    response = await get_relative_strength(
        ticker="010950",
        benchmark_ticker="069500",
        timeframe="weekly",
        db=None,
    )
    rs = response["relative_strength"]

    print("\n[RS 테스트] 현재 spread:", rs["current_relative_return"])
    print("[RS 테스트] 현재 Mansfield:", rs["current_mansfield_rs"])
    print("[RS 테스트] 첫 시계열:", rs["series"][0])

    assert rs["series"][0]["stock_performance"] == pytest.approx(100.0)
    assert rs["current_relative_return"] > 0
    assert rs["current_mansfield_rs"] is not None


@pytest.mark.asyncio
async def test_get_fibonacci_levels_supports_manual_mode(monkeypatch):
    """수동 Fibonacci 모드에서 전달한 swing low/high 기준으로 레벨을 계산하는지 검증한다."""

    async def fake_load_price_frame(db, ticker, timeframe, min_daily_records=120):
        frame = pd.DataFrame(
            [
                {"date": date(2025, 1, 1), "open": 100, "high": 105, "low": 95, "close": 102, "volume": 1000},
                {"date": date(2025, 1, 2), "open": 102, "high": 108, "low": 99, "close": 106, "volume": 1200},
                {"date": date(2025, 1, 3), "open": 106, "high": 112, "low": 104, "close": 110, "volume": 1300},
            ]
            * 10
        )
        return _stock_stub(ticker, "S-Oil"), frame

    monkeypatch.setattr("app.api.v1.indicators._load_price_frame", fake_load_price_frame)

    response = await get_fibonacci_levels(
        ticker="010950",
        trend="UP",
        mode="manual",
        swing_low=100,
        swing_high=200,
        db=None,
    )
    fibonacci = response["fibonacci"]

    print("\n[수동 Fibonacci 테스트] 모드:", fibonacci["mode"])
    print("[수동 Fibonacci 테스트] 0.5 레벨:", fibonacci["levels"]["0.5"])

    assert fibonacci["mode"] == "manual"
    assert fibonacci["levels"]["0.5"] == pytest.approx(150.0)
