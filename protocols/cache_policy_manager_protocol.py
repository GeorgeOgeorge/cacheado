from typing import Optional, Protocol

from cache_types import _CacheKey
from protocols.eviction_policy import IEvictionPolicy


class ICachePolicyManager(Protocol):
    """
    Interface (Protocol) for cache policy management implementations.

    Defines the contract for managing cache policies including
    background cleanup and eviction coordination.
    """

    @property
    def policy(self) -> IEvictionPolicy:
        """Returns the eviction policy instance."""
        ...

    @property
    def global_max_size(self) -> Optional[int]:
        """Returns the global maximum cache size."""
        ...

    @property
    def cleanup_interval(self) -> int:
        """Returns the cleanup interval in seconds."""
        ...

    def start_background_cleanup(self) -> None:
        """Starts the background cleanup thread."""
        ...

    def stop_background_cleanup(self) -> None:
        """Stops the background cleanup thread gracefully."""
        ...

    def notify_set(self, key: _CacheKey, namespace: str, max_items: Optional[int]) -> Optional[_CacheKey]:
        """
        Notifies that an item was set and returns key to evict if needed.

        Args:
            key: The key that was set.
            namespace: The namespace of the key.
            max_items: The max_items limit for this namespace.

        Returns:
            Key to evict or None.
        """
        ...

    def notify_get(self, key: _CacheKey, namespace: str) -> None:
        """
        Notifies that an item was accessed.

        Args:
            key: The key that was accessed.
            namespace: The namespace of the key.
        """
        ...

    def notify_evict(self, key: _CacheKey, namespace: str) -> None:
        """
        Notifies that an item was evicted.

        Args:
            key: The key that was evicted.
            namespace: The namespace of the key.
        """
        ...

    def notify_clear(self) -> None:
        """Notifies that the entire cache was cleared."""
        ...

    def get_namespace_count(self) -> int:
        """Returns the total number of tracked namespaces."""
        ...

    def get_global_size(self) -> int:
        """Returns the global item count."""
        ...
