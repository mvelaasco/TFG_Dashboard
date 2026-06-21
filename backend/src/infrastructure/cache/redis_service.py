import redis.asyncio as aioredis

from core.config import settings


class AsyncRedisCacheService:

    def __init__(self) -> None:
        self._client = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
        )

    async def acquire_lock(self, key: str, expire_seconds: int = 60) -> bool:
        acquired = await self._client.setnx(key, "1")
        if acquired:
            await self._client.expire(key, expire_seconds)
        return acquired

    async def release_lock(self, key: str) -> None:
        await self._client.delete(key)

    async def increment_counter(self, key: str, expire_seconds: int = 3600) -> int:
        val = await self._client.incr(key)
        if val == 1:
            await self._client.expire(key, expire_seconds)
        return val

    async def get_counter(self, key: str) -> int:
        val = await self._client.get(key)
        return int(val) if val is not None else 0

    async def close(self) -> None:
        await self._client.close()
