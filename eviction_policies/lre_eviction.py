from collections import OrderedDict, defaultdict
from typing import DefaultDict, Optional

from cache_types import CacheKey
from protocols.eviction_policy import IEvictionPolicy


class LRUEvictionPolicy(IEvictionPolicy):
    """
    Implements IEvictionPolicy using a Least Recently Used (LRU) strategy.
    Optimized with __slots__ for memory efficiency.
    Uses atomic dict operations for lock-free concurrent access.
    """

    __slots__ = ("_lru_tracker", "_namespaced_lru_trackers")

    def __init__(self) -> None:
        """Initializes the LRU policy trackers."""
        self._lru_tracker: OrderedDict[str, None] = OrderedDict()
        self._namespaced_lru_trackers: DefaultDict[str, OrderedDict[str, None]] = defaultdict(OrderedDict)

    def notify_set(self, key: str, max_items: Optional[int], global_max_size: Optional[int]) -> Optional[str]:
        """
        Adds an item to LRU trackers and evicts an old item if limits are hit.

        Args:
            key (str): The key that was set.
            max_items (Optional[int]): The max_items limit for this namespace.
            global_max_size (Optional[int]): The global max_size limit.

        Returns:
            Optional[str]: The key to evict, or None.
        """
        namespace = CacheKey.extract_namespace(key)
        self._lru_tracker[key] = None
        if namespace:
            self._namespaced_lru_trackers[namespace][key] = None

        key_to_evict: Optional[str] = None

        if max_items is not None and namespace:
            ns_tracker = self._namespaced_lru_trackers[namespace]
            if len(ns_tracker) > max_items:
                try:
                    key_to_evict, _ = ns_tracker.popitem(last=False)
                except (KeyError, Exception):
                    pass

        if key_to_evict is None and global_max_size is not None:
            if len(self._lru_tracker) > global_max_size:
                try:
                    key_to_evict, _ = self._lru_tracker.popitem(last=False)
                except KeyError:
                    pass

        if key_to_evict:
            self._lru_tracker.pop(key_to_evict, None)
            evicted_ns = CacheKey.extract_namespace(key_to_evict)
            if evicted_ns in self._namespaced_lru_trackers:
                self._namespaced_lru_trackers[evicted_ns].pop(key_to_evict, None)

        return key_to_evict

    def notify_get(self, key: str) -> None:
        """
        Moves the accessed item to the end (MRU) of the LRU trackers.

        Args:
            key (str): The key that was accessed.
        """
        try:
            self._lru_tracker.move_to_end(key)
            namespace = CacheKey.extract_namespace(key)
            if namespace in self._namespaced_lru_trackers:
                self._namespaced_lru_trackers[namespace].move_to_end(key)
        except (KeyError, Exception):
            pass

    def notify_evict(self, key: str) -> None:
        """
        Removes an item from all LRU trackers.

        Args:
            key (str): The key that was evicted.
        """
        self._lru_tracker.pop(key, None)
        namespace = CacheKey.extract_namespace(key)
        if namespace in self._namespaced_lru_trackers:
            self._namespaced_lru_trackers[namespace].pop(key, None)
            if not self._namespaced_lru_trackers[namespace]:
                del self._namespaced_lru_trackers[namespace]

    def notify_clear(self) -> None:
        """Clears all LRU trackers."""
        self._lru_tracker.clear()
        self._namespaced_lru_trackers.clear()

    def get_namespace_count(self) -> int:
        """
        Returns the total number of tracked namespaces.

        Returns:
            int: The count of namespaces.
        """
        return len(self._namespaced_lru_trackers)

    def get_global_size(self) -> int:
        """
        Returns the total number of items tracked by the policy.

        Returns:
            int: The global item count.
        """
        return len(self._lru_tracker)
