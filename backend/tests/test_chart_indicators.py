import pytest

from app.api.v1.chart import _calculate_basic_indicators
from app.schemas import ChartDataPoint


@pytest.mark.asyncio
async def test_calculate_basic_indicators_uses_real_sma_values():
    """차트 기본 지표 계산이 실제 SMA와 숫자형 응답을 반환하는지 검증한다."""
    data = [
        ChartDataPoint(
            date=f"2025-01-{index:02d}",
            open=float(index),
            high=float(index),
            low=float(index),
            close=float(index),
            volume=1000 + index,
        )
        for index in range(1, 31)
    ]

    indicators = await _calculate_basic_indicators(data)

    sma5 = indicators["sma"]["5"]
    print("\n[차트 지표 테스트] SMA(5) 첫 값:", sma5[0]["value"])
    print("[차트 지표 테스트] MACD 첫 value 타입:", type(indicators["macd"][0]["value"]).__name__)

    assert sma5[0]["value"] == pytest.approx(3.0)
    assert isinstance(indicators["macd"][0]["value"], float)
    assert isinstance(indicators["rsi"][0]["value"], float)
    assert isinstance(indicators["bollinger"][0]["value"], float)
