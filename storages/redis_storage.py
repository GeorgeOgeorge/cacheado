import logging
import pickle
import threading
from typing import List, Optional

import redis

from cache_types import _CacheKey, _CacheValue
from protocols.storage_provider import IStorageProvider


class RedisStorage(IStorageProvider):
    """
    Thread-safe Redis implementation of the IStorageProvider.

    Uses Redis as the backend storage with connection string configuration.
    Serializes cache keys and values using pickle for Redis compatibility.
    """

    __slots__ = ("_redis", "_instance_lock")

    def __init__(self, connection_string: str):
        """Initializes the Redis storage provider.

        Args:
            connection_string (str): Redis connection string (e.g., "redis://localhost:6379/0").
        """
        if not connection_string:
            raise ValueError("Connection string is required")

        try:
            self._redis = redis.from_url(connection_string)
            self._instance_lock = threading.Lock()
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

    def get_value_no_lock(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        Performs a non-locking read for the cleanup loop.
        Redis operations are atomic by default.

        Args:
            key (_CacheKey): The internal key to look up.

        Returns:
            Optional[_CacheValue]: The stored tuple (value, expiry) or None.
        """
        return self.get(key)

    def set(self, key: _CacheKey, value: _CacheValue) -> None:
        """
        Atomically sets a value tuple (value, expiry) in Redis.

        Args:
            key (_CacheKey): The internal key to set.
            value (_CacheValue): The (value, expiry) tuple to store.
        """
        try:
            serialized_key = self._serialize_key(key)
            serialized_value = self._serialize_value(value)
            self._redis.set(serialized_key, serialized_value)
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
        Atomically gets a copy of all keys in Redis.

        Returns:
            List[_CacheKey]: A list of all cache keys.
        """
        try:
            with self._instance_lock:
                serialized_keys = self._redis.keys("*")
                return [self._deserialize_key(key.decode()) for key in serialized_keys]
        except Exception as e:
            logging.error(f"Error getting all keys: {e}")
            return []

    def clear(self) -> None:
        """Atomically clears the entire Redis storage."""
        try:
            with self._instance_lock:
                self._redis.flushdb()
        except Exception as e:
            logging.error(f"Error clearing storage: {e}")
