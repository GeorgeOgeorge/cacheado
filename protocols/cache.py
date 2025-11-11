from typing import Any, Awaitable, Callable, Dict, Optional, Protocol, Union

from cache_types import _CacheScope, _FuncT
from protocols.eviction_policy import IEvictionPolicy
from protocols.storage_provider import IStorageProvider


class ICache(Protocol):
    """
    Interface (Protocol) defining the public API for the Cache.

    This allows for Dependency Injection and testability, enabling
    consumers to depend on this interface rather than the concrete
    Singleton implementation.
    """

    def get(
        self, key: Any, scope: _CacheScope = "global", organization_id: Optional[str] = None, user_id: Optional[str] = None
    ) -> Optional[Any]:
        """
        Gets an item programmatically from the cache.

        Args:
            key (Any): The key to look up (must be hashable).
            scope (_CacheScope): The scope ('global', 'organization', 'user').
            organization_id (Optional[str]): Required if scope='organization'.
            user_id (Optional[str]): Required if scope='user'.

        Returns:
            Optional[Any]: The cached value or None if not found or expired.
        """
        ...

    def set(
        self,
        key: Any,
        value: Any,
        ttl_seconds: Union[int, float],
        scope: _CacheScope = "global",
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Sets an item programmatically in the cache.

        Args:
            key (Any): The key (must be hashable).
            value (Any): The value to store.
            ttl_seconds (Union[int, float]): Time-to-live in seconds.
            scope (_CacheScope): The scope ('global', 'organization', 'user').
            organization_id (Optional[str]): Required if scope='organization'.
            user_id (Optional[str]): Required if scope='user'.
        """
        ...

    def evict(
        self, key: Any, scope: _CacheScope = "global", organization_id: Optional[str] = None, user_id: Optional[str] = None
    ) -> None:
        """
        Removes a specific item programmatically from the cache.

        Args:
            key (Any): The key to remove (must be hashable).
            scope (_CacheScope): The scope ('global', 'organization', 'user').
            organization_id (Optional[str]): Required if scope='organization'.
            user_id (Optional[str]): Required if scope='user'.
        """
        ...

    def clear(self) -> None:
        """Safely clears the entire cache."""
        ...

    def aget(
        self, key: Any, scope: _CacheScope = "global", organization_id: Optional[str] = None, user_id: Optional[str] = None
    ) -> Awaitable[Optional[Any]]:
        """
        Asynchronously gets an item programmatically from the cache.

        Args:
            key (Any): The key to look up (must be hashable).
            scope (_CacheScope): The scope ('global', 'organization', 'user').
            organization_id (Optional[str]): Required if scope='organization'.
            user_id (Optional[str]): Required if scope='user'.

        Returns:
            Awaitable[Optional[Any]]: The cached value or None.
        """
        ...

    def aset(
        self,
        key: Any,
        value: Any,
        ttl_seconds: Union[int, float],
        scope: _CacheScope = "global",
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Awaitable[None]:
        """
        Asynchronously sets an item programmatically in the cache.

        Args:
            key (Any): The key (must be hashable).
            value (Any): The value to store.
            ttl_seconds (Union[int, float]): Time-to-live in seconds.
            scope (_CacheScope): The scope ('global', 'organization', 'user').
            organization_id (Optional[str]): Required if scope='organization'.
            user_id (Optional[str]): Required if scope='user'.
        """
        ...

    def aevict(
        self, key: Any, scope: _CacheScope = "global", organization_id: Optional[str] = None, user_id: Optional[str] = None
    ) -> Awaitable[None]:
        """
        Asynchronously removes a specific item programmatically.

        Args:
            key (Any): The key to remove (must be hashable).
            scope (_CacheScope): The scope ('global', 'organization', 'user').
            organization_id (Optional[str]): Required if scope='organization'.
            user_id (Optional[str]): Required if scope='user'.
        """
        ...

    def aclear(self) -> Awaitable[None]:
        """Asynchronously clears the entire cache."""
        ...

    def stats(self) -> Dict[str, Any]:
        """
        Returns a dictionary of cache observability statistics.

        Returns:
            Dict[str, Any]: A dict containing keys like 'hits', 'misses',
            'evictions', 'current_size', etc.
        """
        ...

    def evict_by_scope(self, scope: _CacheScope, organization_id: Optional[str] = None, user_id: Optional[str] = None) -> int:
        """
        Granularly evicts all items belonging to a specific tenant.

        Args:
            scope (_CacheScope): The scope to target ('organization' or 'user').
            organization_id (Optional[str]): Required if scope='organization'.
            user_id (Optional[str]): Required if scope='user'.

        Returns:
            int: The number of items successfully evicted.
        """
        ...

    def cache(
        self, ttl_seconds: Union[int, float], scope: _CacheScope = "global", max_items: Optional[int] = None
    ) -> Callable[[_FuncT], _FuncT]:
        """
        Decorator factory for caching function results.

        Args:
            ttl_seconds (Union[int, float]): Time-to-live for items.
            scope (_CacheScope): The cache scope.
            max_items (Optional[int]): Max items for this function.

        Returns:
            Callable[[_FuncT], _FuncT]: A decorator function.
        """
        ...

    def configure(
        self, backend: IStorageProvider, policy: IEvictionPolicy, max_size: int = 1000, cleanup_interval: int = 60
    ) -> None:
        """
        Configures and starts the cache. Must be called once.

        Args:
            backend (IStorageProvider): The storage backend (e.g., InMemoryStorageProvider).
            policy (IEvictionPolicy): The eviction policy (e.g., LRUEvictionPolicy).
            max_size (int): Max number of items to store globally.
            cleanup_interval (int): Interval (in seconds) for background cleanup.
        """
        ...
