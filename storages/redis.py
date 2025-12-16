import json
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, List, Optional, Union

import redis
import redis.asyncio as async_redis
from redis.exceptions import ConnectionError as RedisConnectionError

from protocols.storage_provider import IStorageProvider
from utils.cache_types import _CacheValue


class RedisStorage(IStorageProvider):
    """Persistent storage implementation using Redis. Supports synchronous and asynchronous operations for flexibility
    in hybrid contexts.

    This class manages dual connections (Sync/Async) to allow usage
    in different parts of the application without duplicating configuration logic.
    """

    def __init__(
        self,
        connection_string: str,
        db: int = 0,
        **extra_options: Any,
    ) -> None:
        """Initializes the Redis storage provider.

        Warning: This constructor performs a ping operation to verify connection,
        which may cause blocking during initialization.

        Args:
            connection_string (str): The Redis connection URI (e.g., redis://localhost:6379).
            db (int): Redis database index. Default: 0 (Acts as 'cacheado_cache_db').
            **extra_options: Additional options passed directly to the Redis client.

        Raises:
            ConnectionError: If unable to establish a connection to the Redis server.
        """
        self._sync_client = redis.from_url(connection_string, db=db, decode_responses=True, **extra_options)

        try:
            self._sync_client.ping()
        except RedisConnectionError as e:
            raise ConnectionError(f"Could not connect to Redis server: {e}")

        self._async_client: async_redis.Redis = async_redis.from_url(
            connection_string, db=db, decode_responses=True, **extra_options
        )  # type: ignore[assignment]

    @asynccontextmanager
    async def get_async_client(self) -> AsyncGenerator[async_redis.Redis, None]:  # type: ignore[type-arg]
        """Context manager to get the asynchronous Redis client.

        Yields:
            redis.asyncio.Redis: The client instance ready for awaitable operations.
        """
        try:
            yield self._async_client
        finally:
            pass

    def get_sync_client(self) -> redis.Redis:  # type: ignore[type-arg]
        """
        Gets the direct instance of the synchronous client.

        Returns:
            redis.Redis: The Redis client.
        """
        return self._sync_client  # type: ignore[no-any-return]

    def set(self, key: str, value: Any, ttl_seconds: Union[int, float]) -> None:
        """Stores a value in the cache. Synchronous operation (blocking).

        Args:
            key (str): The unique key.
            value (Any): The value to be stored (must be JSON serializable).
            ttl_seconds (Union[int, float]): Time in seconds until expiration.
        """
        client = self.get_sync_client()
        client.set(key, json.dumps({"value": value, "ttl_seconds": time.monotonic() + ttl_seconds}))

    def get(self, key: str) -> Optional[_CacheValue]:
        """Retrieves a value from the cache atomically. Synchronous operation (blocking).

        Args:
            key (str): The key to retrieve.

        Returns:
            Optional[_CacheValue]: Tuple (value, expiry) or None.
        """
        client = self.get_sync_client()
        data = client.get(key)
        if data:
            payload = json.loads(str(data))
            return (payload["value"], payload["ttl_seconds"])

        return None

    def evict(self, key: str) -> None:
        """Explicitly removes a key from storage. Synchronous operation (blocking).

        Args:
            key (str): The key to be removed.
        """
        client = self.get_sync_client()
        client.delete(key)

    def get_all_keys(self) -> List[str]:
        """Returns all keys present in storage. Warning: Uses KEYS command, which can be costly in production.

        Returns:
            List[str]: List containing all stored keys.
        """
        client = self.get_sync_client()
        keys = client.keys("*")
        return [str(k) for k in keys] if isinstance(keys, list) else []

    def clear(self) -> None:
        """Clears the entire storage (flushdb). Synchronous operation (blocking)."""
        client = self.get_sync_client()
        client.flushdb()

    async def aget(self, key: str) -> Optional[_CacheValue]:
        """Retrieves a value from the cache asynchronously.

        Args:
            key (str): The key to retrieve.

        Returns:
            Optional[_CacheValue]: Tuple (value, expiry) or None.
        """
        async with self.get_async_client() as client:
            data = await client.get(key)
            if data:
                payload = json.loads(str(data))
                return (payload["value"], payload["ttl_seconds"])

            return None

    async def aset(self, key: str, value: Any, ttl_seconds: Union[int, float]) -> None:
        """Stores a value asynchronously with TTL.

        Args:
            key (str): Cache key.
            value (Any): Value to store.
            ttl_seconds (Union[int, float]): Time-to-live in seconds.
        """
        async with self.get_async_client() as client:
            await client.set(key, json.dumps({"value": value, "ttl_seconds": time.monotonic() + ttl_seconds}))

    async def aevict(self, key: str) -> None:
        """
        Removes a key asynchronously.

        Args:
            key (str): The key to remove.
        """
        async with self.get_async_client() as client:
            await client.delete(key)

    async def aget_all_keys(self) -> List[str]:
        """Returns all keys asynchronously.

        Returns:
            List[str]: List of keys.
        """
        async with self.get_async_client() as client:
            keys = await client.keys("*")
            return [str(k) for k in keys] if isinstance(keys, list) else []

    async def aclear(self) -> None:
        """Clears the entire storage asynchronously."""
        async with self.get_async_client() as client:
            await client.flushdb()
