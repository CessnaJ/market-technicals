from datetime import date, timedelta
from types import SimpleNamespace

import pandas as pd

from app.schemas.screener import ScreeningScanRequest
from app.services.screener_service import screener_service


def _build_weekly_candidate_frame():
    rows = []
    start = date(2024, 1, 1)
    close = 100.0

    for index in range(70):
        if index < 42:
            close -= 0.25
        elif index < 54:
            close += 0.10
        else:
            close += 1.55

        rows.append(
            {
                "date": start + timedelta(days=index * 7),
                "open": close - 1.0,
                "high": close + 1.8,
                "low": close - 1.8,
                "close": close,
                "volume": 1000 + (index * 8 if index < 54 else 520 + index * 25),
            }
        )

    return pd.DataFrame(rows)


def _build_daily_candidate_frame():
    rows = []
    start = date(2025, 1, 1)
    close = 100.0

    for index in range(90):
        close += 0.15 if index < 45 else 0.45
        rows.append(
            {
                "date": start + timedelta(days=index),
                "open": close - 0.3,
                "high": close + 0.8,
                "low": close - 0.7,
                "close": close,
                "volume": 100_000 + index * 2_200,
            }
        )

    return pd.DataFrame(rows)


def test_is_excluded_instrument_detects_etf_spac_and_preferred():
    """ETF/스팩/우선주 성격 종목은 기본 유니버스에서 제외되어야 한다."""

    print("\n[스크리너 제외 규칙 테스트] KODEX 200:", screener_service.is_excluded_instrument("KODEX 200"))
    print("[스크리너 제외 규칙 테스트] 미래산업스팩:", screener_service.is_excluded_instrument("미래산업스팩"))
    print("[스크리너 제외 규칙 테스트] 삼성전자우:", screener_service.is_excluded_instrument("삼성전자우"))
    print("[스크리너 제외 규칙 테스트] 삼성전자:", screener_service.is_excluded_instrument("삼성전자"))

    assert screener_service.is_excluded_instrument("KODEX 200") is True
    assert screener_service.is_excluded_instrument("미래산업스팩") is True
    assert screener_service.is_excluded_instrument("삼성전자우") is True
    assert screener_service.is_excluded_instrument("삼성전자") is False


def test_build_request_hash_is_stable_for_filter_order():
    """필터 순서가 달라도 request hash는 같아야 캐시 재사용이 가능하다."""

    left = screener_service.normalize_scan_request(
        ScreeningScanRequest(include_filters=["rs_positive", "vpci_positive", "volume_confirmed"])
    )
    right = screener_service.normalize_scan_request(
        ScreeningScanRequest(include_filters=["volume_confirmed", "vpci_positive", "rs_positive"])
    )

    left_hash = screener_service.build_request_hash(left)
    right_hash = screener_service.build_request_hash(right)

    print("\n[스크리너 hash 테스트] left filters:", left.include_filters)
    print("[스크리너 hash 테스트] right filters:", right.include_filters)
    print("[스크리너 hash 테스트] hash:", left_hash)

    assert left.include_filters == ["rs_positive", "volume_confirmed", "vpci_positive"]
    assert right.include_filters == ["rs_positive", "volume_confirmed", "vpci_positive"]
    assert left_hash == right_hash


def test_evaluate_candidate_detects_stage2_starter_and_optional_filters():
    """Stage 2 전환 직후 후보는 optional 필터를 통과하면 matched 결과를 반환해야 한다."""

    weekly_df = _build_weekly_candidate_frame()
    daily_df = _build_daily_candidate_frame()
    benchmark_df = weekly_df.copy()
    benchmark_df["close"] = benchmark_df["close"] * 0.97

    config = screener_service.normalize_scan_request(
        ScreeningScanRequest(
            include_filters=["vpci_positive", "rs_positive"],
            stage_start_window_weeks=8,
            max_distance_to_30w_pct=15,
            volume_ratio_min=1.2,
        )
    )

    result = screener_service.evaluate_candidate(
        master=SimpleNamespace(
            ticker="005930",
            name="삼성전자",
            sector_name="제조",
            industry_name="전기전자",
        ),
        weekly_df=weekly_df,
        daily_df=daily_df,
        benchmark_weekly_df=benchmark_df,
        config=config,
    )

    print("\n[스크리너 Stage2 테스트] outcome:", result.outcome)
    print("[스크리너 Stage2 테스트] result:", result.result)

    assert result.outcome == "matched"
    assert result.result is not None
    assert result.result["stage_label"] == "MARKUP"
    assert result.result["weeks_since_stage2_start"] is not None
    assert result.result["score"] > 60
    assert "stage2_start" in result.result["matched_filters"]
    assert "rs_positive" in result.result["matched_filters"]
