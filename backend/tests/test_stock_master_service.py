from types import SimpleNamespace

import pytest

from app.models.stock_master import StockMaster, StockThemeMap
from app.services.stock_master_service import (
    KOSDAQ_COLUMNS,
    KOSDAQ_WIDTHS,
    KOSPI_COLUMNS,
    KOSPI_WIDTHS,
    StockMasterService,
    extract_search_initials,
    stock_master_service,
)


class FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return FakeScalarResult(self._rows)

    def all(self):
        return self._rows


class FakeSearchDB:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _statement):
        return FakeExecuteResult(self.rows)


class FakeSyncDB:
    def __init__(self):
        self.executed = []
        self.added = []
        self.committed = False

    async def execute(self, statement):
        self.executed.append(statement)
        return None

    def add_all(self, rows):
        self.added.extend(rows)

    async def commit(self):
        self.committed = True


class FakeScalarSequenceDB:
    def __init__(self, results):
        self._results = list(results)

    async def scalar(self, _statement):
        if not self._results:
            return None
        return self._results.pop(0)

    async def execute(self, _statement):
        return FakeExecuteResult([])


def _build_fixed_width_tail(columns, widths, values):
    return "".join(str(values.get(column, "")).ljust(width)[:width] for column, width in zip(columns, widths))


def _build_equity_row(ticker, standard_code, name, columns, widths, values):
    head = f"{ticker:<9}{standard_code:<12}{name}"
    return head + _build_fixed_width_tail(columns, widths, values)


@pytest.mark.asyncio
async def test_extract_search_initials_supports_hangul_and_mixed_text():
    """한글 초성과 영문/숫자 혼합 검색키가 안정적으로 생성되는지 확인한다."""

    result = extract_search_initials("삼성전자 a1")

    print("\n[초성 추출 테스트] 입력: 삼성전자 a1")
    print("[초성 추출 테스트] 결과:", result)

    assert result == "ㅅㅅㅈㅈA1"
    assert extract_search_initials("ㅅㅅㅈㅈ") == "ㅅㅅㅈㅈ"


@pytest.mark.asyncio
async def test_search_stocks_ranks_exact_and_prefix_matches(monkeypatch):
    """검색 결과는 exact/prefix 우선순위와 시총 정렬을 함께 만족해야 한다."""

    service = StockMasterService()
    rows = [
        SimpleNamespace(
            ticker="005930",
            name="삼성전자",
            market="KOSPI",
            sector_name="전기전자",
            industry_name="반도체",
            market_cap=500,
            search_name="삼성전자",
            search_initials="ㅅㅅㅈㅈ",
        ),
        SimpleNamespace(
            ticker="005935",
            name="삼성전자우",
            market="KOSPI",
            sector_name="전기전자",
            industry_name="반도체",
            market_cap=300,
            search_name="삼성전자우",
            search_initials="ㅅㅅㅈㅈㅇ",
        ),
        SimpleNamespace(
            ticker="009150",
            name="삼양홀딩스",
            market="KOSPI",
            sector_name="화학",
            industry_name="지주",
            market_cap=200,
            search_name="삼양홀딩스",
            search_initials="ㅅㅇㅎㄷㅅ",
        ),
    ]

    async def fake_is_master_ready(_db):
        return True

    monkeypatch.setattr(service, "is_master_ready", fake_is_master_ready)

    master_ready, suggestions = await service.search_stocks(FakeSearchDB(rows), "삼성전자", limit=10)

    print("\n[검색 랭킹 테스트] master_ready:", master_ready)
    print("[검색 랭킹 테스트] 결과:", [(item.ticker, item.match_type) for item in suggestions])

    assert master_ready is True
    assert suggestions[0].ticker == "005930"
    assert suggestions[0].match_type == "name_exact"
    assert suggestions[1].ticker == "005935"
    assert suggestions[1].match_type == "name_prefix"


@pytest.mark.asyncio
async def test_sync_master_data_builds_stock_master_and_theme_rows(monkeypatch):
    """마스터 동기화는 종목/테마 데이터를 새 테이블 구조로 적재해야 한다."""

    service = StockMasterService()
    db = FakeSyncDB()

    sector_text = "\n".join([
        "A1001에너지",
        "A1002화학",
        "A1003정유",
        "A2001IT서비스",
        "A2002소프트웨어",
        "A2003플랫폼",
    ])
    theme_text = "\n".join([
        "0272018 신규 상장주                        010950   ",
        "113AI 플랫폼                              123456   ",
    ])
    kospi_text = _build_equity_row(
        "010950",
        "KR7010950004",
        "S-OIL",
        KOSPI_COLUMNS,
        KOSPI_WIDTHS,
        {
            "지수업종대분류": "1001",
            "지수업종중분류": "1002",
            "지수업종소분류": "1003",
            "상장일자": "19760507",
            "시가총액": "123456789",
        },
    )
    kosdaq_text = _build_equity_row(
        "123456",
        "KR7123456000",
        "테스트소프트",
        KOSDAQ_COLUMNS,
        KOSDAQ_WIDTHS,
        {
            "지수업종대분류": "2001",
            "지수업종중분류": "2002",
            "지수업종소분류": "2003",
            "주식상장일자": "20200102",
            "전일기준시가총액억": "321",
        },
    )

    async def fake_download_master_payloads():
        return sector_text, theme_text, kospi_text, kosdaq_text

    monkeypatch.setattr(service, "_download_master_payloads", fake_download_master_payloads)

    result = await service.sync_master_data(db)

    stock_rows = [row for row in db.added if isinstance(row, StockMaster)]
    theme_rows = [row for row in db.added if isinstance(row, StockThemeMap)]

    print("\n[마스터 동기화 테스트] 종목 수:", len(stock_rows))
    print("[마스터 동기화 테스트] 테마 매핑 수:", len(theme_rows))
    print("[마스터 동기화 테스트] 첫 종목:", stock_rows[0].ticker, stock_rows[0].sector_name, stock_rows[0].industry_name)

    assert db.committed is True
    assert result["kospi_count"] == 1
    assert result["kosdaq_count"] == 1
    assert len(stock_rows) == 2
    assert len(theme_rows) == 2
    assert stock_rows[0].search_initials
    assert any(row.ticker == "010950" and row.sector_name == "에너지" and row.industry_name == "정유" for row in stock_rows)


@pytest.mark.asyncio
async def test_get_stock_profile_falls_back_to_price_service(monkeypatch):
    """마스터 미적재 종목도 현재가 API fallback으로 최소 프로필을 반환해야 한다."""

    db = FakeScalarSequenceDB([
        None,
        SimpleNamespace(
            ticker="005930",
            name="삼성전자",
            market="KOSPI",
            sector="전기전자",
            industry=None,
        ),
    ])

    async def fake_get_current_price(_ticker):
        return {
            "name": "삼성전자",
            "market": "KOSPI",
            "industry_name": "반도체",
        }

    monkeypatch.setattr("app.services.stock_master_service.kis_price_service.get_current_price", fake_get_current_price)

    profile = await stock_master_service.get_stock_profile(db, "005930")

    print("\n[프로필 fallback 테스트] ticker:", profile.ticker if profile else None)
    print("[프로필 fallback 테스트] industry:", profile.industry if profile else None)

    assert profile is not None
    assert profile.ticker == "005930"
    assert profile.industry == "반도체"
    assert profile.related_by_sector == []
