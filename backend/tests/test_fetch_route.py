from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1.fetch import FetchStockRequest, fetch_stock_data


@pytest.mark.asyncio
async def test_fetch_stock_data_uses_body_force_refresh(monkeypatch):
    """fetch API가 body의 force_refresh 값을 사용해 캐시 우회를 수행하는지 검증한다."""
    current_price = {
        "name": "SK Hynix",
        "market": "KOSPI",
        "current_price": 180000,
    }
    ohlcv_data = [
        {"date": "2025-01-06", "open": 100.0, "high": 110.0, "low": 90.0, "close": 105.0, "volume": 1000}
    ]

    monkeypatch.setattr(
        "app.api.v1.fetch.kis_price_service.get_current_price",
        AsyncMock(return_value=current_price),
    )
    get_daily_price = AsyncMock(return_value=ohlcv_data)
    monkeypatch.setattr("app.api.v1.fetch.kis_price_service.get_daily_price", get_daily_price)
    monkeypatch.setattr(
        "app.api.v1.fetch.data_service.get_or_create_stock",
        AsyncMock(return_value=SimpleNamespace(id=1)),
    )
    monkeypatch.setattr(
        "app.api.v1.fetch.data_service.save_ohlcv_daily",
        AsyncMock(return_value=1),
    )
    convert_daily_to_weekly = AsyncMock(return_value=1)
    monkeypatch.setattr(
        "app.api.v1.fetch.data_service.convert_daily_to_weekly",
        convert_daily_to_weekly,
    )
    monkeypatch.setattr(
        "app.api.v1.fetch.redis_client.delete_pattern",
        AsyncMock(return_value=1),
    )

    response = await fetch_stock_data(
        ticker="000660",
        payload=FetchStockRequest(force_refresh=True),
        db=object(),
    )

    print("\n[fetch API 테스트] 응답:", response)
    get_daily_price.assert_awaited_once_with(ticker="000660", use_cache=False)
    convert_daily_to_weekly.assert_awaited_once()
    assert response["weekly_records"] == 1
