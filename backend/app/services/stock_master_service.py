from __future__ import annotations

import asyncio
from datetime import date, datetime
import io
import re
import zipfile

import httpx
import pandas as pd
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Stock
from app.models.stock_master import StockMaster, StockThemeMap
from app.schemas import (
    RelatedThemeGroup,
    StockProfileResponse,
    StockSearchSuggestion,
    StockTheme,
)
from app.services.kis_api.price import kis_price_service

CHOSEONG = [
    "ㄱ",
    "ㄲ",
    "ㄴ",
    "ㄷ",
    "ㄸ",
    "ㄹ",
    "ㅁ",
    "ㅂ",
    "ㅃ",
    "ㅅ",
    "ㅆ",
    "ㅇ",
    "ㅈ",
    "ㅉ",
    "ㅊ",
    "ㅋ",
    "ㅌ",
    "ㅍ",
    "ㅎ",
]
CHOSEONG_SET = set(CHOSEONG)
MASTER_URLS = {
    "kospi": "https://new.real.download.dws.co.kr/common/master/kospi_code.mst.zip",
    "kosdaq": "https://new.real.download.dws.co.kr/common/master/kosdaq_code.mst.zip",
    "sector": "https://new.real.download.dws.co.kr/common/master/idxcode.mst.zip",
    "theme": "https://new.real.download.dws.co.kr/common/master/theme_code.mst.zip",
}
MATCH_PRIORITY = {
    "ticker_exact": 0,
    "ticker_prefix": 1,
    "name_exact": 2,
    "name_prefix": 3,
    "initials_prefix": 4,
    "name_contains": 5,
    "initials_contains": 6,
}
KOSPI_WIDTHS = [
    2, 1, 4, 4, 4,
    1, 1, 1, 1, 1,
    1, 1, 1, 1, 1,
    1, 1, 1, 1, 1,
    1, 1, 1, 1, 1,
    1, 1, 1, 1, 1,
    1, 9, 5, 5, 1,
    1, 1, 2, 1, 1,
    1, 2, 2, 2, 3,
    1, 3, 12, 12, 8,
    15, 21, 2, 7, 1,
    1, 1, 1, 1, 9,
    9, 9, 5, 9, 8,
    9, 3, 1, 1, 1,
]
KOSPI_COLUMNS = [
    "그룹코드", "시가총액규모", "지수업종대분류", "지수업종중분류", "지수업종소분류",
    "제조업", "저유동성", "지배구조지수종목", "KOSPI200섹터업종", "KOSPI100",
    "KOSPI50", "KRX", "ETP", "ELW발행", "KRX100",
    "KRX자동차", "KRX반도체", "KRX바이오", "KRX은행", "SPAC",
    "KRX에너지화학", "KRX철강", "단기과열", "KRX미디어통신", "KRX건설",
    "Non1", "KRX증권", "KRX선박", "KRX섹터_보험", "KRX섹터_운송",
    "SRI", "기준가", "매매수량단위", "시간외수량단위", "거래정지",
    "정리매매", "관리종목", "시장경고", "경고예고", "불성실공시",
    "우회상장", "락구분", "액면변경", "증자구분", "증거금비율",
    "신용가능", "신용기간", "전일거래량", "액면가", "상장일자",
    "상장주수", "자본금", "결산월", "공모가", "우선주",
    "공매도과열", "이상급등", "KRX300", "KOSPI", "매출액",
    "영업이익", "경상이익", "당기순이익", "ROE", "기준년월",
    "시가총액", "그룹사코드", "회사신용한도초과", "담보대출가능", "대주가능",
]
KOSDAQ_WIDTHS = [
    2, 1,
    4, 4, 4, 1, 1,
    1, 1, 1, 1, 1,
    1, 1, 1, 1, 1,
    1, 1, 1, 1, 1,
    1, 1, 1, 1, 9,
    5, 5, 1, 1, 1,
    2, 1, 1, 1, 2,
    2, 2, 3, 1, 3,
    12, 12, 8, 15, 21,
    2, 7, 1, 1, 1,
    1, 9, 9, 9, 5,
    9, 8, 9, 3, 1,
    1, 1,
]
KOSDAQ_COLUMNS = [
    "증권그룹구분코드", "시가총액규모구분",
    "지수업종대분류", "지수업종중분류", "지수업종소분류", "벤처기업여부",
    "저유동성종목여부", "KRX종목여부", "ETP상품구분코드", "KRX100종목여부",
    "KRX자동차여부", "KRX반도체여부", "KRX바이오여부", "KRX은행여부", "기업인수목적회사여부",
    "KRX에너지화학여부", "KRX철강여부", "단기과열종목구분코드", "KRX미디어통신여부",
    "KRX건설여부", "투자주의환기종목여부", "KRX증권구분", "KRX선박구분",
    "KRX섹터보험여부", "KRX섹터운송여부", "KOSDAQ150지수여부", "주식기준가",
    "정규시장매매수량단위", "시간외시장매매수량단위", "거래정지여부", "정리매매여부",
    "관리종목여부", "시장경고구분코드", "시장경고위험예고여부", "불성실공시여부",
    "우회상장여부", "락구분코드", "액면가변경구분코드", "증자구분코드", "증거금비율",
    "신용주문가능여부", "신용기간", "전일거래량", "주식액면가", "주식상장일자", "상장주수",
    "자본금", "결산월", "공모가격", "우선주구분코드", "공매도과열종목여부",
    "이상급등종목여부", "KRX300종목여부", "매출액", "영업이익", "경상이익", "단기순이익",
    "ROE", "기준년월", "전일기준시가총액억", "그룹사코드", "회사신용한도초과여부", "담보대출가능여부", "대주가능여부",
]


def normalize_search_text(text: str) -> str:
    return re.sub(r"[^0-9A-Z가-힣ㄱ-ㅎㅏ-ㅣ]", "", (text or "").upper())


def extract_search_initials(text: str) -> str:
    chars: list[str] = []
    for char in (text or "").strip():
        if "가" <= char <= "힣":
            index = (ord(char) - ord("가")) // 588
            chars.append(CHOSEONG[index])
            continue
        if char in CHOSEONG_SET:
            chars.append(char)
            continue
        if char.isalnum():
            chars.append(char.upper())
    return "".join(chars)


def is_query_searchable(query: str) -> bool:
    normalized = normalize_search_text(query)
    if not normalized:
        return False
    if re.fullmatch(r"[A-Z0-9]+", normalized):
        return len(normalized) >= 1
    return len(normalized) >= 2


class StockMasterService:
    async def sync_master_data(self, db: AsyncSession) -> dict:
        sector_text, theme_text, kospi_text, kosdaq_text = await self._download_master_payloads()

        sector_map = self._parse_sector_master(sector_text)
        theme_links = self._parse_theme_master(theme_text)
        kospi_records = self._parse_equity_master(
            kospi_text,
            market="KOSPI",
            widths=KOSPI_WIDTHS,
            columns=KOSPI_COLUMNS,
            listed_at_key="상장일자",
            market_cap_key="시가총액",
            market_cap_multiplier=1,
            sector_map=sector_map,
        )
        kosdaq_records = self._parse_equity_master(
            kosdaq_text,
            market="KOSDAQ",
            widths=KOSDAQ_WIDTHS,
            columns=KOSDAQ_COLUMNS,
            listed_at_key="주식상장일자",
            market_cap_key="전일기준시가총액억",
            market_cap_multiplier=100_000_000,
            sector_map=sector_map,
        )

        merged_records = {record["ticker"]: record for record in [*kospi_records, *kosdaq_records]}
        available_tickers = set(merged_records.keys())
        stock_rows = [StockMaster(**record) for record in merged_records.values()]

        dedup_theme_keys: set[tuple[str, str]] = set()
        theme_rows: list[StockThemeMap] = []
        for item in theme_links:
            key = (item["stock_ticker"], item["theme_code"])
            if item["stock_ticker"] not in available_tickers or key in dedup_theme_keys:
                continue
            dedup_theme_keys.add(key)
            theme_rows.append(StockThemeMap(**item))

        await db.execute(delete(StockThemeMap))
        await db.execute(delete(StockMaster))
        db.add_all(stock_rows)
        db.add_all(theme_rows)
        await db.commit()

        return {
            "kospi_count": len(kospi_records),
            "kosdaq_count": len(kosdaq_records),
            "theme_links": len(theme_rows),
            "updated_at": datetime.now().isoformat(),
        }

    async def is_master_ready(self, db: AsyncSession) -> bool:
        count = await db.scalar(select(func.count(StockMaster.id)))
        return (count or 0) > 0

    async def search_stocks(self, db: AsyncSession, query: str, limit: int = 10) -> tuple[bool, list[StockSearchSuggestion]]:
        master_ready = await self.is_master_ready(db)
        if not master_ready or not is_query_searchable(query):
            return master_ready, []

        stripped_query = (query or "").strip()
        normalized_query = normalize_search_text(stripped_query)
        ticker_query = re.sub(r"[^A-Z0-9]", "", stripped_query.upper())
        initials_query = extract_search_initials(stripped_query)

        conditions = []
        if ticker_query:
            conditions.append(StockMaster.ticker.startswith(ticker_query))
        if normalized_query:
            conditions.append(StockMaster.search_name.contains(normalized_query))
        if initials_query:
            conditions.append(StockMaster.search_initials.contains(initials_query))

        result = await db.execute(
            select(StockMaster)
            .where(or_(*conditions))
            .limit(max(limit * 10, 50))
        )
        candidates = result.scalars().all()

        ranked: list[tuple[int, int, str, str, StockSearchSuggestion]] = []
        for stock in candidates:
            match_type = self._detect_match_type(stock, stripped_query, normalized_query, ticker_query, initials_query)
            if not match_type:
                continue
            ranked.append(
                (
                    MATCH_PRIORITY[match_type],
                    -(stock.market_cap or 0),
                    stock.name,
                    stock.ticker,
                    self._to_suggestion(stock, match_type),
                )
            )

        ranked.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
        return master_ready, [item[-1] for item in ranked[:limit]]

    async def get_stock_profile(self, db: AsyncSession, ticker: str) -> StockProfileResponse | None:
        normalized_ticker = ticker.upper()
        stock = await db.scalar(select(StockMaster).where(StockMaster.ticker == normalized_ticker))

        if stock is None:
            return await self._build_fallback_profile(db, normalized_ticker)

        current_price = None
        if not stock.industry_name:
            current_price = await kis_price_service.get_current_price(normalized_ticker)

        themes_result = await db.execute(
            select(StockThemeMap)
            .where(StockThemeMap.stock_ticker == normalized_ticker)
            .order_by(StockThemeMap.theme_name.asc())
        )
        theme_rows = themes_result.scalars().all()
        theme_entries = [StockTheme(code=row.theme_code, name=row.theme_name) for row in theme_rows]

        related_by_sector = await self._build_related_by_sector(db, stock, limit=8)
        related_by_theme = await self._build_related_by_theme(db, theme_entries, exclude_ticker=normalized_ticker)

        return StockProfileResponse(
            ticker=stock.ticker,
            name=stock.name,
            market=stock.market,
            sector=stock.sector_name,
            industry=stock.industry_name or (current_price or {}).get("industry_name"),
            themes=theme_entries,
            related_by_sector=related_by_sector,
            related_by_theme=related_by_theme,
        )

    async def _build_fallback_profile(self, db: AsyncSession, ticker: str) -> StockProfileResponse | None:
        stock = await db.scalar(select(Stock).where(Stock.ticker == ticker))
        current_price = await kis_price_service.get_current_price(ticker)
        if stock is None and current_price is None:
            return None

        return StockProfileResponse(
            ticker=ticker,
            name=(current_price or {}).get("name") or (stock.name if stock else ticker),
            market=(current_price or {}).get("market") or (stock.market if stock else None),
            sector=stock.sector if stock else None,
            industry=(stock.industry if stock else None) or (current_price or {}).get("industry_name"),
            themes=[],
            related_by_sector=[],
            related_by_theme=[],
        )

    async def _build_related_by_sector(
        self,
        db: AsyncSession,
        stock: StockMaster,
        limit: int,
    ) -> list[StockSearchSuggestion]:
        if stock.industry_name:
            condition = StockMaster.industry_name == stock.industry_name
        elif stock.sector_name:
            condition = StockMaster.sector_name == stock.sector_name
        else:
            return []

        result = await db.execute(
            select(StockMaster)
            .where(
                condition,
                StockMaster.ticker != stock.ticker,
            )
            .order_by(StockMaster.market_cap.desc(), StockMaster.name.asc(), StockMaster.ticker.asc())
            .limit(limit)
        )
        return [self._to_suggestion(item, "name_contains") for item in result.scalars().all()]

    async def _build_related_by_theme(
        self,
        db: AsyncSession,
        themes: list[StockTheme],
        *,
        exclude_ticker: str,
    ) -> list[RelatedThemeGroup]:
        groups: list[RelatedThemeGroup] = []
        for theme in themes[:3]:
            result = await db.execute(
                select(StockMaster, StockThemeMap)
                .join(StockThemeMap, StockThemeMap.stock_ticker == StockMaster.ticker)
                .where(
                    StockThemeMap.theme_code == theme.code,
                    StockMaster.ticker != exclude_ticker,
                )
                .order_by(StockMaster.market_cap.desc(), StockMaster.name.asc(), StockMaster.ticker.asc())
                .limit(6)
            )
            stocks = [self._to_suggestion(row[0], "name_contains") for row in result.all()]
            groups.append(
                RelatedThemeGroup(
                    theme_code=theme.code,
                    theme_name=theme.name,
                    stocks=stocks,
                )
            )
        return groups

    async def _download_master_payloads(self) -> tuple[str, str, str, str]:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            sector_response, theme_response, kospi_response, kosdaq_response = await self._gather_downloads(client)
            for response in (sector_response, theme_response, kospi_response, kosdaq_response):
                response.raise_for_status()
        return (
            self._extract_zip_text(sector_response.content),
            self._extract_zip_text(theme_response.content),
            self._extract_zip_text(kospi_response.content),
            self._extract_zip_text(kosdaq_response.content),
        )

    async def _gather_downloads(self, client: httpx.AsyncClient):
        return await asyncio.gather(
            client.get(MASTER_URLS["sector"]),
            client.get(MASTER_URLS["theme"]),
            client.get(MASTER_URLS["kospi"]),
            client.get(MASTER_URLS["kosdaq"]),
        )

    def _extract_zip_text(self, payload: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = [name for name in archive.namelist() if not name.endswith("/") and not name.startswith("__MACOSX")]
            target_name = next((name for name in names if name.lower().endswith(".mst")), names[0])
            with archive.open(target_name) as source:
                return source.read().decode("cp949", errors="ignore")

    def _parse_sector_master(self, text: str) -> dict[str, str]:
        sector_map: dict[str, str] = {}
        for row in text.splitlines():
            if not row.strip():
                continue
            code = row[1:5].strip()
            name = row[5:45].strip()
            if code and name:
                sector_map[code] = name
        return sector_map

    def _parse_theme_master(self, text: str) -> list[dict]:
        rows: list[dict] = []
        for line in text.splitlines():
            if not line.strip():
                continue
            theme_code = line[0:3].strip()
            stock_ticker = line[-10:].strip()
            theme_name = line[3:-10].strip()
            stock_ticker = re.sub(r"[^A-Z0-9]", "", stock_ticker.upper())
            if not theme_code or not stock_ticker or not theme_name:
                continue
            rows.append(
                {
                    "stock_ticker": stock_ticker,
                    "theme_code": theme_code,
                    "theme_name": theme_name,
                }
            )
        return rows

    def _parse_equity_master(
        self,
        text: str,
        *,
        market: str,
        widths: list[int],
        columns: list[str],
        listed_at_key: str,
        market_cap_key: str,
        market_cap_multiplier: int,
        sector_map: dict[str, str],
    ) -> list[dict]:
        split_rows = [row.rstrip("\n") for row in text.splitlines() if row.strip()]
        tail_length = sum(widths)
        head_rows: list[list[str]] = []
        tail_rows: list[str] = []

        for row in split_rows:
            head = row[: len(row) - tail_length]
            tail = row[-tail_length:]
            head_rows.append([head[0:9].strip(), head[9:21].strip(), head[21:].strip()])
            tail_rows.append(tail)

        head_df = pd.DataFrame(head_rows, columns=["ticker", "standard_code", "name"])
        tail_df = pd.read_fwf(io.StringIO("\n".join(tail_rows)), widths=widths, names=columns, dtype=str).fillna("")
        merged = pd.concat([head_df.reset_index(drop=True), tail_df.reset_index(drop=True)], axis=1)

        records: list[dict] = []
        for row in merged.to_dict("records"):
            ticker = re.sub(r"[^A-Z0-9]", "", str(row.get("ticker", "")).upper())
            name = str(row.get("name", "")).strip()
            if not ticker or not name:
                continue

            large_code = self._clean_code(row.get("지수업종대분류"))
            medium_code = self._clean_code(row.get("지수업종중분류"))
            small_code = self._clean_code(row.get("지수업종소분류"))
            sector_code = large_code or medium_code or None
            industry_code = small_code or medium_code or large_code or None
            sector_name = sector_map.get(large_code or "", "") or sector_map.get(medium_code or "", "") or None
            industry_name = (
                sector_map.get(small_code or "", "")
                or sector_map.get(medium_code or "", "")
                or sector_name
            )

            records.append(
                {
                    "ticker": ticker,
                    "standard_code": str(row.get("standard_code", "")).strip() or None,
                    "name": name,
                    "market": market,
                    "sector_code": sector_code,
                    "sector_name": sector_name,
                    "industry_code": industry_code,
                    "industry_name": industry_name,
                    "market_cap": self._parse_int(row.get(market_cap_key), multiplier=market_cap_multiplier),
                    "listed_at": self._parse_date(row.get(listed_at_key)),
                    "search_name": normalize_search_text(name),
                    "search_initials": extract_search_initials(name),
                }
            )
        return records

    def _detect_match_type(
        self,
        stock: StockMaster,
        raw_query: str,
        normalized_query: str,
        ticker_query: str,
        initials_query: str,
    ) -> str | None:
        if ticker_query and stock.ticker == ticker_query:
            return "ticker_exact"
        if ticker_query and stock.ticker.startswith(ticker_query):
            return "ticker_prefix"

        stripped_name = (stock.name or "").strip()
        if raw_query and stripped_name == raw_query:
            return "name_exact"
        if normalized_query and stock.search_name == normalized_query:
            return "name_exact"
        if normalized_query and stock.search_name.startswith(normalized_query):
            return "name_prefix"
        if initials_query and stock.search_initials.startswith(initials_query):
            return "initials_prefix"
        if normalized_query and normalized_query in stock.search_name:
            return "name_contains"
        if initials_query and initials_query in stock.search_initials:
            return "initials_contains"
        return None

    def _to_suggestion(self, stock: StockMaster, match_type: str) -> StockSearchSuggestion:
        return StockSearchSuggestion(
            ticker=stock.ticker,
            name=stock.name,
            market=stock.market,
            sector=stock.sector_name,
            industry=stock.industry_name,
            match_type=match_type,  # type: ignore[arg-type]
        )

    def _clean_code(self, value: object) -> str | None:
        code = re.sub(r"[^0-9A-Z]", "", str(value or "").strip())
        return code or None

    def _parse_int(self, value: object, *, multiplier: int = 1) -> int:
        digits = re.sub(r"[^0-9]", "", str(value or ""))
        if not digits:
            return 0
        return int(digits) * multiplier

    def _parse_date(self, value: object) -> date | None:
        digits = re.sub(r"[^0-9]", "", str(value or ""))
        if len(digits) != 8:
            return None
        try:
            return date.fromisoformat(f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}")
        except ValueError:
            return None


stock_master_service = StockMasterService()
