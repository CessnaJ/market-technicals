from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from datetime import datetime

from app.core.database import get_db
from app.models import Watchlist
from app.schemas import Stock

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("", response_model=List[dict])
async def get_watchlist(db: AsyncSession = Depends(get_db)):
    """Get all watchlist items"""
    result = await db.execute(
        select(Watchlist).order_by(Watchlist.priority.desc(), Watchlist.added_at.desc())
    )
    watchlist = result.scalars().all()

    return [
        {
            "id": item.id,
            "ticker": item.ticker,
            "name": item.name,
            "memo": item.memo,
            "priority": item.priority,
            "added_at": item.added_at.isoformat() if item.added_at else None,
        }
        for item in watchlist
    ]


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    ticker: str,
    name: str,
    memo: str = None,
    priority: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Add stock to watchlist"""
    # Check if already exists
    result = await db.execute(select(Watchlist).where(Watchlist.ticker == ticker))
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stock {ticker} already in watchlist",
        )

    watchlist_item = Watchlist(
        ticker=ticker,
        name=name,
        memo=memo,
        priority=priority,
    )
    db.add(watchlist_item)
    await db.commit()
    await db.refresh(watchlist_item)

    return {
        "id": watchlist_item.id,
        "ticker": watchlist_item.ticker,
        "name": watchlist_item.name,
        "memo": watchlist_item.memo,
        "priority": watchlist_item.priority,
        "added_at": watchlist_item.added_at.isoformat(),
    }


@router.put("/{ticker}", response_model=dict)
async def update_watchlist(
    ticker: str,
    name: str = None,
    memo: str = None,
    priority: int = None,
    db: AsyncSession = Depends(get_db),
):
    """Update watchlist item"""
    result = await db.execute(select(Watchlist).where(Watchlist.ticker == ticker))
    watchlist_item = result.scalar_one_or_none()

    if not watchlist_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {ticker} not found in watchlist",
        )

    if name is not None:
        watchlist_item.name = name
    if memo is not None:
        watchlist_item.memo = memo
    if priority is not None:
        watchlist_item.priority = priority

    await db.commit()
    await db.refresh(watchlist_item)

    return {
        "id": watchlist_item.id,
        "ticker": watchlist_item.ticker,
        "name": watchlist_item.name,
        "memo": watchlist_item.memo,
        "priority": watchlist_item.priority,
        "added_at": watchlist_item.added_at.isoformat(),
    }


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_from_watchlist(ticker: str, db: AsyncSession = Depends(get_db)):
    """Remove stock from watchlist"""
    result = await db.execute(select(Watchlist).where(Watchlist.ticker == ticker))
    watchlist_item = result.scalar_one_or_none()

    if not watchlist_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {ticker} not found in watchlist",
        )

    await db.execute(delete(Watchlist).where(Watchlist.ticker == ticker))
    await db.commit()

    return None
