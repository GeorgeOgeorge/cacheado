import asyncio
import logging
import pickle
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple, Union

from typing_extensions import ParamSpec, TypeVar

from cache_scope_config import ScopeConfig
from cache_types import _CacheKey, _CacheScope
from protocols.storage_provider import IStorageProvider
from storages.in_memory import InMemory

P = ParamSpec("P")
T = TypeVar("T")


class Cache:
    """Public API for cache operations with scope management.

    Responsibilities:
    - Public API (get/set/evict/clear, decorator)
    - Namespace/scope management
    - Statistics aggregation

    Storage handles: TTL, eviction, cleanup
    """

    __slots__ = ("_storage", "_scope_config", "_hits", "_misses", "_evictions")

    def __init__(self, backend: IStorageProvider, scope_config: ScopeConfig) -> None:
        """Initializes cache with storage backend and scope configuration.

        Args:
            backend (IStorageProvider): Storage backend
            scope_config (ScopeConfig): Scope hierarchy configuration
        """
        self._storage = backend
        self._scope_config = scope_config
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0
        logging.info(f"Cache initialized with {backend.__class__.__name__}")

    def _internal_get(self, key: _CacheKey) -> Optional[Any]:
        """Gets value from storage and updates statistics.

        Args:
            key (_CacheKey): Cache key

        Returns:
            Optional[Any]: Cached value or None if not found
        """
        value_tuple = self._storage.get(key)
        if value_tuple is None:
            self._misses += 1
            return None

        self._hits += 1
        return value_tuple[0]

    def _internal_set(self, key: _CacheKey, value: Any, ttl_seconds: Union[int, float]) -> None:
        """Sets value in storage.

        Args:
            key (_CacheKey): Cache key
            value (Any): Value to cache
            ttl_seconds (Union[int, float]): Time-to-live in seconds
        """
        if ttl_seconds <= 0:
            return

        self._storage.set(key, value, ttl_seconds)

    def _internal_evict(self, key: _CacheKey) -> None:
        """Evicts key from storage and updates statistics.

        Args:
            key (_CacheKey): Cache key to evict
        """
        self._storage.evict(key)
        self._evictions += 1

    def _make_args_key(self, *args: Any, **kwargs: Any) -> Tuple[Any, ...]:
        """Creates hashable key from function arguments.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Tuple[Any, ...]: Serialized arguments as tuple

        Raises:
            TypeError: If arguments cannot be serialized
        """
        try:
            key_repr = (args, tuple(sorted(kwargs.items())))
            return (pickle.dumps(key_repr, protocol=pickle.HIGHEST_PROTOCOL),)
        except (pickle.PicklingError, TypeError) as e:
            logging.warning(f"Failed to serialize arguments: {e}")
            raise TypeError(f"Unhashable arguments: {e}")

    def _build_scope_prefix(self, scope: _CacheScope, params: Dict[str, Any]) -> str:
        """Builds scope prefix from scope and parameters.

        Args:
            scope (_CacheScope): Scope level or path
            params (Dict[str, Any]): Scope parameters

        Returns:
            str: Scope prefix path

        Raises:
            ValueError: If invalid scope type
        """
        if scope == "global":
            return "global"

        target = scope if isinstance(scope, str) else scope[-1]
        self._scope_config.validate_scope_params(target, params)
        return self._scope_config.build_scope_path(params)

    def _make_cache_key(
        self, func_name: str, args_key: Tuple[Any, ...], scope: _CacheScope, kwargs: Dict[str, Any]
    ) -> _CacheKey:
        """Creates cache key for decorated function.

        Args:
            func_name (str): Function name
            args_key (Tuple[Any, ...]): Serialized arguments
            scope (_CacheScope): Cache scope
            kwargs (Dict[str, Any]): Function kwargs (for scope params)

        Returns:
            _CacheKey: Composite cache key
        """
        prefix = self._build_scope_prefix(scope, kwargs)
        return (prefix, func_name, args_key)

    def _make_programmatic_key(self, key: Any, scope: _CacheScope, params: Dict[str, Any]) -> _CacheKey:
        """Creates cache key for programmatic access.

        Args:
            key (Any): User-provided key
            scope (_CacheScope): Cache scope
            params (Dict[str, Any]): Scope parameters

        Returns:
            _CacheKey: Composite cache key
        """
        prefix = self._build_scope_prefix(scope, params)
        return (prefix, "__programmatic__", (key,))

    def cache(
        self, ttl_seconds: Union[int, float], scope: _CacheScope = "global"
    ) -> Callable[[Callable[P, T]], Callable[P, T]]:
        """Decorator for caching function results.

        Args:
            ttl_seconds (Union[int, float]): Time-to-live in seconds
            scope (_CacheScope): Cache scope (default: "global")

        Returns:
            Callable: Decorator function
        """

        def decorator(func: Callable[P, T]) -> Callable[P, T]:
            wrapper = (
                self._create_async_wrapper(func, ttl_seconds, scope)  # type: ignore
                if asyncio.iscoroutinefunction(func)
                else self._create_sync_wrapper(func, ttl_seconds, scope)  # type: ignore
            )
            return wraps(func)(wrapper)  # type: ignore

        return decorator

    def _create_sync_wrapper(self, func: Callable[P, T], ttl_seconds: Union[int, float], scope: _CacheScope) -> Callable[P, T]:
        """Creates synchronous cache wrapper.

        Args:
            func (Callable[P, T]): Function to wrap
            ttl_seconds (Union[int, float]): Time-to-live
            scope (_CacheScope): Cache scope

        Returns:
            Callable[P, T]: Wrapped function
        """

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                args_key = self._make_args_key(*args, **kwargs)
                key = self._make_cache_key(func.__name__, args_key, scope, kwargs)
            except (TypeError, ValueError) as e:
                logging.warning(f"{func.__name__}: {e}. Skipping cache")
                return func(*args, **kwargs)

            cached = self._internal_get(key)
            if cached is not None:
                return cached  # type: ignore

            result = func(*args, **kwargs)
            self._internal_set(key, result, ttl_seconds)
            return result

        return wrapper

    def _create_async_wrapper(
        self, func: Callable[P, T], ttl_seconds: Union[int, float], scope: _CacheScope
    ) -> Callable[P, T]:
        """Creates asynchronous cache wrapper.

        Args:
            func (Callable[P, T]): Async function to wrap
            ttl_seconds (Union[int, float]): Time-to-live
            scope (_CacheScope): Cache scope

        Returns:
            Callable[P, T]: Wrapped async function
        """

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                args_key = self._make_args_key(*args, **kwargs)
                key = self._make_cache_key(func.__name__, args_key, scope, kwargs)
            except (TypeError, ValueError) as e:
                logging.warning(f"{func.__name__}: {e}. Skipping cache")
                return await func(*args, **kwargs)  # type: ignore

            cached = await asyncio.to_thread(self._internal_get, key)
            if cached is not None:
                return cached  # type: ignore

            result = await func(*args, **kwargs)  # type: ignore
            await asyncio.to_thread(self._internal_set, key, result, ttl_seconds)
            return result  # type: ignore

        return wrapper  # type: ignore

    def get(
        self, key: Any, scope: _CacheScope = "global", scope_params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> Optional[Any]:
        """Gets cached value.

        Args:
            key (Any): Cache key
            scope (_CacheScope): Cache scope (default: "global")
            scope_params (Optional[Dict[str, Any]]): Scope parameters
            **kwargs: Additional scope parameters

        Returns:
            Optional[Any]: Cached value or None
        """
        params = {**(scope_params or {}), **kwargs}
        cache_key = self._make_programmatic_key(key, scope, params)
        return self._internal_get(cache_key)

    def set(
        self,
        key: Any,
        value: Any,
        ttl_seconds: Union[int, float],
        scope: _CacheScope = "global",
        scope_params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Sets cached value.

        Args:
            key (Any): Cache key
            value (Any): Value to cache
            ttl_seconds (Union[int, float]): Time-to-live in seconds
            scope (_CacheScope): Cache scope (default: "global")
            scope_params (Optional[Dict[str, Any]]): Scope parameters
            **kwargs: Additional scope parameters

        Raises:
            Exception: If storage operation fails
        """
        params = {**(scope_params or {}), **kwargs}
        cache_key = self._make_programmatic_key(key, scope, params)
        self._internal_set(cache_key, value, ttl_seconds)

    def evict(
        self, key: Any, scope: _CacheScope = "global", scope_params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> None:
        """Evicts cached value.

        Args:
            key (Any): Cache key
            scope (_CacheScope): Cache scope (default: "global")
            scope_params (Optional[Dict[str, Any]]): Scope parameters
            **kwargs: Additional scope parameters
        """
        params = {**(scope_params or {}), **kwargs}
        cache_key = self._make_programmatic_key(key, scope, params)
        self._internal_evict(cache_key)

    def clear(self) -> None:
        """Clears entire cache and resets statistics.

        Raises:
            Exception: If storage operation fails
        """
        self._storage.clear()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        logging.warning("Cache cleared")

    async def aget(
        self, key: Any, scope: _CacheScope = "global", scope_params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> Optional[Any]:
        """Asynchronously gets cached value.

        Args:
            key (Any): Cache key
            scope (_CacheScope): Cache scope (default: "global")
            scope_params (Optional[Dict[str, Any]]): Scope parameters
            **kwargs: Additional scope parameters

        Returns:
            Optional[Any]: Cached value or None
        """
        return await asyncio.to_thread(self.get, key, scope, scope_params, **kwargs)

    async def aset(
        self,
        key: Any,
        value: Any,
        ttl_seconds: Union[int, float],
        scope: _CacheScope = "global",
        scope_params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Asynchronously sets cached value.

        Args:
            key (Any): Cache key
            value (Any): Value to cache
            ttl_seconds (Union[int, float]): Time-to-live in seconds
            scope (_CacheScope): Cache scope (default: "global")
            scope_params (Optional[Dict[str, Any]]): Scope parameters
            **kwargs: Additional scope parameters
        """
        await asyncio.to_thread(self.set, key, value, ttl_seconds, scope, scope_params, **kwargs)

    async def aevict(
        self, key: Any, scope: _CacheScope = "global", scope_params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> None:
        """Asynchronously evicts cached value.

        Args:
            key (Any): Cache key
            scope (_CacheScope): Cache scope (default: "global")
            scope_params (Optional[Dict[str, Any]]): Scope parameters
            **kwargs: Additional scope parameters
        """
        await asyncio.to_thread(self.evict, key, scope, scope_params, **kwargs)

    async def aclear(self) -> None:
        """Asynchronously clears entire cache."""
        await asyncio.to_thread(self.clear)

    def stats(self) -> Dict[str, Any]:
        """Returns cache statistics.

        Returns:
            Dict[str, Any]: Statistics including hits, misses, evictions, and storage-specific stats
        """
        stats = {
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
        }
        stats.update(self._storage.get_stats())
        return stats

    def evict_by_scope(self, scope: _CacheScope, scope_params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> int:
        """Evicts all items in scope.

        Args:
            scope (_CacheScope): Scope to evict
            scope_params (Optional[Dict[str, Any]]): Scope parameters
            **kwargs: Additional scope parameters

        Returns:
            int: Number of items evicted
        """
        params = {**(scope_params or {}), **kwargs}
        try:
            prefix = self._build_scope_prefix(scope, params)
        except ValueError as e:
            logging.error(f"Invalid scope: {e}")
            return 0

        count = 0
        for key in self._storage.get_all_keys():
            if key[0] == prefix or self._scope_config.is_descendant_of(key[0], prefix):
                self._internal_evict(key)
                count += 1

        if count > 0:
            logging.warning(f"Evicted {count} items from scope {prefix}")

        return count


def create_cache(
    backend: Optional[IStorageProvider] = None,
    scope_config: Optional[ScopeConfig] = None,
) -> Cache:
    """Creates and configures cache instance.

    Args:
        backend (Optional[IStorageProvider]): Storage backend (default: InMemory())
        scope_config (Optional[ScopeConfig]): Scope configuration (default: ScopeConfig())

    Returns:
        Cache: Configured cache instance
    """
    return Cache(
        backend=backend or InMemory(),
        scope_config=scope_config or ScopeConfig(),
    )
