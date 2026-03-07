from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete
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
            overwrite: bool = False,  # 기본값을 False(Upsert 개념)로 변경
    ) -> int:
        if not ohlcv_data:
            return 0

        saved_count = 0

        # 1. overwrite가 True면 강제 갱신이므로 해당 종목의 기존 데이터를 모두 삭제
        if overwrite:
            await db.execute(
                delete(OHLCDaily).where(OHLCDaily.stock_id == stock_id)
            )
            logger.info(f"🐤 기존 일봉 데이터 삭제 완료 (강제 갱신, stock_id: {stock_id})")
            existing_dates = set()  # 모두 지웠으므로 빈 Set

        # 2. overwrite가 False면 기존 날짜들을 가져와서 중복 방지 (최적화 로직)
        else:
            existing_dates_result = await db.execute(
                select(OHLCDaily.date).where(OHLCDaily.stock_id == stock_id)
            )
            existing_dates = set(existing_dates_result.scalars().all())

        # 3. 데이터 Insert
        for data in ohlcv_data:
            date_obj = date.fromisoformat(data["date"]) if isinstance(data["date"], str) else data["date"]

            # DB에 없는 날짜만 새로 추가 (overwrite일 때는 existing_dates가 비어있으므로 전부 들어감)
            if date_obj not in existing_dates:
                ohlcv = OHLCDaily(
                    stock_id=stock_id,
                    date=date_obj,
                    open=data["open"],
                    high=data["high"],
                    low=data["low"],
                    close=data["close"],
                    volume=data["volume"],
                )
                db.add(ohlcv)
                saved_count += 1

        # 4. 저장된 건수가 있거나, 삭제(overwrite)가 일어났을 때만 커밋
        if saved_count > 0 or overwrite:
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
            # Convert ISO string date to date object
            date_obj = date.fromisoformat(data["week_start"]) if isinstance(data["week_start"], str) else data["week_start"]
            
            # Check if data already exists
            result = await db.execute(
                select(OHLCWeekly).where(
                    and_(
                        OHLCWeekly.stock_id == stock_id,
                        OHLCWeekly.week_start == date_obj,
                    )
                )
            )
            existing = result.scalar_one_or_none()

            if not existing:
                ohlcv = OHLCWeekly(
                    stock_id=stock_id,
                    week_start=date_obj,
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

        await db.execute(delete(OHLCWeekly).where(OHLCWeekly.stock_id == stock_id))

        if not daily_data:
            await db.commit()
            return 0

        weekly_groups = {}
        for daily in sorted(daily_data, key=lambda item: item.date):
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
                continue

            group = weekly_groups[week_key]
            group["high"] = max(group["high"], daily.high)
            group["low"] = min(group["low"], daily.low)
            group["close"] = daily.close
            group["volume"] += daily.volume

        for data in weekly_groups.values():
            db.add(
                OHLCWeekly(
                    stock_id=stock_id,
                    week_start=data["week_start"],
                    open=data["open"],
                    high=data["high"],
                    low=data["low"],
                    close=data["close"],
                    volume=data["volume"],
                )
            )

        await db.commit()
        return len(weekly_groups)


# Global data service instance
data_service = DataService()
