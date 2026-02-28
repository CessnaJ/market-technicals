from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional, List
from datetime import date, timedelta
from app.models import Stock, OHLCDaily, OHLCWeekly, FinancialData
from app.schemas import StockCreate, OHLCDailyCreate, OHLCWeeklyCreate, FinancialDataCreate
import logging

logger = logging.getLogger(__name__)


class DataService:
    """Database operations for stock data"""

    async def get_or_create_stock(
        self,
        db: AsyncSession,
        ticker: str,
        name: str,
        market: Optional[str] = None,
    ) -> Stock:
        """Get existing stock or create new one"""
        result = await db.execute(select(Stock).where(Stock.ticker == ticker))
        stock = result.scalar_one_or_none()

        if not stock:
            stock = Stock(
                ticker=ticker,
                name=name,
                market=market,
            )
            db.add(stock)
            await db.flush()

        return stock

    async def save_ohlcv_daily(
        self,
        db: AsyncSession,
        stock_id: int,
        ohlcv_data: List[dict],
    ) -> int:
        """Save daily OHLCV data"""
        saved_count = 0

        for data in ohlcv_data:
            # Check if data already exists
            result = await db.execute(
                select(OHLCDaily).where(
                    and_(
                        OHLCDaily.stock_id == stock_id,
                        OHLCDaily.date == data["date"],
                    )
                )
            )
            existing = result.scalar_one_or_none()

            if not existing:
                ohlcv = OHLCDaily(
                    stock_id=stock_id,
                    date=data["date"],
                    open=data["open"],
                    high=data["high"],
                    low=data["low"],
                    close=data["close"],
                    volume=data["volume"],
                )
                db.add(ohlcv)
                saved_count += 1

        await db.commit()
        return saved_count

    async def get_ohlcv_daily(
        self,
        db: AsyncSession,
        stock_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: Optional[int] = None,
    ) -> List[OHLCDaily]:
        """Get daily OHLCV data"""
        query = select(OHLCDaily).where(OHLCDaily.stock_id == stock_id)

        if start_date:
            query = query.where(OHLCDaily.date >= start_date)
        if end_date:
            query = query.where(OHLCDaily.date <= end_date)

        query = query.order_by(OHLCDaily.date.desc())

        if limit:
            query = query.limit(limit)

        result = await db.execute(query)
        return result.scalars().all()

    async def save_ohlcv_weekly(
        self,
        db: AsyncSession,
        stock_id: int,
        weekly_data: List[dict],
    ) -> int:
        """Save weekly OHLCV data"""
        saved_count = 0

        for data in weekly_data:
            # Check if data already exists
            result = await db.execute(
                select(OHLCWeekly).where(
                    and_(
                        OHLCWeekly.stock_id == stock_id,
                        OHLCWeekly.week_start == data["week_start"],
                    )
                )
            )
            existing = result.scalar_one_or_none()

            if not existing:
                ohlcv = OHLCWeekly(
                    stock_id=stock_id,
                    week_start=data["week_start"],
                    open=data["open"],
                    high=data["high"],
                    low=data["low"],
                    close=data["close"],
                    volume=data["volume"],
                )
                db.add(ohlcv)
                saved_count += 1

        await db.commit()
        return saved_count

    async def get_ohlcv_weekly(
        self,
        db: AsyncSession,
        stock_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: Optional[int] = None,
    ) -> List[OHLCWeekly]:
        """Get weekly OHLCV data"""
        query = select(OHLCWeekly).where(OHLCWeekly.stock_id == stock_id)

        if start_date:
            query = query.where(OHLCWeekly.week_start >= start_date)
        if end_date:
            query = query.where(OHLCWeekly.week_start <= end_date)

        query = query.order_by(OHLCWeekly.week_start.desc())

        if limit:
            query = query.limit(limit)

        result = await db.execute(query)
        return result.scalars().all()

    async def convert_daily_to_weekly(
        self,
        db: AsyncSession,
        stock_id: int,
    ) -> int:
        """
        Convert daily OHLCV to weekly OHLCV
        Groups by week (Monday-based)
        """
        daily_data = await self.get_ohlcv_daily(db, stock_id, limit=1000)

        if not daily_data:
            return 0

        # Group by week
        weekly_groups = {}
        for daily in daily_data:
            # Get Monday of the week
            week_start = daily.date - timedelta(days=daily.date.weekday())
            week_key = week_start.strftime("%Y-%m-%d")

            if week_key not in weekly_groups:
                weekly_groups[week_key] = {
                    "week_start": week_start,
                    "open": daily.open,
                    "high": daily.high,
                    "low": daily.low,
                    "close": daily.close,
                    "volume": daily.volume,
                }
            else:
                group = weekly_groups[week_key]
                group["high"] = max(group["high"], daily.high)
                group["low"] = min(group["low"], daily.low)
                group["close"] = daily.close
                group["volume"] += daily.volume

        # Save weekly data
        weekly_list = list(weekly_groups.values())
        return await self.save_ohlcv_weekly(db, stock_id, weekly_list)


# Global data service instance
data_service = DataService()
