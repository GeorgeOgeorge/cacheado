from typing import List, Optional, Protocol

from cache_types import _CacheKey, _CacheValue


class IStorageProvider(Protocol):
    """
    Interface (Protocol) for all storage backends (e.g., In-Memory, Redis).
    
    Implementations MUST support both sync and async operations.
    For async-first applications, prefer async variants.
    Async methods are non-blocking and allow concurrent operations.
    """

    def get(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        Atomically gets a value tuple (value, expiry) from storage.

        Args:
            key (_CacheKey): The internal key to get.

        Returns:
            Optional[_CacheValue]: The stored tuple, or None.
        """
        ...

    def set(self, key: _CacheKey, value: _CacheValue) -> None:
        """
        Atomically sets a value tuple (value, expiry) in storage.

        Args:
            key (_CacheKey): The internal key to set.
            value (_CacheValue): The (value, expiry) tuple to store.
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

    async def aset(self, key: _CacheKey, value: _CacheValue) -> None:
        """
        Asynchronously sets a value tuple (value, expiry) in storage.
        Non-blocking, allows concurrent operations.

        Args:
            key (_CacheKey): The internal key to set.
            value (_CacheValue): The (value, expiry) tuple to store.
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
