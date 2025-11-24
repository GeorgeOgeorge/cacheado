import logging
from typing import Dict, List, Optional

from cache_types import _CacheKey, _CacheValue
from protocols.storage_provider import IStorageProvider


class InMemory(IStorageProvider):
    """
    High-performance in-memory implementation of the IStorageProvider.

    Uses zero-lock philosophy for all operations on atomic dict operations (get/set/evict/clear).
    Relies on Python's GIL and atomic dict operations for thread safety.
    Optimized with __slots__ for memory efficiency.
    """

    __slots__ = ("_cache",)

    def __init__(self):
        """Initializes the in-memory storage."""
        self._cache: Dict[_CacheKey, _CacheValue] = {}
        logging.info("InMemoryStorageProvider initialized.")

    def get(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        Gets a value tuple (value, expiry) from memory without locking.

        The dict.get() operation is atomic in Python, so no lock is needed.
        Per the "let it crash" philosophy, we trust the atomicity of dict operations.

        Args:
            key (_CacheKey): The internal key to get.

        Returns:
            Optional[_CacheValue]: The stored tuple, or None.
        """
        return self._cache.get(key, None)

    def set(self, key: _CacheKey, value: _CacheValue) -> None:
        """
        Sets a value tuple (value, expiry) in memory without locking.

        The dict[key] = value operation is atomic in Python.
        Per the "let it crash" philosophy, the last writer wins (acceptable for cache).

        Args:
            key (_CacheKey): The internal key to set.
            value (_CacheValue): The (value, expiry) tuple to store.
        """
        self._cache[key] = value

    def evict(self, key: _CacheKey) -> None:
        """
        Evicts a key from memory without locking.

        Uses .pop(key, None) which is atomic in Python.
        Per the "let it crash" philosophy, we trust dict atomicity.

        Args:
            key (_CacheKey): The internal key to evict.
        """
        self._cache.pop(key, None)

    def get_all_keys(self) -> List[_CacheKey]:
        """
        Gets a copy of all keys in memory.

        Returns a snapshot of keys at the time of call.
        Per the "let it crash" philosophy, we trust list() snapshot operation.

        Returns:
            List[_CacheKey]: A list of all cache keys.
        """
        return list(self._cache.keys())

    def clear(self) -> None:
        """
        Clears the entire in-memory storage.

        Uses dict.clear() which is atomic in Python.
        Per the "let it crash" philosophy, we trust dict atomicity.
        """
        self._cache.clear()

    async def aget(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        Asynchronously gets a value tuple (value, expiry) from memory.
        Non-blocking operation.

        Args:
            key (_CacheKey): The internal key to get.

        Returns:
            Optional[_CacheValue]: The stored tuple, or None.
        """
        return self._cache.get(key, None)

    async def aset(self, key: _CacheKey, value: _CacheValue) -> None:
        """
        Asynchronously sets a value tuple (value, expiry) in memory.
        Non-blocking operation.

        Args:
            key (_CacheKey): The internal key to set.
            value (_CacheValue): The (value, expiry) tuple to store.
        """
        self._cache[key] = value

    async def aevict(self, key: _CacheKey) -> None:
        """
        Asynchronously evicts a key from memory.
        Non-blocking operation.

        Args:
            key (_CacheKey): The internal key to evict.
        """
        self._cache.pop(key, None)

    async def aget_all_keys(self) -> List[_CacheKey]:
        """
        Asynchronously gets a copy of all keys in memory.
        Non-blocking operation.

        Returns:
            List[_CacheKey]: A list of all cache keys.
        """
        return list(self._cache.keys())

    async def aclear(self) -> None:
        """
        Asynchronously clears the entire in-memory storage.
        Non-blocking operation.
        """
        self._cache.clear()
