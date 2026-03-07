from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.api.v1.signals import get_signals


class FakeScalars:
    """SQLAlchemy scalars().all() 대체용 테스트 헬퍼."""

    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class FakeResult:
    """SQLAlchemy execute 결과 대체용 테스트 헬퍼."""

    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        values = self._value if isinstance(self._value, list) else [self._value]
        return FakeScalars(values)


class FakeDB:
    """순차 execute 응답을 반환하는 테스트용 DB."""

    def __init__(self, results):
        self._results = list(results)

    async def execute(self, stmt):
        return self._results.pop(0)


def _daily_rows(count: int):
    start = date(2024, 1, 1)
    rows = []
    for index in range(count):
        current = start + timedelta(days=index)
        rows.append(
            SimpleNamespace(
                date=current,
                open=100 + index,
                high=110 + index,
                low=90 + index,
                close=105 + index,
                volume=1000 + index,
            )
        )
    return rows


def _weekly_rows(count: int):
    start = date(2024, 1, 1)
    rows = []
    for index in range(count):
        current = start + timedelta(days=index * 7)
        rows.append(
            SimpleNamespace(
                week_start=current,
                open=100 + index,
                high=120 + index,
                low=95 + index,
                close=118 + index,
                volume=5000 + index,
            )
        )
    return rows


@pytest.mark.asyncio
async def test_get_signals_returns_empty_when_data_is_insufficient():
    """신호 계산에 필요한 데이터가 부족하면 빈 배열을 반환하는지 검증한다."""
    db = FakeDB(
        [
            FakeResult(SimpleNamespace(id=1, ticker="000660")),
            FakeResult([]),
            FakeResult([]),
        ]
    )

    response = await get_signals(ticker="000660", limit=10, db=db)

    print("\n[시그널 테스트 - 데이터 부족] 반환 개수:", len(response.signals))
    assert response.signals == []


@pytest.mark.asyncio
async def test_get_signals_returns_computed_signal_payload(monkeypatch):
    """충분한 데이터가 있을 때 계산형 시그널 payload를 반환하는지 검증한다."""
    db = FakeDB(
        [
            FakeResult(SimpleNamespace(id=1, ticker="000660")),
            FakeResult(_daily_rows(80)),
            FakeResult(_weekly_rows(40)),
        ]
    )

    monkeypatch.setattr(
        "app.api.v1.signals.detector.analyze_breakout",
        lambda **kwargs: {
            "signal_type": "TRUE_BREAKOUT",
            "confidence": 0.8,
            "checklist": {"weinstein_breakout": True},
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        "app.api.v1.signals.detector.detect_divergence",
        lambda *args, **kwargs: [
            {
                "date": date(2025, 1, 31),
                "type": "BEARISH",
                "strength": 0.4,
                "weinstein_stage": 2,
                "stage_label": "ADVANCING",
                "significance": "WARNING",
            }
        ],
    )

    response = await get_signals(ticker="000660", limit=10, db=db)

    print("\n[시그널 테스트 - 계산형 응답] 반환 payload:", response.signals)
    assert response.signals[0].signal_type in {"TRUE_BREAKOUT", "DIVERGENCE"}
    assert all(signal.signal_date for signal in response.signals)
