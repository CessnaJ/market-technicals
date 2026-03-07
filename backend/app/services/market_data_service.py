from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OHLCDaily, OHLCWeekly, Stock
from app.schemas import ChartDataPoint
from app.services.data_service import data_service
from app.services.kis_api.price import kis_price_service


OLDER_FETCH_SPAN_DAYS = {
    "daily": 420,
    "weekly": 980,
    "monthly": 2555,
}


class MarketDataService:
    """Shared market-data helpers for chart and indicator routes."""

    async def ensure_stock_history(
        self,
        db: AsyncSession,
        ticker: str,
        *,
        force_refresh: bool = False,
        min_daily_records: int = 120,
    ) -> Optional[Stock]:
        result = await db.execute(select(Stock).where(Stock.ticker == ticker))
        stock = result.scalar_one_or_none()

        if stock is None:
            current_price = await kis_price_service.get_current_price(ticker)
            if not current_price:
                return None

            stock = await data_service.get_or_create_stock(
                db,
                ticker=ticker,
                name=current_price.get("name", ticker),
                market=current_price.get("market"),
            )

        daily_count = await db.scalar(
            select(func.count(OHLCDaily.id)).where(OHLCDaily.stock_id == stock.id)
        )
        weekly_count = await db.scalar(
            select(func.count(OHLCWeekly.id)).where(OHLCWeekly.stock_id == stock.id)
        )
        oldest_daily = await self.get_oldest_daily_date(db, stock.id)
        oldest_weekly = await self.get_oldest_weekly_date(db, stock.id)
        expected_oldest_week = (
            oldest_daily - timedelta(days=oldest_daily.weekday())
            if oldest_daily is not None
            else None
        )

        needs_daily_refresh = (
            force_refresh
            or (daily_count or 0) < min_daily_records
        )
        needs_weekly_rebuild = (
            expected_oldest_week is not None
            and (
                (weekly_count or 0) == 0
                or oldest_weekly is None
                or oldest_weekly > expected_oldest_week
            )
        )

        if not needs_daily_refresh and not needs_weekly_rebuild:
            return stock

        daily_updated = False
        if needs_daily_refresh:
            fetched_daily = await kis_price_service.get_daily_price(
                ticker=ticker,
                start_date=date.today() - timedelta(days=730),
                use_cache=not force_refresh,
            )
            if fetched_daily:
                await data_service.save_ohlcv_daily(
                    db,
                    stock.id,
                    fetched_daily,
                    overwrite=force_refresh,
                )
                daily_updated = True

        if daily_updated or needs_weekly_rebuild:
            await data_service.convert_daily_to_weekly(db, stock.id)
        return stock

    async def load_chart_points(
        self,
        db: AsyncSession,
        stock_id: int,
        timeframe: str,
        *,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        before_date: Optional[date] = None,
        limit: Optional[int] = None,
    ) -> list[ChartDataPoint]:
        if timeframe == "weekly":
            query = (
                select(OHLCWeekly)
                .where(OHLCWeekly.stock_id == stock_id)
                .order_by(OHLCWeekly.week_start.desc())
            )
            if start_date:
                query = query.where(OHLCWeekly.week_start >= start_date)
            if end_date:
                query = query.where(OHLCWeekly.week_start <= end_date)
            if before_date:
                query = query.where(OHLCWeekly.week_start < before_date)
            if limit:
                query = query.limit(limit)

            result = await db.execute(query)
            records = result.scalars().all()
            points = [
                ChartDataPoint(
                    date=record.week_start,
                    open=float(record.open),
                    high=float(record.high),
                    low=float(record.low),
                    close=float(record.close),
                    volume=int(record.volume),
                )
                for record in records
            ]
            points.sort(key=lambda item: item.date)
            return points

        query = (
            select(OHLCDaily)
            .where(OHLCDaily.stock_id == stock_id)
            .order_by(OHLCDaily.date.desc())
        )
        if start_date:
            query = query.where(OHLCDaily.date >= start_date)
        if end_date:
            query = query.where(OHLCDaily.date <= end_date)
        if before_date:
            query = query.where(OHLCDaily.date < before_date)

        source_limit = limit
        if timeframe == "monthly":
            source_limit = None

        if source_limit:
            query = query.limit(source_limit)

        result = await db.execute(query)
        daily_records = result.scalars().all()
        daily_points = [
            ChartDataPoint(
                date=record.date,
                open=float(record.open),
                high=float(record.high),
                low=float(record.low),
                close=float(record.close),
                volume=int(record.volume),
            )
            for record in daily_records
        ]
        daily_points.sort(key=lambda item: item.date)

        if timeframe == "monthly":
            aggregated = self.aggregate_points(daily_points, "monthly")
            if limit:
                return aggregated[-limit:]
            return aggregated

        if limit:
            return daily_points[-limit:]
        return daily_points

    async def has_points_before(
        self,
        db: AsyncSession,
        stock_id: int,
        timeframe: str,
        before_date: date,
    ) -> bool:
        if timeframe == "weekly":
            result = await db.execute(
                select(OHLCWeekly.id)
                .where(
                    OHLCWeekly.stock_id == stock_id,
                    OHLCWeekly.week_start < before_date,
                )
                .limit(1)
            )
            return result.scalar_one_or_none() is not None

        result = await db.execute(
            select(OHLCDaily.id)
            .where(
                OHLCDaily.stock_id == stock_id,
                OHLCDaily.date < before_date,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def get_oldest_daily_date(
        self,
        db: AsyncSession,
        stock_id: int,
    ) -> Optional[date]:
        result = await db.execute(
            select(OHLCDaily.date)
            .where(OHLCDaily.stock_id == stock_id)
            .order_by(OHLCDaily.date.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_oldest_weekly_date(
        self,
        db: AsyncSession,
        stock_id: int,
    ) -> Optional[date]:
        result = await db.execute(
            select(OHLCWeekly.week_start)
            .where(OHLCWeekly.stock_id == stock_id)
            .order_by(OHLCWeekly.week_start.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def fetch_history_before(
        self,
        db: AsyncSession,
        ticker: str,
        stock_id: int,
        timeframe: str,
        *,
        before_date: date,
        required_points: int,
    ) -> bool:
        existing = await self.load_chart_points(
            db,
            stock_id,
            timeframe,
            before_date=before_date,
            limit=required_points,
        )
        if len(existing) >= required_points:
            return False

        current_oldest = await self.get_oldest_daily_date(db, stock_id)
        if current_oldest is None:
            return False

        span_days = max(OLDER_FETCH_SPAN_DAYS[timeframe], required_points * 3)
        fetched_any = False

        for _ in range(4):
            fetch_end = current_oldest - timedelta(days=1)
            fetch_start = fetch_end - timedelta(days=span_days)
            if fetch_end < date(1980, 1, 1):
                break

            fetched_daily = await kis_price_service.get_daily_price(
                ticker=ticker,
                start_date=fetch_start,
                end_date=fetch_end,
                use_cache=True,
            )
            if not fetched_daily:
                break

            previous_oldest = current_oldest
            await data_service.save_ohlcv_daily(
                db,
                stock_id,
                fetched_daily,
                overwrite=False,
            )
            await data_service.convert_daily_to_weekly(db, stock_id)

            current_oldest = await self.get_oldest_daily_date(db, stock_id)
            fetched_any = True

            existing = await self.load_chart_points(
                db,
                stock_id,
                timeframe,
                before_date=before_date,
                limit=required_points,
            )
            if len(existing) >= required_points:
                break

            if current_oldest is None or current_oldest >= previous_oldest:
                break

        return fetched_any

    def aggregate_points(
        self,
        points: list[ChartDataPoint],
        timeframe: str,
    ) -> list[ChartDataPoint]:
        if timeframe != "monthly":
            return sorted(points, key=lambda item: item.date)

        groups: dict[date, ChartDataPoint] = {}
        for point in sorted(points, key=lambda item: item.date):
            month_start = point.date.replace(day=1)
            if month_start not in groups:
                groups[month_start] = ChartDataPoint(
                    date=month_start,
                    open=point.open,
                    high=point.high,
                    low=point.low,
                    close=point.close,
                    volume=point.volume,
                )
                continue

            current = groups[month_start]
            current.high = max(current.high, point.high)
            current.low = min(current.low, point.low)
            current.close = point.close
            current.volume += point.volume

        return [groups[key] for key in sorted(groups.keys())]


market_data_service = MarketDataService()
