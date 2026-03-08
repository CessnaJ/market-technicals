import pytest

from app.api.v1.stocks import (
    get_price_preload_status,
    run_price_preload_batch,
    seed_price_preload_jobs,
    start_price_preload_auto_sync,
)
from app.schemas import (
    PricePreloadAutoSyncRequest,
    PricePreloadRunRequest,
    PricePreloadSeedRequest,
)


@pytest.mark.asyncio
async def test_seed_price_preload_jobs_returns_seed_summary(monkeypatch):
    """선적재 시드 엔드포인트는 큐 생성 요약을 그대로 반환해야 한다."""

    async def fake_seed_universe(db, **kwargs):
        return {
            "target_days": kwargs["target_days"],
            "markets": kwargs["markets"] or [],
            "seeded": 100,
            "updated": 5,
            "skipped": 2,
            "total_jobs": 107,
        }

    monkeypatch.setattr("app.api.v1.stocks.preload_service.seed_universe", fake_seed_universe)

    response = await seed_price_preload_jobs(
        PricePreloadSeedRequest(target_days=730, markets=["KOSPI"], limit=100, reset_existing=False),
        db=None,
    )

    print("\n[선적재 시드 테스트] seeded:", response["seeded"])
    print("[선적재 시드 테스트] total_jobs:", response["total_jobs"])

    assert response["seeded"] == 100
    assert response["total_jobs"] == 107


@pytest.mark.asyncio
async def test_get_price_preload_status_returns_failure_list(monkeypatch):
    """선적재 상태 엔드포인트는 실패 샘플과 상태 카운트를 반환해야 한다."""

    async def fake_get_status(db, **kwargs):
        return {
            "total_jobs": 120,
            "status_counts": {
                "PENDING": 70,
                "COMPLETED": 40,
                "FAILED": 10,
            },
            "recent_failures": [
                {
                    "ticker": "005930",
                    "name": "삼성전자",
                    "attempts": 2,
                    "last_error": "timeout",
                    "updated_at": None,
                }
            ],
        }

    monkeypatch.setattr("app.api.v1.stocks.preload_service.get_status", fake_get_status)

    response = await get_price_preload_status(failure_limit=5, db=None)

    print("\n[선적재 상태 테스트] 상태 카운트:", response["status_counts"])
    print("[선적재 상태 테스트] 실패 샘플:", response["recent_failures"])

    assert response["status_counts"]["FAILED"] == 10
    assert response["recent_failures"][0]["ticker"] == "005930"


@pytest.mark.asyncio
async def test_run_price_preload_batch_returns_run_summary(monkeypatch):
    """선적재 실행 엔드포인트는 배치 실행 요약을 반환해야 한다."""

    async def fake_run_batch(db, **kwargs):
        return {
            "requested": kwargs["batch_size"],
            "processed": 2,
            "completed": 1,
            "failed": 1,
            "skipped": 0,
            "results": [
                {
                    "ticker": "010950",
                    "name": "S-Oil",
                    "status": "COMPLETED",
                    "daily_records": 700,
                    "weekly_records": 150,
                    "error": None,
                },
                {
                    "ticker": "069500",
                    "name": "KODEX 200",
                    "status": "FAILED",
                    "daily_records": 0,
                    "weekly_records": 0,
                    "error": "no data",
                },
            ],
        }

    monkeypatch.setattr("app.api.v1.stocks.preload_service.run_batch", fake_run_batch)

    response = await run_price_preload_batch(
        PricePreloadRunRequest(batch_size=2, markets=["KOSPI"], statuses=["PENDING"], sleep_ms=0),
        db=None,
    )

    print("\n[선적재 실행 테스트] processed:", response["processed"])
    print("[선적재 실행 테스트] results:", response["results"])

    assert response["processed"] == 2
    assert response["completed"] == 1
    assert response["failed"] == 1


@pytest.mark.asyncio
async def test_start_price_preload_auto_sync_returns_started_summary(monkeypatch):
    """자동 선적재 시작 엔드포인트는 백그라운드 실행 시작 요약을 반환해야 한다."""

    async def fake_start_auto_sync(**kwargs):
        return {
            "started": True,
            "already_running": False,
            "message": "Universe preload started",
            "total_jobs": 4317,
            "major_ticker_count": 203,
            "is_running": True,
            "last_started_at": None,
        }

    monkeypatch.setattr("app.api.v1.stocks.preload_service.start_auto_sync", fake_start_auto_sync)

    response = await start_price_preload_auto_sync(
        PricePreloadAutoSyncRequest(
            current_ticker="010950",
            benchmark_ticker="069500",
            batch_size=25,
            sleep_ms=100,
        )
    )

    print("\n[자동 선적재 시작 테스트] total_jobs:", response["total_jobs"])
    print("[자동 선적재 시작 테스트] major_ticker_count:", response["major_ticker_count"])

    assert response["started"] is True
    assert response["is_running"] is True
    assert response["major_ticker_count"] == 203
