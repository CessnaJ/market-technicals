from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import date

from app.core.database import get_db
from app.models import Stock, FinancialData
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/financial", tags=["financial"])


@router.get("/{ticker}")
async def get_financial_metrics(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get financial metrics for a stock

    Returns:
        Financial metrics including PSR, PER, PBR, ROE, Debt Ratio, Market Cap
    """
    from fastapi import HTTPException, status

    # Get stock
    result = await db.execute(select(Stock).where(Stock.ticker == ticker))
    stock = result.scalar_one_or_none()

    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {ticker} not found",
        )

    # Get financial data
    result = await db.execute(
        select(FinancialData)
        .where(FinancialData.stock_id == stock.id)
        .order_by(FinancialData.period_date.desc())
        .limit(1)
    )
    financial_data = result.scalar_one_or_none()

    if not financial_data:
        # Return empty metrics if no financial data available
        return {
            "ticker": ticker,
            "name": stock.name,
            "psr": None,
            "per": None,
            "pbr": None,
            "roe": None,
            "debt_ratio": None,
            "market_cap": None,
            "period_date": None,
        }

    # Calculate market cap if not available
    market_cap = None
    if financial_data.market_cap:
        market_cap = float(financial_data.market_cap)
    elif financial_data.shares_outstanding and stock.current_price:
        # Calculate market cap: shares * price
        market_cap = float(financial_data.shares_outstanding) * float(stock.current_price)

    return {
        "ticker": ticker,
        "name": stock.name,
        "psr": float(financial_data.psr) if financial_data.psr else None,
        "per": float(financial_data.per) if financial_data.per else None,
        "pbr": float(financial_data.pbr) if financial_data.pbr else None,
        "roe": float(financial_data.roe) if financial_data.roe else None,
        "debt_ratio": float(financial_data.debt_ratio) if financial_data.debt_ratio else None,
        "market_cap": market_cap,
        "period_date": financial_data.period_date.isoformat() if financial_data.period_date else None,
    }
