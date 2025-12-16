import time
from collections import OrderedDict
from typing import Any, Optional, Union

from protocols.storage_rule import IStorageRule
from utils.cache_types import RuleSideEffect, StorageRuleAction


class LRUEvict(IStorageRule):
    """
    Implements a Least Recently Used (LRU) eviction policy.

    This rule maintains the order of access for keys. When the cache capacity
    (`max_items`) is exceeded, the least recently accessed item is identified
    for eviction.

    Attributes:
        _access_order (OrderedDict[str, float]): Keeps track of keys ordered by
            access time. The beginning of the dict holds the LRU item, while
            the end holds the MRU (Most Recently Used) item.
        _max_items (int): The maximum number of items allowed in the cache.
    """

    __slots__ = ("_access_order", "_max_items")

    def __init__(self, max_items: int) -> None:
        """Initializes the LRU Eviction rule.

        Args:
            max_items (int): The maximum capacity of the cache. Must be greater than 0.
        """
        self._access_order: OrderedDict[str, float] = OrderedDict()
        self._max_items = max_items

    def on_get(self, key: str) -> Optional[RuleSideEffect]:
        """Marks a key as recently used upon access.

        Moves the accessed key to the end of the tracking structure, designating
        it as the Most Recently Used (MRU).

        Args:
            key (str): The cache key being accessed.

        Returns:
            Optional[RuleSideEffect]: Always returns None.
        """
        if key in self._access_order:
            self._access_order.move_to_end(key, last=True)
        return None

    def on_set(self, key: str, value: Any, ttl_seconds: Union[int, float]) -> Optional[RuleSideEffect]:
        """Registers a key access and enforces capacity limits.

        If the new set operation causes the cache to exceed `max_items`,
        the least recently used item is evicted.

        Args:
            key (str): The cache key being set.
            value (Any): The value being stored.
            ttl_seconds (Union[int, float]): Time-to-live (unused by LRU logic itself).

        Returns:
            Optional[RuleSideEffect]: Returns an EVICT side effect if the cache
            is full, targeting the oldest key. Otherwise, returns None.
        """
        self._access_order[key] = time.monotonic()
        self._access_order.move_to_end(key, last=True)

        if len(self._access_order) > self._max_items:
            oldest_key, _ = self._access_order.popitem(last=False)

            return RuleSideEffect(cache_key=oldest_key, action=StorageRuleAction.EVICT)

        return None

    def on_evict(self, key: str) -> Optional[RuleSideEffect]:
        """Removes a key from LRU tracking when explicitly evicted.

        Args:
            key (str): The key being removed.

        Returns:
            Optional[RuleSideEffect]: Always returns None.
        """
        self._access_order.pop(key, None)
        return None

    def on_clear(self) -> Optional[RuleSideEffect]:
        """Clears all LRU tracking data.

        Returns:
            Optional[RuleSideEffect]: Always returns None.
        """
        self._access_order.clear()
        return None

    def on_get_all_keys(self) -> Optional[RuleSideEffect]:
        """Hook for when all keys are requested.

        Returns:
            Optional[RuleSideEffect]: Always returns None.
        """
        return None
