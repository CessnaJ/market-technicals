import logging

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis_client import redis_client
from app.models import Watchlist
from app.services.data_service import data_service
from app.services.kis_api.price import kis_price_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fetch", tags=["fetch"])


class FetchStockRequest(BaseModel):
    force_refresh: bool = False


@router.post("/{ticker}")
async def fetch_stock_data(
    ticker: str,
    payload: FetchStockRequest = Body(default_factory=FetchStockRequest),
    db: AsyncSession = Depends(get_db),
):
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

    ohlcv_data = await kis_price_service.get_daily_price(
        ticker=ticker,
        use_cache=not payload.force_refresh,
    )

    weekly_count = 0
    if ohlcv_data:
        saved_count = await data_service.save_ohlcv_daily(
            db,
            stock.id,
            ohlcv_data,
            overwrite=payload.force_refresh,
        )
        logger.info("🐤 [%s] 일봉 데이터 %s건 저장 완료", ticker, saved_count)
        weekly_count = await data_service.convert_daily_to_weekly(db, stock.id)
    else:
        saved_count = 0

    await redis_client.delete_pattern(f"kis:*{ticker}:*")

    return {
        "ticker": ticker,
        "name": current_price.get("name"),
        "current_price": current_price.get("current_price"),
        "ohlcv_records": len(ohlcv_data) if ohlcv_data else 0,
        "weekly_records": weekly_count,
        "message": "Data fetched successfully",
    }


@router.post("/batch")
async def fetch_batch_data(
    db: AsyncSession = Depends(get_db),
):
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
            current_price = await kis_price_service.get_current_price(item.ticker)
            if current_price:
                stock = await data_service.get_or_create_stock(
                    db,
                    ticker=item.ticker,
                    name=item.name or current_price.get("name", item.ticker),
                    market=current_price.get("market"),
                )

                ohlcv_data = await kis_price_service.get_daily_price(
                    item.ticker,
                    use_cache=False,
                )

                if ohlcv_data:
                    saved_count = await data_service.save_ohlcv_daily(
                        db,
                        stock.id,
                        ohlcv_data,
                    )
                    weekly_count = await data_service.convert_daily_to_weekly(db, stock.id)

                    results.append(
                        {
                            "ticker": item.ticker,
                            "name": item.name,
                            "status": "success",
                            "records": saved_count,
                            "weekly_records": weekly_count,
                        }
                    )
                    logger.info(
                        "🐤 [%s] %s - %s건 수집 완료",
                        item.ticker,
                        item.name,
                        saved_count,
                    )
                else:
                    results.append(
                        {
                            "ticker": item.ticker,
                            "name": item.name,
                            "status": "no_data",
                            "records": 0,
                            "weekly_records": 0,
                        }
                    )
            else:
                results.append(
                    {
                        "ticker": item.ticker,
                        "name": item.name,
                        "status": "not_found",
                        "records": 0,
                        "weekly_records": 0,
                    }
                )

            await asyncio.sleep(0.1)
        except Exception as exc:
            logger.error("❌ [%s] 데이터 수집 실패: %s", item.ticker, exc)
            results.append(
                {
                    "ticker": item.ticker,
                    "name": item.name,
                    "status": "error",
                    "error": str(exc),
                    "records": 0,
                    "weekly_records": 0,
                }
            )

    return {
        "message": "Batch fetch completed",
        "total": len(watchlist_items),
        "results": results,
    }
