import time
from typing import Any, Dict, List, Optional, Union

from protocols.storage_provider import IStorageProvider
from utils.cache_types import _CacheValue


class InMemory(IStorageProvider):
    """
    Implements an in-memory storage provider using a simple Python dictionary.

    This class provides a non-persistent storage mechanism. It is suitable for
    caching data that does not need to survive application restarts.

    Attributes:
        _cache (Dict[str, _CacheValue]): The internal dictionary storage.
    """

    __slots__ = "_cache"

    def __init__(self) -> None:
        """Initializes the in-memory storage."""
        self._cache: Dict[str, _CacheValue] = {}

    def get_all_keys(self) -> List[str]:
        """Retrieves a list of all keys currently stored in the cache.

        Returns:
            List[str]: A list containing all active keys.
        """
        return list(self._cache.keys())

    def get_stats(self) -> dict:
        """Retrieves current statistics about the storage usage.

        Returns:
            dict: A dictionary containing:
                - 'storage_type': The name of the storage backend ('in_memory').
                - 'total_keys': Current number of items stored.
                - 'max_size': The configured maximum capacity.
        """
        return {
            "storage_type": "in_memory",
            "total_keys": len(self._cache),
        }

    def get(self, key: str) -> Optional[_CacheValue]:
        """Retrieves a value and its expiration metadata from the cache.

        Args:
            key (str): The identifier of the item to retrieve.

        Returns:
            Optional[_CacheValue]: A tuple containing the value and the absolute expiration timestamp,
            or None if the key does not exist.
        """
        return self._cache.get(key, None)

    def set(self, key: str, value: Any, ttl_seconds: Union[int, float]) -> None:
        """Stores a value in the cache with a specific Time-To-Live (TTL). Calculates the absolute expiration time
        based on `time.monotonic()`.

        Args:
            key (str): The identifier for the item.
            value (Any): The actual data to store.
            ttl_seconds (Union[int, float]): Duration in seconds until the item expires.
        """
        self._cache[key] = (value, time.monotonic() + ttl_seconds)

    def evict(self, key: str) -> None:
        """Removes a specific key from the cache. If the key does not exist, this operation does nothing (idempotent).

        Args:
            key (str): The identifier of the item to remove.
        """
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Removes all items from the cache, resetting the storage."""
        self._cache.clear()

    async def aget(self, key: str) -> Optional[_CacheValue]:
        """Asynchronous wrapper for the `get` method."""
        return self.get(key)

    async def aset(self, key: str, value: Any, ttl_seconds: Union[int, float]) -> None:
        """Asynchronous wrapper for the `set` method."""
        self.set(key, value, ttl_seconds)

    async def aevict(self, key: str) -> None:
        """Asynchronous wrapper for the `evict` method."""
        self.evict(key)

    async def aget_all_keys(self) -> List[str]:
        """Asynchronous wrapper for the `get_all_keys` method."""
        return self.get_all_keys()

    async def aclear(self) -> None:
        """Asynchronous wrapper for the `clear` method."""
        self.clear()
