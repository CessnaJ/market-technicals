from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
from app.services.kis_api.client import kis_client
from app.core.redis_client import redis_client
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class KISPriceService:
    """KIS API price data fetch service"""

    # KIS API endpoints
    ENDPOINTS = {
        "daily_price": {
            "path": "/uapi/domestic-stock/v1/quotations/inquire-daily-price",
            "tr_id": "FHKST01010400",
        },
        "current_price": {
            "path": "/uapi/domestic-stock/v1/quotations/inquire-price",
            "tr_id": "FHKST01010100",
        },
    }

    async def get_daily_price(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        use_cache: bool = True,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch daily OHLCV data for a stock

        Args:
            ticker: Stock ticker (e.g., "010950")
            start_date: Start date (default: 100 days ago)
            end_date: End date (default: today)
            use_cache: Whether to use cached data

        Returns:
            List of OHLCV data points
        """
        cache_key = f"kis:daily_price:{ticker}:{start_date}:{end_date}"

        # Try cache first
        if use_cache:
            cached_data = await redis_client.get_json(cache_key)
            if cached_data:
                logger.info(f"🐤 [{ticker}] 캐시 적중 - 일봉 데이터")
                return cached_data

        # Set default dates (1 year by default)
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=365)

        # Format dates for KIS API (YYYYMMDD)
        end_date_str = end_date.strftime("%Y%m%d")
        start_date_str = start_date.strftime("%Y%m%d")

        endpoint = self.ENDPOINTS["daily_price"]
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # J: 전체
            "FID_INPUT_ISCD": ticker,  # 종목코드
            "FID_INPUT_DATE_1": start_date_str,  # 조회시작일
            "FID_INPUT_DATE_2": end_date_str,  # 조회종료일
            "FID_PERIOD_DIV_CODE": "D",  # D: 일봉
            "FID_ORG_ADJ_PRC": "1",  # 0: 수정주가, 1: 원주가
        }

        try:
            # Use tr_cont for pagination (fetch more than 100 records)
            all_data = []
            tr_cont = ""
            
            while True:
                headers = {}
                if tr_cont:
                    headers["tr_cont"] = tr_cont
                    
                response = await kis_client.get(
                    endpoint["path"],
                    params=params,
                    tr_id=endpoint["tr_id"],
                    extra_headers=headers if headers else None,
                )

                logger.info(f"🐤 [{ticker}] KIS API 응답 수신")

                if response and "output" in response:
                    data = response["output"]
                    # Parse and format data
                    ohlcv_data = self._parse_daily_price(data)
                    all_data.extend(ohlcv_data)
                    logger.info(f"🐤 [{ticker}] {len(ohlcv_data)}건 수집 (누적: {len(all_data)}건)")
                    
                    # Check if there's more data (tr_cont in response header)
                    if response.get("tr_cont"):
                        tr_cont = response["tr_cont"]
                        logger.info(f"🐤 [{ticker}] 추가 데이터 수집 중...")
                    else:
                        logger.info(f"🐤 [{ticker}] 모든 데이터 수집 완료")
                        break
                else:
                    logger.error(f"❌ [{ticker}] 예상치 못한 응답: {response}")
                    break

            # Cache the result
            if use_cache and all_data:
                await redis_client.set_json(
                    cache_key,
                    all_data,
                    expire=settings.CACHE_TTL_HISTORICAL,
                )

            return all_data

        except Exception as e:
            logger.error(f"❌ [{ticker}] 일봉 데이터 수집 실패: {e}")
            return None

    def _parse_daily_price(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse KIS API daily price response

        KIS API response format:
        - stck_bsop_date: 영업일자
        - stck_oprc: 시가
        - stck_hgpr: 고가
        - stck_lwpr: 저가
        - stck_clpr: 종가
        - stck_vol: 거래량
        """
        parsed_data = []

        for item in data:
            try:
                # Parse date (YYYYMMDD -> YYYY-MM-DD)
                date_str = item.get("stck_bsop_date", "")
                if len(date_str) == 8:
                    parsed_date = datetime.strptime(date_str, "%Y%m%d").date()
                else:
                    continue

                parsed_data.append({
                    "date": parsed_date.isoformat(),
                    "open": float(item.get("stck_oprc", 0)),
                    "high": float(item.get("stck_hgpr", 0)),
                    "low": float(item.get("stck_lwpr", 0)),
                    "close": float(item.get("stck_clpr", 0)),
                    "volume": int(item.get("stck_vol", 0)),
                })
            except (ValueError, KeyError) as e:
                logger.warning(f"⚠️ 가격 데이터 파싱 오류: {e}")
                continue

        # Sort by date ascending
        parsed_data.sort(key=lambda x: x["date"])
        return parsed_data

    async def get_current_price(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch current price and basic info for a stock

        Args:
            ticker: Stock ticker

        Returns:
            Current price data
        """
        cache_key = f"kis:current_price:{ticker}"

        # Try cache first (short TTL)
        cached_data = await redis_client.get_json(cache_key)
        if cached_data:
            return cached_data

        endpoint = self.ENDPOINTS["current_price"]
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
        }

        try:
            response = await kis_client.get(
                endpoint["path"],
                params=params,
                tr_id=endpoint["tr_id"],
            )

            if response and "output" in response:
                logger.info(f"🐤 [{ticker}] KIS API 응답 수신")
                output = response["output"]
                # KIS API returns output as a dict (single object) or array
                if isinstance(output, dict):
                    data = output
                elif isinstance(output, list) and len(output) > 0:
                    data = output[0]
                else:
                    logger.error(f"❌ [{ticker}] 빈 응답: {response}")
                    return None
                parsed_data = self._parse_current_price(data)

                # Cache with short TTL
                await redis_client.set_json(
                    cache_key,
                    parsed_data,
                    expire=settings.CACHE_TTL_CURRENT,
                )

                return parsed_data
            else:
                logger.error(f"❌ [{ticker}] 현재가 응답 오류: {response}")
                return None

        except Exception as e:
            logger.error(f"❌ [{ticker}] 현재가 조회 실패: {e}")
            return None

    def _parse_current_price(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse KIS API current price response

        KIS API response format:
        - stck_prpr: 현재가
        - stck_hgpr: 고가
        - stck_lwpr: 저가
        - stck_oprc: 시가
        - stck_vol: 거래량
        - prdy_vrss: 전일대비
        - prdy_vrss_sign: 전일대비부호 (+, -)
        - prdy_ctrt: 전일대비율
        """
        return {
            "ticker": data.get("stck_shrn_iscd", ""),
            "name": data.get("hts_kor_isnm", ""),
            "current_price": float(data.get("stck_prpr", 0)),
            "high": float(data.get("stck_hgpr", 0)),
            "low": float(data.get("stck_lwpr", 0)),
            "open": float(data.get("stck_oprc", 0)),
            "volume": int(data.get("stck_vol", 0)),
            "change": float(data.get("prdy_vrss", 0)),
            "change_sign": data.get("prdy_vrss_sign", ""),
            "change_rate": float(data.get("prdy_ctrt", 0)),
            "market": data.get("mrkt_clss", ""),
        }

    async def fetch_historical_data(
        self,
        ticker: str,
        days: int = 1000,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch historical data with pagination (max 100 days per request)
        Note: Using tr_cont for automatic pagination now

        Args:
            ticker: Stock ticker
            days: Number of days to fetch

        Returns:
            List of OHLCV data points
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Use get_daily_price with tr_cont support
        data = await self.get_daily_price(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            use_cache=False,  # Don't use cache for historical fetch
        )

        if data:
            # Remove duplicates and sort
            unique_data = {item["date"]: item for item in data}
            sorted_data = sorted(unique_data.values(), key=lambda x: x["date"])
            return sorted_data

        return None


# Global price service instance
kis_price_service = KISPriceService()
