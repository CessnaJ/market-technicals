from datetime import date, timedelta
from types import SimpleNamespace

from fastapi import BackgroundTasks
import pytest

from app.api.v1.chart import _parse_sma_periods, get_chart_data
from app.schemas import ChartDataPoint


def _weekly_points(count: int = 40):
    start = date(2024, 1, 1)
    return [
        ChartDataPoint(
            date=start + timedelta(days=index * 7),
            open=100 + index,
            high=105 + index,
            low=95 + index,
            close=102 + index,
            volume=1000 + index,
        )
        for index in range(count)
    ]


@pytest.mark.asyncio
async def test_get_chart_data_returns_history_metadata(monkeypatch):
    """차트 응답이 히스토리 메타와 함께 반환되는지 검증한다."""

    async def fake_ensure_stock_history(db, ticker, force_refresh=False, min_daily_records=120):
        return SimpleNamespace(id=1, ticker=ticker, name="S-Oil")

    async def fake_load_chart_points(
        db,
        stock_id,
        timeframe,
        start_date=None,
        end_date=None,
        before_date=None,
        limit=None,
    ):
        return _weekly_points()

    async def fake_has_points_before(db, stock_id, timeframe, before_date):
        return True

    monkeypatch.setattr(
        "app.api.v1.chart.market_data_service.ensure_stock_history",
        fake_ensure_stock_history,
    )
    monkeypatch.setattr(
        "app.api.v1.chart.market_data_service.load_chart_points",
        fake_load_chart_points,
    )
    monkeypatch.setattr(
        "app.api.v1.chart.market_data_service.has_points_before",
        fake_has_points_before,
    )

    response = await get_chart_data(
        ticker="010950",
        background_tasks=BackgroundTasks(),
        timeframe="weekly",
        db=None,
    )

    print("\n[차트 히스토리 메타 테스트] oldest:", response.history.oldest_date)
    print("[차트 히스토리 메타 테스트] newest:", response.history.newest_date)
    print("[차트 히스토리 메타 테스트] has_more_before:", response.history.has_more_before)

    assert response.history.oldest_date == response.ohlcv[0].date
    assert response.history.newest_date == response.ohlcv[-1].date
    assert response.history.loaded_count == len(response.ohlcv)
    assert response.history.has_more_before is True


@pytest.mark.asyncio
async def test_get_chart_data_before_date_can_return_empty_window(monkeypatch):
    """older fetch 요청이 빈 결과여도 404 대신 빈 payload로 응답하는지 검증한다."""

    async def fake_ensure_stock_history(db, ticker, force_refresh=False, min_daily_records=120):
        return SimpleNamespace(id=1, ticker=ticker, name="S-Oil")

    async def fake_load_chart_points(
        db,
        stock_id,
        timeframe,
        start_date=None,
        end_date=None,
        before_date=None,
        limit=None,
    ):
        return []

    async def fake_fetch_history_before(
        db,
        ticker,
        stock_id,
        timeframe,
        before_date,
        required_points,
    ):
        return False

    monkeypatch.setattr(
        "app.api.v1.chart.market_data_service.ensure_stock_history",
        fake_ensure_stock_history,
    )
    monkeypatch.setattr(
        "app.api.v1.chart.market_data_service.load_chart_points",
        fake_load_chart_points,
    )
    monkeypatch.setattr(
        "app.api.v1.chart.market_data_service.fetch_history_before",
        fake_fetch_history_before,
    )

    response = await get_chart_data(
        ticker="010950",
        background_tasks=BackgroundTasks(),
        timeframe="daily",
        before_date=date(2024, 1, 1),
        db=None,
    )

    print("\n[차트 older 빈 응답 테스트] loaded_count:", response.history.loaded_count)
    print("[차트 older 빈 응답 테스트] has_more_before:", response.history.has_more_before)

    assert response.ohlcv == []
    assert response.history.loaded_count == 0
    assert response.history.has_more_before is False


def test_parse_sma_periods_returns_sorted_unique_periods():
    """SMA period 파서는 중복 제거 후 오름차순 canonical order를 반환해야 한다."""
    parsed = _parse_sma_periods("120, 5, 20, 5, 10")

    print("\n[SMA 정렬 테스트] parsed:", parsed)
    assert parsed == [5, 10, 20, 120]
