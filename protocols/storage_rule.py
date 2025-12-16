from typing import Any, Optional, Protocol, Union

from utils.cache_types import RuleSideEffect


class IStorageRule(Protocol):
    """
    Defines the contract for storage rules.

    Uses structural typing (Protocol) to allow any class implementing these
    methods to be treated as a valid rule, without explicit inheritance.
    """

    def on_get(self, key: str) -> Optional[RuleSideEffect]:
        """
        Executed when a read operation (GET) is requested for a key.

        Args:
            key (str): The unique key being accessed in storage.

        Returns:
            Optional[RuleSideEffect]: An optional side effect to be applied
            (e.g., deny access, force expiration), or None if the operation
            should proceed normally.
        """
        ...

    def on_set(self, key: str, value: Any, ttl_seconds: Union[int, float]) -> Optional[RuleSideEffect]:
        """
        Executed when a write operation (SET) is requested.

        Args:
            key (str): The key where the value will be stored.
            value (Any): The value to be stored. Typed as Any since storage may accept varied types.
            ttl_seconds (Union[int, float]): The Time To Live (TTL) defined for this value, in seconds.

        Returns:
            Optional[RuleSideEffect]: An optional side effect (e.g., modify TTL, reject write),
            or None to allow the standard operation.
        """
        ...

    def on_evict(self, key: str) -> Optional[RuleSideEffect]:
        """
        Executed when a key is evicted from storage, either by TTL expiration or explicit removal.

        Args:
            key (str): The key being removed.

        Returns:
            Optional[RuleSideEffect]: An optional side effect to be triggered after removal,
            or None if no extra action is needed.
        """
        ...

    def on_clear(self) -> Optional[RuleSideEffect]:
        """
        Executed when the entire storage is cleared (flush/clear).

        Returns:
            Optional[RuleSideEffect]: An optional side effect to be executed during or after clearing or None.
        """
        ...

    def on_get_all_keys(self) -> Optional[RuleSideEffect]:
        """
        Executed when a listing of all keys is requested.

        Returns:
            Optional[RuleSideEffect]: An optional side effect (e.g., mass access auditing) or None.
        """
        ...
