from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import date

from app.core.database import get_db
from app.models import Stock
from app.services.kis_api.price import kis_price_service
from app.services.data_service import data_service
from app.core.redis_client import redis_client
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fetch", tags=["fetch"])


@router.post("/{ticker}")
async def fetch_stock_data(
    ticker: str,
    force_refresh: bool = False,
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None,
    ):
    """
    Fetch data for a specific stock from KIS API

    Args:
        ticker: Stock ticker (e.g., "010950")
        force_refresh: Force refresh from KIS API (bypass cache)
    """
    # Get or create stock in database
    current_price = await kis_price_service.get_current_price(ticker)

    if not current_price:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {ticker} not found",
        )

    stock = await data_service.get_or_create_stock(
        db,
        ticker=ticker,
        name=current_price.get("name", ticker),
        market=current_price.get("market"),
    )

    # Fetch historical OHLCV data
    # If force_refresh is True, disable cache and fetch fresh data
    ohlcv_data = await kis_price_service.get_daily_price(
        ticker,
        use_cache=not force_refresh
    )

    if ohlcv_data:
        # Use overwrite=True when force_refresh is True to replace existing data
        saved_count = await data_service.save_ohlcv_daily(
            db, stock.id, ohlcv_data,
            overwrite=force_refresh
        )
        logger.info(f"🐤 [{ticker}] 일봉 데이터 {saved_count}건 저장 완료")

        # Convert to weekly
        await data_service.convert_daily_to_weekly(db, stock.id)

    # Invalidate cache for this stock
    cache_pattern = f"kis:*{ticker}:*"
    await redis_client.delete_pattern(cache_pattern)

    return {
        "ticker": ticker,
        "name": current_price.get("name"),
        "current_price": current_price.get("current_price"),
        "ohlcv_records": len(ohlcv_data) if ohlcv_data else 0,
        "message": "Data fetched successfully",
    }


@router.post("/batch")
async def fetch_batch_data(
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """
    Batch fetch data for all watchlist items

    Fetches data sequentially with rate limiting delay
    """
    from app.models import Watchlist
    from sqlalchemy import select

    # Get all watchlist items
    result = await db.execute(
        select(Watchlist).order_by(Watchlist.priority.desc())
    )
    watchlist_items = result.scalars().all()

    if not watchlist_items:
        return {"message": "No items in watchlist", "fetched": 0}

    import asyncio

    results = []
    for item in watchlist_items:
        try:
            # Fetch data for this stock
            current_price = await kis_price_service.get_current_price(item.ticker)

            if current_price:
                stock = await data_service.get_or_create_stock(
                    db,
                    ticker=item.ticker,
                    name=item.name or current_price.get("name", item.ticker),
                    market=current_price.get("market"),
                )

                ohlcv_data = await kis_price_service.get_daily_price(
                    item.ticker, use_cache=False
                )

                if ohlcv_data:
                    saved_count = await data_service.save_ohlcv_daily(
                        db, stock.id, ohlcv_data
                    )
                    await data_service.convert_daily_to_weekly(db, stock.id)

                    results.append({
                        "ticker": item.ticker,
                        "name": item.name,
                        "status": "success",
                        "records": saved_count,
                    })

                    logger.info(
                        f"🐤 [{item.ticker}] {item.name} - {saved_count}건 수집 완료"
                    )
                else:
                    results.append({
                        "ticker": item.ticker,
                        "name": item.name,
                        "status": "no_data",
                        "records": 0,
                    })
            else:
                results.append({
                    "ticker": item.ticker,
                    "name": item.name,
                    "status": "not_found",
                    "records": 0,
                })

            # Rate limiting delay (0.1s between requests)
            await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"❌ [{item.ticker}] 데이터 수집 실패: {e}")
            results.append({
                "ticker": item.ticker,
                "name": item.name,
                "status": "error",
                "error": str(e),
                "records": 0,
            })

    return {
        "message": f"Batch fetch completed",
        "total": len(watchlist_items),
        "results": results,
    }
