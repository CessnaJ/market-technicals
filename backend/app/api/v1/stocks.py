from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas import (
    PricePreloadAutoSyncRequest,
    PricePreloadAutoSyncResponse,
    PricePreloadRunRequest,
    PricePreloadRunResponse,
    PricePreloadSeedRequest,
    PricePreloadSeedResponse,
    PricePreloadStatusResponse,
    StockMasterSyncResponse,
    StockProfileResponse,
    StockSearchResponse,
)
from app.services.preload_service import preload_service
from app.services.stock_master_service import stock_master_service

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.post("/sync-master", response_model=StockMasterSyncResponse)
async def sync_stock_master(
    db: AsyncSession = Depends(get_db),
):
    return await stock_master_service.sync_master_data(db)


@router.get("/search", response_model=StockSearchResponse)
async def search_stocks(
    q: str = Query("", description="Ticker, stock name, or Hangul initials"),
    limit: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    master_ready, suggestions = await stock_master_service.search_stocks(db, q, limit=limit)
    return StockSearchResponse(master_ready=master_ready, suggestions=suggestions)


@router.get("/{ticker}/profile", response_model=StockProfileResponse)
async def get_stock_profile(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    profile = await stock_master_service.get_stock_profile(db, ticker.upper())
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {ticker} not found",
        )
    return profile


@router.post("/preload/seed", response_model=PricePreloadSeedResponse)
async def seed_price_preload_jobs(
    payload: PricePreloadSeedRequest,
    db: AsyncSession = Depends(get_db),
):
    return await preload_service.seed_universe(
        db,
        target_days=payload.target_days,
        markets=payload.markets,
        limit=payload.limit,
        reset_existing=payload.reset_existing,
    )


@router.get("/preload/status", response_model=PricePreloadStatusResponse)
async def get_price_preload_status(
    failure_limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    return await preload_service.get_status(db, failure_limit=failure_limit)


@router.post("/preload/run", response_model=PricePreloadRunResponse)
async def run_price_preload_batch(
    payload: PricePreloadRunRequest,
    db: AsyncSession = Depends(get_db),
):
    if await preload_service.is_global_runner_active(db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Universe preload auto-sync is already running",
        )
    return await preload_service.run_batch(
        db,
        batch_size=payload.batch_size,
        markets=payload.markets,
        statuses=payload.statuses,
        use_cache=payload.use_cache,
        force_refresh=payload.force_refresh,
        sleep_ms=payload.sleep_ms,
    )


@router.post("/preload/auto-sync", response_model=PricePreloadAutoSyncResponse)
async def start_price_preload_auto_sync(
    payload: PricePreloadAutoSyncRequest,
):
    return await preload_service.start_auto_sync(
        current_ticker=payload.current_ticker,
        benchmark_ticker=payload.benchmark_ticker,
        sync_master=payload.sync_master,
        batch_size=payload.batch_size,
        sleep_ms=payload.sleep_ms,
        worker_count=payload.worker_count,
        universe_target_days=payload.universe_target_days,
        major_target_days=payload.major_target_days,
        major_limit=payload.major_limit,
    )
