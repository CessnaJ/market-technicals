from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FinancialData, Stock
from app.services.kis_api.client import kis_client
from app.services.kis_api.price import kis_price_service


class FinancialService:
    """Fetches and stores derived financial summary data for dashboard use."""

    STALE_AFTER = timedelta(hours=24)
    ENDPOINT_PATH = "/uapi/domestic-stock/v1/finance/financial-ratio"
    ENDPOINT_TR_ID = "FHKST66430300"

    async def get_latest_financial_data(
        self,
        db: AsyncSession,
        stock_id: int,
    ) -> Optional[FinancialData]:
        result = await db.execute(
            select(FinancialData)
            .where(FinancialData.stock_id == stock_id)
            .order_by(FinancialData.period_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def is_stale(self, financial_data: Optional[FinancialData]) -> bool:
        if financial_data is None or financial_data.fetched_at is None:
            return True

        fetched_at = financial_data.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)

        return fetched_at <= datetime.now(timezone.utc) - self.STALE_AFTER

    async def refresh_financial_data(
        self,
        db: AsyncSession,
        stock: Stock,
    ) -> Optional[FinancialData]:
        rows = await self._fetch_financial_ratio_rows(stock.ticker)
        if not rows:
            return None

        result = await db.execute(
            select(FinancialData).where(FinancialData.stock_id == stock.id)
        )
        existing_by_key = {
            (item.period_type, item.period_date): item for item in result.scalars().all()
        }

        fetched_at = datetime.now(timezone.utc)
        for row in rows:
            key = (row["period_type"], row["period_date"])
            existing = existing_by_key.get(key)
            if existing is None:
                existing = FinancialData(stock_id=stock.id, **row)
                db.add(existing)
            else:
                for field, value in row.items():
                    setattr(existing, field, value)
            existing.fetched_at = fetched_at

        await db.commit()
        return await self.get_latest_financial_data(db, stock.id)

    def to_summary(
        self,
        stock: Stock,
        financial_data: Optional[FinancialData],
    ) -> dict[str, Any]:
        if financial_data is None:
            return {
                "ticker": stock.ticker,
                "name": stock.name,
                "period_date": None,
                "psr": None,
                "per": None,
                "pbr": None,
                "roe": None,
                "debt_ratio": None,
                "market_cap": None,
            }

        return {
            "ticker": stock.ticker,
            "name": stock.name,
            "period_date": financial_data.period_date,
            "psr": self._to_float(financial_data.psr),
            "per": self._to_float(financial_data.per),
            "pbr": self._to_float(financial_data.pbr),
            "roe": self._to_float(financial_data.roe),
            "debt_ratio": self._to_float(financial_data.debt_ratio),
            "market_cap": self._to_float(financial_data.market_cap),
        }

    async def _fetch_financial_ratio_rows(self, ticker: str) -> list[dict[str, Any]]:
        response = await kis_client.get(
            self.ENDPOINT_PATH,
            params={
                "FID_DIV_CLS_CODE": "0",
                "fid_cond_mrkt_div_code": "J",
                "fid_input_iscd": ticker,
            },
            tr_id=self.ENDPOINT_TR_ID,
        )

        output = response.get("output") if response else None
        if output is None:
            return []

        rows = output if isinstance(output, list) else [output]
        current_price_payload = await kis_price_service.get_current_price(ticker)
        current_price = self._to_decimal(
            current_price_payload.get("current_price") if current_price_payload else None
        )

        parsed_rows = []
        for row in rows:
            period_date = self._parse_period_date(row.get("stac_yymm"))
            if period_date is None:
                continue

            eps = self._to_decimal(row.get("eps"))
            bps = self._to_decimal(row.get("bps"))
            sps = self._to_decimal(row.get("sps"))

            parsed_rows.append(
                {
                    "period_type": "ANNUAL",
                    "period_date": period_date,
                    "revenue": None,
                    "operating_income": None,
                    "net_income": None,
                    "total_assets": None,
                    "total_equity": None,
                    "shares_outstanding": None,
                    "market_cap": None,
                    "psr": self._safe_ratio(current_price, sps),
                    "per": self._safe_ratio(current_price, eps),
                    "pbr": self._safe_ratio(current_price, bps),
                    "roe": self._to_decimal(row.get("roe_val")),
                    "debt_ratio": self._to_decimal(row.get("lblt_rate")),
                }
            )

        parsed_rows.sort(key=lambda item: item["period_date"], reverse=True)
        return parsed_rows

    def _parse_period_date(self, value: Any) -> Optional[date]:
        if value is None:
            return None

        text = str(value).strip()
        if len(text) != 6 or not text.isdigit():
            return None

        year = int(text[:4])
        month = int(text[4:6])
        last_day = monthrange(year, month)[1]
        return date(year, month, last_day)

    def _safe_ratio(
        self,
        numerator: Optional[Decimal],
        denominator: Optional[Decimal],
    ) -> Optional[Decimal]:
        if numerator is None or denominator is None or denominator <= 0:
            return None
        return numerator / denominator

    def _to_decimal(self, value: Any) -> Optional[Decimal]:
        if value in (None, "", "-"):
            return None

        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    def _to_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        return float(value)


financial_service = FinancialService()
