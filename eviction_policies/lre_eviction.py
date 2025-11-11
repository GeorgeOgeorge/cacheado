import threading
from collections import OrderedDict, defaultdict
from typing import DefaultDict, Optional

from cache_types import _CacheKey
from protocols.eviction_policy import IEvictionPolicy


class LRUEvictionPolicy(IEvictionPolicy):
    """
    Implements IEvictionPolicy using a thread-safe Least Recently Used (LRU) strategy.
    Optimized with __slots__ for memory efficiency.
    """

    __slots__ = ("_lock", "_lru_tracker", "_namespaced_lru_trackers")

    def __init__(self):
        """Initializes the LRU policy trackers and lock."""
        self._lock = threading.Lock()
        self._lru_tracker: OrderedDict[_CacheKey, None] = OrderedDict()
        self._namespaced_lru_trackers: DefaultDict[str, OrderedDict[_CacheKey, None]] = defaultdict(OrderedDict)

    def notify_set(
        self, key: _CacheKey, namespace: str, max_items: Optional[int], global_max_size: Optional[int]
    ) -> Optional[_CacheKey]:
        """
        Adds an item to LRU trackers and evicts an old item if limits are hit.

        Logic:
        1. Adds the new key to both global and namespace-specific LRU trackers
        2. Checks namespace limit first - if exceeded, evicts oldest item from namespace
        3. If no namespace eviction, checks global limit - if exceeded, evicts globally oldest item
        4. Removes evicted key from all relevant trackers to maintain consistency

        Args:
            key (_CacheKey): The key that was set.
            namespace (str): The namespace of the key.
            max_items (Optional[int]): The max_items limit for this namespace.
            global_max_size (Optional[int]): The global max_size limit.

        Returns:
            Optional[_CacheKey]: The key to evict, or None.
        """
        with self._lock:
            self._lru_tracker[key] = None
            if namespace:
                self._namespaced_lru_trackers[namespace][key] = None

            key_to_evict: Optional[_CacheKey] = None

            if max_items is not None:
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

                evicted_ns = key_to_evict[1]
                if evicted_ns in self._namespaced_lru_trackers:
                    self._namespaced_lru_trackers[evicted_ns].pop(key_to_evict, None)

            return key_to_evict

    def notify_get(self, key: _CacheKey, namespace: str) -> None:
        """
        Moves the accessed item to the end (MRU) of the LRU trackers.

        Args:
            key (_CacheKey): The key that was accessed.
            namespace (str): The namespace of the key.
        """
        with self._lock:
            try:
                self._lru_tracker.move_to_end(key)
                if namespace in self._namespaced_lru_trackers:
                    self._namespaced_lru_trackers[namespace].move_to_end(key)
            except (KeyError, Exception):
                pass

    def notify_evict(self, key: _CacheKey, namespace: str) -> None:
        """
        Removes an item from all LRU trackers.

        Args:
            key (_CacheKey): The key that was evicted.
            namespace (str): The namespace of the key.
        """
        with self._lock:
            self._lru_tracker.pop(key, None)
            if namespace in self._namespaced_lru_trackers:
                self._namespaced_lru_trackers[namespace].pop(key, None)
                if not self._namespaced_lru_trackers[namespace]:
                    del self._namespaced_lru_trackers[namespace]

    def notify_clear(self) -> None:
        """Clears all LRU trackers."""
        with self._lock:
            self._lru_tracker.clear()
            self._namespaced_lru_trackers.clear()

    def get_namespace_count(self) -> int:
        """
        Returns the total number of tracked namespaces.

        Returns:
            int: The count of namespaces.
        """
        with self._lock:
            return len(self._namespaced_lru_trackers)

    def get_global_size(self) -> int:
        """
        Returns the total number of items tracked by the policy.

        Returns:
            int: The global item count.
        """
        with self._lock:
            return len(self._lru_tracker)
