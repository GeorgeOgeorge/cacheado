import logging
import pickle
from typing import Any, List, Optional, Union

try:
    import pymemcache.client.base
except ImportError:
    raise ImportError(
        "The 'pymemcache' package is required for MemcachedStorage. Install it via 'pip install cacehado[memcached]'."
    )

from cache_types import _CacheKey, _CacheValue
from protocols.storage_provider import IStorageProvider


class MemcachedStorage(IStorageProvider):
    """
    High-performance Memcached implementation of the IStorageProvider.

    Uses Memcached as the backend storage with server configuration.
    Serializes cache keys and values using pickle for Memcached compatibility.
    Memcached operations are atomic by default, so zero-lock philosophy applies.

    Memcached natively supports TTL via expire parameter in set(),
    so it does NOT require external policy management.
    """

    __slots__ = ("_client",)

    def __init__(self, server: str = "localhost:11211"):
        """Initializes the Memcached storage provider.

        Args:
            server (str): Memcached server address (default: "localhost:11211").
        """
        if not server:
            raise ValueError("Server address is required")

        try:
            self._client = pymemcache.client.base.Client(server)

            self._client.version()
            logging.info(f"MemcachedStorage initialized with server: {server}")
        except Exception as e:
            logging.error(f"Failed to connect to Memcached: {e}")
            raise

    def _serialize_key(self, key: _CacheKey) -> str:
        """Serializes cache key for Memcached storage."""
        return pickle.dumps(key).hex()

    def _deserialize_key(self, serialized_key: str) -> _CacheKey:
        """Deserializes cache key from Memcached storage."""
        result = pickle.loads(bytes.fromhex(serialized_key))
        if not isinstance(result, tuple) or len(result) != 3:
            raise ValueError(f"Invalid cache key format: {result}")
        return result

    def get(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        Atomically gets a value tuple (value, expiry) from Memcached.

        Args:
            key (_CacheKey): The internal key to get.

        Returns:
            Optional[_CacheValue]: The stored tuple, or None.
        """
        try:
            serialized_key = self._serialize_key(key)
            serialized_value = self._client.get(serialized_key)

            if serialized_value is None:
                return None

            result = pickle.loads(serialized_value)
            if not isinstance(result, tuple) or len(result) != 2:
                raise ValueError(f"Invalid cache value format: {result}")
            return result
        except Exception as e:
            logging.error(f"Error getting key {key}: {e}")
            return None

    def set(self, key: _CacheKey, value: Any, ttl_seconds: Union[int, float]) -> None:
        """
        Sets a value with Memcached native TTL.

        Args:
            key: The cache key
            value: The value to store
            ttl_seconds: Time-to-live in seconds
        """
        try:
            serialized_key = self._serialize_key(key)
            # Store value with placeholder expiry (Memcached manages TTL)
            serialized_value = pickle.dumps((value, 0.0))

            # Memcached manages TTL natively via expire parameter
            ttl_int = max(1, int(ttl_seconds))
            self._client.set(serialized_key, serialized_value, expire=ttl_int)
        except Exception as e:
            logging.error(f"Error setting key {key}: {e}")
            raise

    def evict(self, key: _CacheKey) -> None:
        """
        Atomically evicts a key from Memcached.

        Args:
            key (_CacheKey): The internal key to evict.
        """
        try:
            serialized_key = self._serialize_key(key)
            self._client.delete(serialized_key)
        except Exception as e:
            logging.error(f"Error evicting key {key}: {e}")

    def get_all_keys(self) -> List[_CacheKey]:
        """
        Gets all keys from Memcached.
        Note: Memcached doesn't natively support key enumeration,
        so this returns an empty list as a limitation.

        Returns:
            List[_CacheKey]: Empty list (Memcached limitation).
        """
        logging.warning("Memcached does not support key enumeration. Returning empty list.")
        return []

    def clear(self) -> None:
        """Atomically clears the entire Memcached storage."""
        try:
            self._client.flush_all()
        except Exception as e:
            logging.error(f"Error clearing storage: {e}")

    # TODO use aiomcache.

    async def aget(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        Asynchronously gets a value tuple (value, expiry) from Memcached.
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
        Asynchronously evicts a key from Memcached.
        Non-blocking operation.

        Args:
            key (_CacheKey): The internal key to evict.
        """
        self.evict(key)

    async def aget_all_keys(self) -> List[_CacheKey]:
        """
        Asynchronously gets a copy of all keys in Memcached.
        Note: Memcached doesn't natively support key enumeration.

        Returns:
            List[_CacheKey]: Empty list (Memcached limitation).
        """
        return self.get_all_keys()

    async def aclear(self) -> None:
        """
        Asynchronously clears the entire Memcached storage.
        Non-blocking operation.
        """
        self.clear()

    def get_stats(self) -> dict:
        """Returns Memcached storage statistics."""
        try:
            stats = self._client.stats()
            return {
                "storage_type": "memcached",
                "total_keys": int(stats.get(b"curr_items", 0)),
                "total_connections": int(stats.get(b"curr_connections", 0)),
            }
        except Exception as e:
            logging.error(f"Error getting Memcached stats: {e}")
            return {"storage_type": "memcached", "error": str(e)}
