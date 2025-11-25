import logging
import time
from typing import Any, Dict, List, Optional, Union

from cache_types import _CacheKey, _CacheValue
from eviction_policies.lre_eviction import LRUEvictionPolicy
from protocols.storage_provider import IStorageProvider


class InMemory(IStorageProvider):
    """In-memory storage with lazy TTL checking and LRU eviction.
    
    Uses lazy eviction: expired items are removed only when accessed.
    LRU policy manages memory limits without background threads.
    """

    __slots__ = ("_cache", "_lru_policy", "_max_size")

    def __init__(self, max_size: Optional[int] = None) -> None:
        """Initializes in-memory storage with LRU policy.

        Args:
            max_size (Optional[int]): Maximum number of items (default: None)
        """
        self._cache: Dict[_CacheKey, _CacheValue] = {}
        self._lru_policy = LRUEvictionPolicy()
        self._max_size = max_size
        logging.info(f"InMemory initialized: max_size={max_size}")

    def get_all_keys(self) -> List[_CacheKey]:
        """Returns all cache keys.

        Returns:
            List[_CacheKey]: List of all keys
        """
        return list(self._cache.keys())

    def get_stats(self) -> dict:
        """Returns storage statistics.

        Returns:
            dict: Statistics including storage type, keys, and LRU stats
        """
        return {
            "storage_type": "in_memory",
            "total_keys": len(self._cache),
            "max_size": self._max_size,
            "lru_global_size": self._lru_policy.get_global_size(),
            "lru_namespaces": self._lru_policy.get_namespace_count(),
        }

    def get(self, key: _CacheKey) -> Optional[_CacheValue]:
        """Gets value with lazy TTL check and LRU tracking.

        Args:
            key (_CacheKey): Cache key

        Returns:
            Optional[_CacheValue]: Value tuple or None if not found/expired
        """
        value_tuple = self._cache.get(key)
        if value_tuple is None:
            return None

        _, expiry = value_tuple
        if time.monotonic() > expiry:
            self.evict(key)
            return None

        self._lru_policy.notify_get(key, key[1])
        return value_tuple

    def set(self, key: _CacheKey, value: Any, ttl_seconds: Union[int, float]) -> None:
        """Sets value with TTL and LRU eviction check.

        Args:
            key (_CacheKey): Cache key
            value (Any): Value to store
            ttl_seconds (Union[int, float]): Time-to-live in seconds
        """
        expiry = time.monotonic() + ttl_seconds
        self._cache[key] = (value, expiry)

        key_to_evict = self._lru_policy.notify_set(key, key[1], None, self._max_size)
        if key_to_evict:
            self.evict(key_to_evict)

    def evict(self, key: _CacheKey) -> None:
        """Evicts key and notifies LRU policy.

        Args:
            key (_CacheKey): Cache key to evict
        """
        self._cache.pop(key, None)
        self._lru_policy.notify_evict(key, key[1])

    def clear(self) -> None:
        """Clears all data and LRU policy."""
        self._cache.clear()
        self._lru_policy.notify_clear()

    async def aget(self, key: _CacheKey) -> Optional[_CacheValue]:
        """Async get.

        Args:
            key (_CacheKey): Cache key

        Returns:
            Optional[_CacheValue]: Value tuple or None
        """
        return self.get(key)

    async def aset(self, key: _CacheKey, value: Any, ttl_seconds: Union[int, float]) -> None:
        """Async set.

        Args:
            key (_CacheKey): Cache key
            value (Any): Value to store
            ttl_seconds (Union[int, float]): Time-to-live in seconds
        """
        self.set(key, value, ttl_seconds)

    async def aevict(self, key: _CacheKey) -> None:
        """Async evict.

        Args:
            key (_CacheKey): Cache key to evict
        """
        self.evict(key)

    async def aget_all_keys(self) -> List[_CacheKey]:
        """Async get all keys.

        Returns:
            List[_CacheKey]: List of all keys
        """
        return self.get_all_keys()

    async def aclear(self) -> None:
        """Async clear."""
        self.clear()
