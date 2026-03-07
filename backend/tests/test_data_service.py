from datetime import date
from types import SimpleNamespace

import pytest

from app.services.data_service import data_service


class DummyDB:
    """DB 없이 주봉 재계산 결과를 관찰하기 위한 최소 더미 객체."""

    def __init__(self):
        self.added = []
        self.commits = 0

    async def execute(self, stmt):
        return None

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_convert_daily_to_weekly_uses_oldest_open_and_latest_close(monkeypatch):
    """주봉 생성 시 시가/종가/고가/저가/거래량 집계가 올바른지 검증한다."""
    db = DummyDB()
    captured = {}
    daily_rows = [
        SimpleNamespace(date=date, open=open_, high=high, low=low, close=close, volume=volume)
        for date, open_, high, low, close, volume in [
            (date(2025, 1, 8), 110, 120, 105, 118, 300),
            (date(2025, 1, 7), 105, 111, 100, 109, 200),
            (date(2025, 1, 6), 100, 108, 99, 104, 100),
        ]
    ]

    async def fake_get_daily(*args, **kwargs):
        captured["limit"] = kwargs.get("limit")
        return daily_rows

    monkeypatch.setattr(data_service, "get_ohlcv_daily", fake_get_daily)

    weekly_count = await data_service.convert_daily_to_weekly(db, stock_id=1)

    assert weekly_count == 1
    weekly = db.added[0]
    print("\n[주봉 변환 테스트] 생성 건수:", weekly_count)
    print("[주봉 변환 테스트] get_ohlcv_daily limit:", captured.get("limit"))
    print(
        "[주봉 변환 테스트] open/high/low/close/volume =",
        float(weekly.open),
        float(weekly.high),
        float(weekly.low),
        float(weekly.close),
        int(weekly.volume),
    )
    assert float(weekly.open) == 100
    assert float(weekly.close) == 118
    assert float(weekly.high) == 120
    assert float(weekly.low) == 99
    assert int(weekly.volume) == 600
    assert captured.get("limit") is None
