import logging
import pickle
from typing import Any, List, Optional, Union

try:
    import redis
except ImportError:
    raise ImportError("The 'redis' package is required for RedisStorage. Install it via 'pip install cacehado[redis]'.")

from cache_types import _CacheKey, _CacheValue
from protocols.storage_provider import IStorageProvider


class RedisStorage(IStorageProvider):
    """
    High-performance Redis implementation of the IStorageProvider.

    Uses Redis as the backend storage with connection string configuration.
    Serializes cache keys and values using pickle for Redis compatibility.
    Redis operations are atomic by default, so zero-lock philosophy applies.

    Redis natively supports TTL via EXPIRE command, so it does NOT require
    external policy management. Eviction is handled by Redis internally.
    """

    __slots__ = ("_redis",)

    def __init__(self, connection_string: str):
        """Initializes the Redis storage provider.

        Args:
            connection_string (str): Redis connection string (e.g., "redis://localhost:6379/0").
        """
        if not connection_string:
            raise ValueError("Connection string is required")

        try:
            self._redis = redis.from_url(connection_string)
            self._redis.ping()
            logging.info(f"RedisStorage initialized with connection: {connection_string}")
        except Exception as e:
            logging.error(f"Failed to connect to Redis: {e}")
            raise

    def _serialize_key(self, key: _CacheKey) -> str:
        """Serializes cache key for Redis storage."""
        return pickle.dumps(key).hex()

    def _deserialize_key(self, serialized_key: str) -> _CacheKey:
        """Deserializes cache key from Redis storage."""
        result = pickle.loads(bytes.fromhex(serialized_key))

        if not isinstance(result, tuple) or len(result) != 3:
            raise ValueError(f"Invalid cache key format: {result}")
        return result

    def _serialize_value(self, value: _CacheValue) -> bytes:
        """Serializes cache value for Redis storage."""
        return pickle.dumps(value)

    def _deserialize_value(self, serialized_value: bytes) -> _CacheValue:
        """Deserializes cache value from Redis storage."""
        result = pickle.loads(serialized_value)
        if not isinstance(result, tuple) or len(result) != 2:
            raise ValueError(f"Invalid cache value format: {result}")
        return result

    def get(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        Atomically gets a value tuple (value, expiry) from Redis.

        Args:
            key (_CacheKey): The internal key to get.

        Returns:
            Optional[_CacheValue]: The stored tuple, or None.
        """
        try:
            serialized_key = self._serialize_key(key)
            serialized_value = self._redis.get(serialized_key)

            if serialized_value is None:
                return None

            return self._deserialize_value(serialized_value)
        except Exception as e:
            logging.error(f"Error getting key {key}: {e}")
            return None

    def set(self, key: _CacheKey, value: Any, ttl_seconds: Union[int, float]) -> None:
        """
        Sets a value with Redis native TTL (SETEX).

        Args:
            key: The cache key
            value: The value to store
            ttl_seconds: Time-to-live in seconds
        """
        try:
            serialized_key = self._serialize_key(key)
            # Store value with placeholder expiry (Redis manages TTL)
            serialized_value = self._serialize_value((value, 0.0))

            # Redis manages TTL natively via SETEX
            ttl_int = max(1, int(ttl_seconds))
            self._redis.setex(serialized_key, ttl_int, serialized_value)
        except Exception as e:
            logging.error(f"Error setting key {key}: {e}")
            raise

    def evict(self, key: _CacheKey) -> None:
        """
        Atomically evicts a key from Redis.

        Args:
            key (_CacheKey): The internal key to evict.
        """
        try:
            serialized_key = self._serialize_key(key)
            self._redis.delete(serialized_key)
        except Exception as e:
            logging.error(f"Error evicting key {key}: {e}")

    def get_all_keys(self) -> List[_CacheKey]:
        """
        Gets a copy of all keys in Redis.

        Retrieves all keys in a single atomic operation from Redis.

        Returns:
            List[_CacheKey]: A list of all cache keys.
        """
        try:
            serialized_keys = self._redis.keys("*")
            return [self._deserialize_key(key.decode()) for key in serialized_keys]
        except Exception as e:
            logging.error(f"Error getting all keys: {e}")
            return []

    def clear(self) -> None:
        """Atomically clears the entire Redis storage."""
        try:
            self._redis.flushdb()
        except Exception as e:
            logging.error(f"Error clearing storage: {e}")

    # TODO use aioredis or redis[asyncio].

    async def aget(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        Asynchronously gets a value tuple (value, expiry) from Redis.
        Non-blocking operation.

        Args:
            key (_CacheKey): The internal key to get.

        Returns:
            Optional[_CacheValue]: The stored tuple, or None.
        """
        return self.get(key)

    async def aset(self, key: _CacheKey, value: Any, ttl_seconds: Union[int, float]) -> None:
        """
        Asynchronously sets a value with TTL.

        Args:
            key: The cache key
            value: The value to store
            ttl_seconds: Time-to-live in seconds
        """
        self.set(key, value, ttl_seconds)

    async def aevict(self, key: _CacheKey) -> None:
        """
        Asynchronously evicts a key from Redis.
        Non-blocking operation.

        Args:
            key (_CacheKey): The internal key to evict.
        """
        self.evict(key)

    async def aget_all_keys(self) -> List[_CacheKey]:
        """
        Asynchronously gets a copy of all keys in Redis.
        Non-blocking operation.

        Returns:
            List[_CacheKey]: A list of all cache keys.
        """
        return self.get_all_keys()

    async def aclear(self) -> None:
        """
        Asynchronously clears the entire Redis storage.
        Non-blocking operation.
        """
        self.clear()

    def get_stats(self) -> dict:
        """Returns Redis storage statistics."""
        try:
            info = self._redis.info("stats")
            return {
                "storage_type": "redis",
                "total_keys": self._redis.dbsize(),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
            }
        except Exception as e:
            logging.error(f"Error getting Redis stats: {e}")
            return {"storage_type": "redis", "error": str(e)}
