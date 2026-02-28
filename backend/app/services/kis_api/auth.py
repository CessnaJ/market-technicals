import httpx
from typing import Optional
from app.core.config import settings
from app.core.redis_client import redis_client
import logging

logger = logging.getLogger(__name__)


class KISAuth:
    """KIS API OAuth authentication handler"""

    def __init__(self):
        self.app_key = settings.KIS_APP_KEY
        self.app_secret = settings.KIS_APP_SECRET
        self.base_url = settings.KIS_BASE_URL

    async def get_access_token(self) -> Optional[str]:
        """
        Get access token from cache or request new one
        """
        cache_key = "kis:access_token"

        # Try to get from cache
        cached_token = await redis_client.get(cache_key)
        if cached_token:
            return cached_token

        # Request new token
        token = await self._request_token()
        if token:
            # Cache for 23 hours (token expires in 24 hours)
            await redis_client.set(cache_key, token, expire=82800)
            return token

        return None

    async def _request_token(self) -> Optional[str]:
        """
        Request new access token from KIS API
        """
        url = f"{self.base_url}/oauth2/tokenP"
        headers = {
            "Content-Type": "application/json",
        }
        data = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }

        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.post(url, json=data, headers=headers, timeout=10.0)
                response.raise_for_status()
                result = response.json()

                access_token = result.get("access_token")
                if access_token:
                    logger.info("🔑 KIS 액세스 토큰 발급 성공")
                    return access_token
                else:
                    logger.error(f"❌ 토큰 응답 오류: {result}")
                    return None

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ 토큰 요청 HTTP 오류: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ KIS 토큰 요청 실패: {e}")
            return None

    async def invalidate_token(self):
        """Invalidate cached token"""
        cache_key = "kis:access_token"
        await redis_client.delete(cache_key)
        logger.info("🗑️ KIS 액세스 토큰 삭제 완료")


# Global auth instance
kis_auth = KISAuth()
