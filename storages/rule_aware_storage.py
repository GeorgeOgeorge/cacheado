from typing import Any, Iterable, List, Optional, Union

from protocols.storage_provider import IStorageProvider
from protocols.storage_rule import IStorageRule
from utils.cache_types import RuleSideEffect, _CacheValue


class RuleAwareStorage(IStorageProvider):
    """A storage decorator that intercepts operations to apply business rules before or after calling storage."""

    __slots__ = ("_storage", "_rules")

    def __init__(self, inner_storage: IStorageProvider, rules: Iterable[IStorageRule]):
        """Initialize the RuleAwareStorage.

        Args:
            inner_storage (IStorageProvider): The underlying storage provider that performs the actual I/O.
            rules (Iterable[IStorageRule]): A collection of rules to apply.
        """
        self._storage: IStorageProvider = inner_storage
        self._rules: tuple[IStorageRule, ...] = tuple(rules)

    def _apply_side_effects(self, effect: Optional[RuleSideEffect]) -> None:
        """Dynamically executes a side effect method on this instance.

        Args:
            effect (Optional[RuleSideEffect]): The side effect definition containing the action name and the target key.
        """
        if not effect:
            return

        action = getattr(self, effect.action, None)
        if action and callable(action):
            action(effect.cache_key)

    def set(self, key: str, value: Any, ttl_seconds: Union[int, float]) -> None:
        """Sets a value in storage after applying all 'on_set' rules.

        Args:
            key (str): The unique key.
            value (Any): The payload to store.
            ttl_seconds (Union[int, float]): Expiration time in seconds.
        """
        for rule in self._rules:
            effect = rule.on_set(key, value, ttl_seconds)
            self._apply_side_effects(effect)

        self._storage.set(key, value, ttl_seconds)

    def get(self, key: str) -> Optional[_CacheValue]:
        """Retrieves a value and applies 'on_get' rules if the value exists.

        Args:
            key (str): The key to lookup.

        Returns:
            Optional[_CacheValue]: The stored value or None.
        """
        val = self._storage.get(key)

        if val is not None:
            for rule in self._rules:
                effect = rule.on_get(key)
                self._apply_side_effects(effect)

        return val

    def evict(self, key: str) -> None:
        """Removes a value and triggers 'on_evict' rules.

        Args:
            key (str): The key to remove.
        """
        self._storage.evict(key)

        for rule in self._rules:
            effect = rule.on_evict(key)
            self._apply_side_effects(effect)

    def clear(self) -> None:
        """Clears the storage and triggers 'on_clear' rules."""
        self._storage.clear()

        for rule in self._rules:
            effect = rule.on_clear()
            self._apply_side_effects(effect)

    def get_all_keys(self) -> list[str]:
        """Retrieves all keys from the inner storage.

        Returns:
            list[str]: A list of all keys.
        """
        return self._storage.get_all_keys()

    def get_stats(self) -> dict:
        """Retrieves usage statistics.

        Returns:
            dict: Key-value pairs of storage stats.
        """
        return self._storage.get_stats()

    async def aset(self, key: str, value: Any, ttl: Union[int, float]) -> None:
        """Async version of set"""
        for rule in self._rules:
            effect = rule.on_set(key, value, ttl)
            self._apply_side_effects(effect)

        await self._storage.aset(key, value, ttl)

    async def aget(self, key: str) -> Optional[Any]:
        """Async version of get"""
        val = await self._storage.aget(key)

        if val is not None:
            for rule in self._rules:
                effect = rule.on_get(key)
                self._apply_side_effects(effect)

        return val

    async def aevict(self, key: str) -> None:
        """Async version of evict"""
        await self._storage.aevict(key)
        for rule in self._rules:
            effect = rule.on_evict(key)
            self._apply_side_effects(effect)

    async def aclear(self) -> None:
        """Async version of clear."""
        await self._storage.aclear()
        for rule in self._rules:
            effect = rule.on_clear()
            self._apply_side_effects(effect)

    async def aget_all_keys(self) -> List[str]:
        """Async version of get_all_keys"""
        return await self._storage.aget_all_keys()
