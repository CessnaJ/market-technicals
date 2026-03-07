from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OHLCDaily, OHLCWeekly, Stock
from app.schemas import ChartDataPoint
from app.services.data_service import data_service
from app.services.kis_api.price import kis_price_service


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

        needs_refresh = (
            force_refresh
            or (daily_count or 0) < min_daily_records
            or (weekly_count or 0) == 0
        )

        if not needs_refresh:
            return stock

        fetched_daily = await kis_price_service.get_daily_price(
            ticker=ticker,
            start_date=date.today() - timedelta(days=730),
            use_cache=not force_refresh,
        )
        if not fetched_daily:
            return stock

        await data_service.save_ohlcv_daily(
            db,
            stock.id,
            fetched_daily,
            overwrite=force_refresh,
        )
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

        source_limit = limit
        if timeframe == "monthly":
            source_limit = None if start_date or end_date else 2000

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
