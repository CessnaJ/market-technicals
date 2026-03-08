from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas import (
    ScreeningResultsResponse,
    ScreeningRunStatusResponse,
    ScreeningScanCreateResponse,
    ScreeningScanRequest,
)
from app.services.screener_service import screener_service

router = APIRouter(prefix="/screener", tags=["screener"])


@router.post("/scans", response_model=ScreeningScanCreateResponse)
async def create_screener_scan(
    payload: ScreeningScanRequest,
):
    return await screener_service.create_scan(payload)


@router.get("/scans/{scan_id}", response_model=ScreeningRunStatusResponse)
async def get_screener_scan(
    scan_id: int,
    db: AsyncSession = Depends(get_db),
):
    response = await screener_service.get_scan(db, scan_id)
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan {scan_id} not found",
        )
    return response


@router.get("/scans/{scan_id}/results", response_model=ScreeningResultsResponse)
async def get_screener_scan_results(
    scan_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await screener_service.get_results(
        db,
        scan_id=scan_id,
        limit=limit,
        offset=offset,
    )


@router.get("/scans/latest", response_model=ScreeningRunStatusResponse)
async def get_latest_screener_scan(
    preset: str = Query("weinstein_stage2_start"),
    benchmark_ticker: str = Query("069500"),
    filters_hash: str = Query(..., min_length=64, max_length=64),
    db: AsyncSession = Depends(get_db),
):
    response = await screener_service.get_latest_scan(
        db,
        preset=preset,
        benchmark_ticker=benchmark_ticker,
        filters_hash=filters_hash,
    )
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching screener run found",
        )
    return response
