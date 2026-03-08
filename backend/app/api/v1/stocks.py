from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas import StockMasterSyncResponse, StockProfileResponse, StockSearchResponse
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
