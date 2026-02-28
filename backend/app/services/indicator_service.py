from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional, Dict, Any
from datetime import date
from app.models import IndicatorCache
import logging

logger = logging.getLogger(__name__)


class IndicatorService:
    """Service for managing indicator calculations and caching"""

    async def get_cached_indicator(
        self,
        db: AsyncSession,
        stock_id: int,
        indicator_name: str,
        timeframe: str,
        parameters: Dict[str, Any],
        indicator_date: date,
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached indicator value

        Args:
            db: Database session
            stock_id: Stock ID
            indicator_name: Indicator name (e.g., 'VPCI', 'WEINSTEIN_STAGE')
            timeframe: Timeframe ('DAILY', 'WEEKLY')
            parameters: Indicator parameters
            indicator_date: Date to get indicator for

        Returns:
            Cached indicator value or None
        """
        result = await db.execute(
            select(IndicatorCache).where(
                and_(
                    IndicatorCache.stock_id == stock_id,
                    IndicatorCache.indicator_name == indicator_name,
                    IndicatorCache.timeframe == timeframe,
                    IndicatorCache.parameters == parameters,
                    IndicatorCache.date == indicator_date,
                )
            )
        )
        cached = result.scalar_one_or_none()

        if cached:
            return cached.value

        return None

    async def cache_indicator(
        self,
        db: AsyncSession,
        stock_id: int,
        indicator_name: str,
        timeframe: str,
        parameters: Dict[str, Any],
        indicator_date: date,
        value: Dict[str, Any],
    ) -> None:
        """
        Cache indicator value

        Args:
            db: Database session
            stock_id: Stock ID
            indicator_name: Indicator name
            timeframe: Timeframe
            parameters: Indicator parameters
            indicator_date: Date
            value: Indicator value to cache
        """
        # Check if already exists
        result = await db.execute(
            select(IndicatorCache).where(
                and_(
                    IndicatorCache.stock_id == stock_id,
                    IndicatorCache.indicator_name == indicator_name,
                    IndicatorCache.timeframe == timeframe,
                    IndicatorCache.parameters == parameters,
                    IndicatorCache.date == indicator_date,
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            existing.value = value
        else:
            # Create new
            cached = IndicatorCache(
                stock_id=stock_id,
                indicator_name=indicator_name,
                timeframe=timeframe,
                parameters=parameters,
                date=indicator_date,
                value=value,
            )
            db.add(cached)

        await db.commit()

    async def invalidate_stock_indicators(
        self,
        db: AsyncSession,
        stock_id: int,
        indicator_name: Optional[str] = None,
    ) -> int:
        """
        Invalidate cached indicators for a stock

        Args:
            db: Database session
            stock_id: Stock ID
            indicator_name: Specific indicator name to invalidate (None = all)

        Returns:
            Number of invalidated entries
        """
        from sqlalchemy import delete

        stmt = delete(IndicatorCache).where(IndicatorCache.stock_id == stock_id)

        if indicator_name:
            stmt = stmt.where(IndicatorCache.indicator_name == indicator_name)

        result = await db.execute(stmt)
        await db.commit()

        return result.rowcount


# Global indicator service instance
indicator_service = IndicatorService()
