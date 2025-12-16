from typing import Any, Optional, Set, Union

from protocols.storage_rule import IStorageRule
from utils.cache_types import RuleSideEffect, StorageRuleAction


class MaxItemsEvict(IStorageRule):
    """
    Implements a 'Hard Limit' capacity policy.

    Unlike eviction policies that remove old items to make space (like LRU),
    this rule rejects new items when the cache reaches its maximum capacity
    (`max_items`). It ensures the cache never grows beyond a fixed size.

    Attributes:
        _keys (Set[str]): A set tracking all currently stored keys for O(1) lookup.
        _max_items (int): The hard limit for the number of items in the cache.
    """

    __slots__ = ("_keys", "_max_items")

    def __init__(self, max_items: int) -> None:
        """
        Initializes the Max Items Eviction rule.

        Args:
            max_items (int): The maximum capacity of the cache. Must be greater than 0.
        """
        self._keys: Set[str] = set()
        self._max_items = max_items

    def on_get(self, key: str) -> Optional[RuleSideEffect]:
        """Hook for key access.

        This rule does not track access patterns (recency/frequency),
        so this method does nothing.

        Args:
            key (str): The cache key being accessed.

        Returns:
            Optional[RuleSideEffect]: Always returns None.
        """
        return None

    def on_set(self, key: str, value: Any, ttl_seconds: Union[int, float]) -> Optional[RuleSideEffect]:
        """Enforces the capacity limit on new insertions.

        If the key is new (not currently in the set) and the cache is full,
        this triggers an immediate eviction of the *incoming* key, effectively
        rejecting the storage operation.

        Args:
            key (str): The cache key being set.
            value (Any): The value being stored.
            ttl_seconds (Union[int, float]): Time-to-live.

        Returns:
            Optional[RuleSideEffect]: Returns an EVICT action for the incoming key
            if the limit is reached. Returns None if the key is accepted or already exists.
        """
        if key not in self._keys:
            if len(self._keys) >= self._max_items:
                return RuleSideEffect(cache_key=key, action=StorageRuleAction.EVICT)

            self._keys.add(key)

        return None

    def on_evict(self, key: str) -> Optional[RuleSideEffect]:
        """Updates the internal tracking when a key is removed.

        Using `discard` ensures no error is raised if the key was already
        removed or tracked by another rule.

        Args:
            key (str): The key being removed.

        Returns:
            Optional[RuleSideEffect]: Always returns None.
        """
        self._keys.discard(key)
        return None

    def on_clear(self) -> Optional[RuleSideEffect]:
        """Resets the internal tracking set.

        Returns:
            Optional[RuleSideEffect]: Always returns None.
        """
        self._keys.clear()
        return None

    def on_get_all_keys(self) -> Optional[RuleSideEffect]:
        """Hook for when all keys are requested.

        Returns:
            Optional[RuleSideEffect]: Always returns None.
        """
        return None
