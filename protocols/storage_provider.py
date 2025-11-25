from typing import Any, List, Optional, Protocol, Union

from cache_types import _CacheKey, _CacheValue


class IStorageProvider(Protocol):
    """
    Interface (Protocol) for all storage backends (e.g., In-Memory, Redis).

    Storage providers are FULLY RESPONSIBLE for:
    - Data persistence (get/set/evict/clear)
    - TTL calculation and management (storage-specific)
    - Eviction policies (LRU, LFU, etc.)
    - Cleanup mechanisms (background threads, native TTL)
    - Statistics tracking

    The Cache class only manages:
    - Public API
    - Namespace/scope management
    - Decorator logic

    This follows the principle: "Storage owns its data lifecycle"
    """

    def set(self, key: _CacheKey, value: Any, ttl_seconds: Union[int, float]) -> None:
        """
        Sets a value with TTL.

        Args:
            key: The cache key
            value: The value to store
            ttl_seconds: Time-to-live in seconds
        """
        ...

    def get_stats(self) -> dict:
        """
        Returns storage-specific statistics.

        Returns:
            dict: Statistics like current_size, namespace_count, etc.
        """
        ...

    def get(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        Atomically gets a value tuple (value, expiry) from storage.

        Args:
            key (_CacheKey): The internal key to get.

        Returns:
            Optional[_CacheValue]: The stored tuple, or None.
        """
        ...

    def evict(self, key: _CacheKey) -> None:
        """
        Atomically evicts a key from storage.

        Args:
            key (_CacheKey): The internal key to evict.
        """
        ...

    def get_all_keys(self) -> List[_CacheKey]:
        """
        Atomically gets a copy of all keys in storage.

        Returns:
            List[_CacheKey]: A list of all cache keys.
        """
        ...

    def clear(self) -> None:
        """Atomically clears the entire storage."""
        ...

    async def aget(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        Asynchronously gets a value tuple (value, expiry) from storage.
        Non-blocking, allows concurrent operations.

        Args:
            key (_CacheKey): The internal key to get.

        Returns:
            Optional[_CacheValue]: The stored tuple, or None.
        """
        ...

    async def aset(self, key: _CacheKey, value: Any, ttl_seconds: Union[int, float]) -> None:
        """
        Asynchronously sets a value with TTL.

        Args:
            key: The cache key
            value: The value to store
            ttl_seconds: Time-to-live in seconds
        """
        ...

    async def aevict(self, key: _CacheKey) -> None:
        """
        Asynchronously evicts a key from storage.
        Non-blocking, allows concurrent operations.

        Args:
            key (_CacheKey): The internal key to evict.
        """
        ...

    async def aget_all_keys(self) -> List[_CacheKey]:
        """
        Asynchronously gets a copy of all keys in storage.
        Non-blocking, allows concurrent operations.

        Returns:
            List[_CacheKey]: A list of all cache keys.
        """
        ...

    async def aclear(self) -> None:
        """
        Asynchronously clears the entire storage.
        Non-blocking, allows concurrent operations.
        """
        ...
