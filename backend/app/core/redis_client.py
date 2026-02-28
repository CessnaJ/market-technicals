import redis.asyncio as redis
from redis.asyncio import Redis
from app.core.config import settings
import json
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client wrapper"""

    def __init__(self):
        self._client: Optional[Redis] = None

    async def connect(self) -> Redis:
        """Create and return Redis connection"""
        if self._client is None:
            # Parse REDIS_URL to extract password if needed
            redis_url = settings.REDIS_URL
            self._client = await redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                health_check_interval=30,
            )
        return self._client

    async def disconnect(self):
        """Close Redis connection"""
        if self._client:
            await self._client.close()
            self._client = None

    async def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        client = await self.connect()
        try:
            return await client.get(key)
        except Exception as e:
            logger.error(f"❌ Redis GET 오류 (key: {key}): {e}")
            return None

    async def set(
        self,
        key: str,
        value: str,
        expire: Optional[int] = None
    ) -> bool:
        """Set value with optional expiration"""
        client = await self.connect()
        try:
            await client.set(key, value, ex=expire)
            return True
        except Exception as e:
            logger.error(f"❌ Redis SET 오류 (key: {key}): {e}")
            return False

    async def get_json(self, key: str) -> Optional[Any]:
        """Get JSON value by key"""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError as e:
                logger.error(f"❌ Redis JSON 디코딩 오류 (key: {key}): {e}")
        return None

    async def set_json(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None
    ) -> bool:
        """Set JSON value with optional expiration"""
        try:
            json_value = json.dumps(value, ensure_ascii=False)
            return await self.set(key, json_value, expire)
        except Exception as e:
            logger.error(f"❌ Redis JSON 저장 오류 (key: {key}): {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key"""
        client = await self.connect()
        try:
            await client.delete(key)
            return True
        except Exception as e:
            logger.error(f"❌ Redis DELETE 오류 (key: {key}): {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        client = await self.connect()
        try:
            return await client.exists(key) > 0
        except Exception as e:
            logger.error(f"❌ Redis EXISTS 오류 (key: {key}): {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        client = await self.connect()
        try:
            keys = await client.keys(pattern)
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"❌ Redis 패턴 삭제 오류 (pattern: {pattern}): {e}")
            return 0


# Global Redis client instance
redis_client = RedisClient()
