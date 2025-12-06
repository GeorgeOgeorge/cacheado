from typing import Optional, Protocol


class IEvictionPolicy(Protocol):
    """
    Interface (Protocol) for all cache eviction policies (e.g., LRU, LFU).
    Implementations MUST be thread-safe.
    """

    def notify_set(self, key: str, max_items: Optional[int], global_max_size: Optional[int]) -> Optional[str]:
        """
        Notifies the policy that an item was set (added/updated).
        The policy must enforce limits and return a key to evict if necessary.

        Args:
            key (str): The key that was set.
            max_items (Optional[int]): The max_items limit for this namespace.
            global_max_size (Optional[int]): The global max_size limit.

        Returns:
            Optional[str]: A key to evict, or None.
        """
        ...

    def notify_get(self, key: str) -> None:
        """
        Notifies the policy that an item was accessed (read).

        Args:
            key (str): The key that was accessed.
        """
        ...

    def notify_evict(self, key: str) -> None:
        """
        Notifies the policy that an item was evicted (removed).

        Args:
            key (str): The key that was evicted.
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
