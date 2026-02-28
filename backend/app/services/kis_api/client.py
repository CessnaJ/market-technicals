import httpx
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.services.kis_api.auth import kis_auth
import logging
import asyncio

logger = logging.getLogger(__name__)


class KISAPIClient:
    """KIS API HTTP client with rate limiting and retry logic"""

    def __init__(self):
        self.base_url = settings.KIS_BASE_URL
        self.app_key = settings.KIS_APP_KEY
        self.app_secret = settings.KIS_APP_SECRET
        self.account_no = settings.KIS_ACCOUNT_NO
        self.rate_limit = settings.KIS_RATE_LIMIT
        self.retry_count = settings.KIS_RETRY_COUNT
        self.retry_delay = settings.KIS_RETRY_DELAY
        self._semaphore = asyncio.Semaphore(self.rate_limit)

    async def _get_headers(self) -> Dict[str, str]:
        """Get headers with authorization token"""
        token = await kis_auth.get_access_token()
        if not token:
            raise Exception("Failed to get KIS access token")

        return {
            "Content-Type": "application/json",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "custtype": "P",  # P: 일반(개인고객,법인고객), B: 제휴사
        }

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        tr_id: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Make API request with rate limiting and retry logic
        """
        url = f"{self.base_url}{path}"
        headers = await self._get_headers()

        if tr_id:
            headers["tr_id"] = tr_id
        
        # Add extra headers (e.g., tr_cont for pagination)
        if extra_headers:
            headers.update(extra_headers)

        async with self._semaphore:
            for attempt in range(self.retry_count):
                try:
                    async with httpx.AsyncClient(verify=False) as client:
                        if method == "GET":
                            response = await client.get(
                                url, headers=headers, params=params, timeout=30.0
                            )
                        elif method == "POST":
                            response = await client.post(
                                url, headers=headers, json=data, timeout=30.0
                            )
                        else:
                            raise ValueError(f"Unsupported method: {method}")

                        response.raise_for_status()
                        return response.json()

                except httpx.HTTPStatusError as e:
                    logger.error(f"HTTP error on attempt {attempt + 1}: {e}")
                    if e.response.status_code == 401:
                        # Token expired, invalidate and retry
                        await kis_auth.invalidate_token()
                        headers = await self._get_headers()
                    if attempt < self.retry_count - 1:
                        await asyncio.sleep(self.retry_delay * (2 ** attempt))
                    else:
                        raise

                except Exception as e:
                    logger.error(f"Error on attempt {attempt + 1}: {e}")
                    if attempt < self.retry_count - 1:
                        await asyncio.sleep(self.retry_delay * (2 ** attempt))
                    else:
                        raise

        return None

    async def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        tr_id: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """GET request"""
        return await self._request("GET", path, params=params, tr_id=tr_id, extra_headers=extra_headers)

    async def post(
        self,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        tr_id: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """POST request"""
        return await self._request("POST", path, data=data, tr_id=tr_id, extra_headers=extra_headers)


# Global API client instance
kis_client = KISAPIClient()
