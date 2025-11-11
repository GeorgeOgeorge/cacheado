from typing import Optional, Protocol

from cache_types import _CacheKey


class IEvictionPolicy(Protocol):
    """
    Interface (Protocol) for all cache eviction policies (e.g., LRU, LFU).
    Implementations MUST be thread-safe.
    """

    def notify_set(
        self, key: _CacheKey, namespace: str, max_items: Optional[int], global_max_size: Optional[int]
    ) -> Optional[_CacheKey]:
        """
        Notifies the policy that an item was set (added/updated).
        The policy must enforce limits and return a key to evict if necessary.

        Args:
            key (_CacheKey): The key that was set.
            namespace (str): The namespace of the key.
            max_items (Optional[int]): The max_items limit for this namespace.
            global_max_size (Optional[int]): The global max_size limit.

        Returns:
            Optional[_CacheKey]: A key to evict, or None.
        """
        ...

    def notify_get(self, key: _CacheKey, namespace: str) -> None:
        """
        Notifies the policy that an item was accessed (read).

        Args:
            key (_CacheKey): The key that was accessed.
            namespace (str): The namespace of the key.
        """
        ...

    def notify_evict(self, key: _CacheKey, namespace: str) -> None:
        """
        Notifies the policy that an item was evicted (removed).

        Args:
            key (_CacheKey): The key that was evicted.
            namespace (str): The namespace of the key.
        """
        ...

    def notify_clear(self) -> None:
        """Notifies the policy that the entire cache was cleared."""
        ...

    def get_namespace_count(self) -> int:
        """
        Returns the total number of tracked namespaces.

        Returns:
            int: The count of namespaces.
        """
        ...

    def get_global_size(self) -> int:
        """
        Returns the total number of items tracked by the policy.

        Returns:
            int: The global item count.
        """
        ...
