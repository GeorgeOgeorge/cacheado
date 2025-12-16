import time
from typing import Any, Dict, Optional, Union

from protocols.storage_rule import IStorageRule
from utils.cache_types import RuleSideEffect, StorageRuleAction


class LifeTimeEvict(IStorageRule):
    """
    Implements a Time-To-Live (TTL) eviction policy.

    This rule tracks the expiration time of each key and strictly enforces
    TTL on access (lazy expiration). It ensures that expired items are
    evicted and not returned to the client.

    Attributes:
        _expiry_times (Dict[str, float]): A mapping of cache keys to their absolute expiration timestamps.
    """

    __slots__ = ("_expiry_times",)

    def __init__(self) -> None:
        """Initializes the Lifetime Eviction rule."""
        self._expiry_times: Dict[str, float] = {}

    def on_get(self, key: str) -> Optional[RuleSideEffect]:
        """Checks if the requested key has expired.

        This method implements 'lazy expiration'. If the key exists but its
        TTL has passed, it triggers an eviction side effect immediately.

        Args:
            key (str): The cache key being accessed.

        Returns:
            Optional[RuleSideEffect]: Returns a side effect with action
            `StorageRuleAction.EVICT` if the item is expired. Returns `None`
            if the item is valid or not tracked.
        """
        expiry = self._expiry_times.get(key)
        if expiry and time.monotonic() >= expiry:
            self._expiry_times.pop(key, None)
            return RuleSideEffect(cache_key=key, action=StorageRuleAction.EVICT)
        return None

    def on_set(self, key: str, value: Any, ttl_seconds: Union[int, float]) -> Optional[RuleSideEffect]:
        """Registers or updates the expiration time for a key.

        Args:
            key (str): The cache key being set.
            value (Any): The value being stored (ignored by this rule).
            ttl_seconds (Union[int, float]): The time-to-live in seconds.

        Returns:
            Optional[RuleSideEffect]: Always returns None as setting a TTL
            does not trigger immediate side effects.
        """
        self._expiry_times[key] = time.monotonic() + ttl_seconds
        return None

    def on_evict(self, key: str) -> Optional[RuleSideEffect]:
        """Cleans up the tracking metadata when a key is explicitly evicted.

        Args:
            key (str): The cache key being evicted.

        Returns:
            Optional[RuleSideEffect]: Always returns None.
        """
        self._expiry_times.pop(key, None)
        return None

    def on_clear(self) -> Optional[RuleSideEffect]:
        """Resets all tracking data when the cache is cleared.

        Returns:
            Optional[RuleSideEffect]: Always returns None.
        """
        self._expiry_times.clear()
        return None

    def on_get_all_keys(self) -> Optional[RuleSideEffect]:
        """Hook for when all keys are requested.

        Returns:
            Optional[RuleSideEffect]: Always returns None.
        """
        return None
