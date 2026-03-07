import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Stock
from app.schemas import FinancialMetrics
from app.services.data_service import data_service
from app.services.financial_service import financial_service
from app.services.kis_api.price import kis_price_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/financial", tags=["financial"])


@router.get("/{ticker}", response_model=FinancialMetrics)
async def get_financial_metrics(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    stock = result.scalar_one_or_none()

    if stock is None:
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

    latest = await financial_service.get_latest_financial_data(db, stock.id)
    if financial_service.is_stale(latest):
        latest = await financial_service.refresh_financial_data(db, stock) or latest

    return financial_service.to_summary(stock, latest)
