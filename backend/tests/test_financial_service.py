from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.services.financial_service import financial_service


@pytest.mark.asyncio
async def test_fetch_financial_ratio_rows_derives_metrics(monkeypatch):
    """KIS 재무비율 응답으로부터 PER/PBR/PSR/ROE/부채비율을 파생하는지 검증한다."""
    monkeypatch.setattr(
        "app.services.financial_service.kis_client.get",
        AsyncMock(
            return_value={
                "output": [
                    {
                        "stac_yymm": "202412",
                        "roe_val": "12.5",
                        "eps": "10000",
                        "bps": "50000",
                        "sps": "200000",
                        "lblt_rate": "85.2",
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        "app.services.financial_service.kis_price_service.get_current_price",
        AsyncMock(return_value={"current_price": 100000}),
    )

    rows = await financial_service._fetch_financial_ratio_rows("000660")

    print("\n[재무 서비스 테스트] 파생 결과:", rows[0])
    assert len(rows) == 1
    assert rows[0]["period_date"] == date(2024, 12, 31)
    assert float(rows[0]["per"]) == pytest.approx(10.0)
    assert float(rows[0]["pbr"]) == pytest.approx(2.0)
    assert float(rows[0]["psr"]) == pytest.approx(0.5)
    assert float(rows[0]["roe"]) == pytest.approx(12.5)
    assert float(rows[0]["debt_ratio"]) == pytest.approx(85.2)
