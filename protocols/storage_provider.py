from typing import List, Optional, Protocol

from cache_types import _CacheKey, _CacheValue


class IStorageProvider(Protocol):
    """
    Interface (Protocol) for all storage backends (e.g., In-Memory, Redis).
    Implementations MUST be thread-safe for synchronous operations.
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

    def get_value_no_lock(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        Performs a non-locking ("dirty") read for the cleanup loop.
        Only required for backends that support it.

        Args:
            key (_CacheKey): The internal key to look up.

        Returns:
            Optional[_CacheValue]: The stored tuple (value, expiry) or None.
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
