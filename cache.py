import asyncio
import logging
import pickle
from functools import wraps
from typing import Any, Callable, Dict, Iterable, Optional, Tuple, Union

from typing_extensions import ParamSpec, TypeVar

from protocols.storage_provider import IStorageProvider
from protocols.storage_rule import IStorageRule
from storages.in_memory import InMemory
from storages.rule_aware_storage import RuleAwareStorage
from utils.cache_scope_config import ScopeConfig
from utils.cache_types import CacheKey, _CacheScope

P = ParamSpec("P")
T = TypeVar("T")


class Cache:
    """High-performance Cache Manager with support for scope strategies and pluggable storages.

    Attributes:
        _storage (IStorageProvider): The storage backend (Redis, Memcached, Memory, etc.).
        _scope_config (ScopeConfig): Configuration rules for scope-based key resolution.
        _storage_rules (Tuple[IStorageRule, ...]): Optional storage rules for side effects.
        _hits (int): Counter for cache hits (for telemetry).
        _misses (int): Counter for cache misses (for telemetry).
        _evictions (int): Counter for manual evictions (for telemetry).
    """

    __slots__ = ("_storage", "_scope_config", "_hits", "_misses", "_evictions")

    def __init__(
        self,
        scope_config: Optional[ScopeConfig] = None,
        storage_provider: Optional[IStorageProvider] = None,
        storage_rules: Optional[Iterable[IStorageRule]] = None,
    ) -> None:
        """Initializes the Cache manager with Dependency Injection.

        Args:
            storage_provider (Optional[IStorageProvider]): Implementation of the storage protocol.
                If None, uses `InMemory`.
            scope_config (Optional[ScopeConfig]): Configuration for dynamic scope resolution.
                If None, uses the default configuration.
            storage_rules (Optional[Iterable[IStorageRule, ...]]): Optional storage rules for side effects.
        """
        _provider = storage_provider or InMemory()

        self._storage = RuleAwareStorage(_provider, storage_rules) if storage_rules else _provider
        self._scope_config = scope_config or ScopeConfig()
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0
        logging.info(f"Cache initialized with backend: {self._storage.__class__.__name__}")

    def _get_from_storage(self, key: CacheKey) -> Optional[Any]:
        """Retrieves a value from the underlying storage using a structured key.

        Converts the `CacheKey` object to its string representation before querying the backend.
        Manages hit/miss counters internally.

        Args:
            key (CacheKey): The structured unique key of the item.

        Returns:
            Optional[Any]: The cached value if found and valid (TTL), otherwise None.
        """
        value_tuple = self._storage.get(key.as_string())
        if value_tuple is None:
            self._misses += 1
            return None

        self._hits += 1
        return value_tuple[0]

    def _set_in_storage(self, key: CacheKey, value: Any, ttl_seconds: Union[int, float]) -> None:
        """Persists a value in the underlying storage.

        Args:
            key (CacheKey): The structured unique key.
            value (Any): The data to be stored. Must be serializable by the chosen backend.
            ttl_seconds (Union[int, float]): Time-to-live in seconds.
        """
        if ttl_seconds <= 0:
            return

        self._storage.set(key.as_string(), value, ttl_seconds)

    def _evict_from_storage(self, key: CacheKey) -> None:
        """Removes a specific item from storage.

        Args:
            key (CacheKey): The structured key of the item to remove.
        """
        self._storage.evict(key.as_string())
        self._evictions += 1

    def _make_args_key(self, *args: Any, **kwargs: Any) -> Tuple[Any, ...]:
        """Serializes function arguments to create a unique signature (hashable).

        Args:
            *args: Positional arguments of the decorated function.
            **kwargs: Keyword arguments of the decorated function.

        Returns:
            Tuple[Any, ...]: A tuple containing the serialized bytes of the arguments.

        Raises:
            TypeError: If any argument cannot be serialized (pickled).
        """
        try:
            key_repr = (args, tuple(sorted(kwargs.items())))
            return (pickle.dumps(key_repr, protocol=pickle.HIGHEST_PROTOCOL),)
        except (pickle.PicklingError, TypeError) as e:
            logging.warning(f"Failed to serialize arguments for cache key: {e}")
            raise TypeError(f"Unhashable/non-serializable arguments: {e}")

    def _build_scope_prefix(self, scope: _CacheScope, params: Dict[str, Any]) -> str:
        """Constructs the scope prefix based on configuration and runtime parameters.

        Args:
            scope (_CacheScope): The logical scope name (e.g., 'global', 'user', 'tenant').
            params (Dict[str, Any]): Dictionary of parameters (usually kwargs) to resolve the scope.

        Returns:
            str: The resolved prefix for the cache key.
        """
        if scope == "global":
            return "global"

        target = scope if isinstance(scope, str) else scope[-1]
        self._scope_config.validate_scope_params(target, params)
        return self._scope_config.build_scope_path(params)

    def _compose_cache_key(self, scope_prefix: str, namespace: str, args_key: Tuple[Any, ...]) -> CacheKey:
        """Factory method to create a CacheKey instance.

        Args:
            scope_prefix (str): The resolved scope part.
            namespace (str): The logical namespace (function name or identifier).
            args_key (Tuple[Any, ...]): The tuple of serialized arguments.

        Returns:
            CacheKey: The constructed key object.
        """
        return CacheKey(scope_prefix, namespace, args_key)

    def _make_cache_key(
        self, func_name: str, args_key: Tuple[Any, ...], scope: _CacheScope, kwargs: Dict[str, Any]
    ) -> CacheKey:
        """Orchestrates the creation of a CacheKey for a decorated function.

        Args:
            func_name (str): Name of the function being cached.
            args_key (Tuple[Any, ...]): Serialized arguments.
            scope (_CacheScope): Scope definition.
            kwargs (Dict[str, Any]): Function kwargs (used to extract scope IDs).

        Returns:
            CacheKey: The complete cache key.
        """
        prefix = self._build_scope_prefix(scope, kwargs)
        return self._compose_cache_key(prefix, func_name, args_key)

    def _make_programmatic_key(self, key: Any, scope: _CacheScope, params: Dict[str, Any]) -> CacheKey:
        """Orchestrates the creation of a CacheKey for manual calls (get/set).

        Args:
            key (Any): The user-provided identifier.
            scope (_CacheScope): Scope definition.
            params (Dict[str, Any]): Parameters for scope resolution.

        Returns:
            CacheKey: The complete cache key.
        """
        prefix = self._build_scope_prefix(scope, params)
        return self._compose_cache_key(prefix, "__programmatic__", (key,))

    def cache(
        self, ttl_seconds: Union[int, float], scope: _CacheScope = "global"
    ) -> Callable[[Callable[P, T]], Callable[P, T]]:
        """Decorator Factory to cache function results based on arguments and scope.

        Automatically detects if the decorated function is synchronous or asynchronous (coroutine)
        and applies the appropriate wrapper, maintaining type compatibility.

        Args:
            ttl_seconds (Union[int, float]): Cache time-to-live in seconds.
            scope (_CacheScope, optional): The scope level (e.g., "user", "global"). Defaults to "global".

        Returns:
            Callable[[Callable[P, T]], Callable[P, T]]: The configured decorator.
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
        """Creates a wrapper for synchronous (blocking) functions.

        Args:
            func (Callable[P, T]): The original function.
            ttl_seconds (Union[int, float]): TTL.
            scope (_CacheScope): Scope.

        Returns:
            Callable[P, T]: Wrapper with caching logic.
        """

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                args_key = self._make_args_key(*args, **kwargs)
                key = self._make_cache_key(func.__name__, args_key, scope, kwargs)
            except (TypeError, ValueError) as e:
                logging.warning(f"{func.__name__}: {e}. Skipping cache")
                return func(*args, **kwargs)

            cached = self._get_from_storage(key)
            if cached is not None:
                return cached  # type: ignore

            result = func(*args, **kwargs)
            self._set_in_storage(key, result, ttl_seconds)
            return result

        return wrapper

    def _create_async_wrapper(
        self, func: Callable[P, T], ttl_seconds: Union[int, float], scope: _CacheScope
    ) -> Callable[P, T]:
        """Creates a wrapper for asynchronous functions (coroutines).

        Args:
            func (Callable[P, T]): The original coroutine.
            ttl_seconds (Union[int, float]): TTL.
            scope (_CacheScope): Scope.

        Returns:
            Callable[P, T]: Async wrapper with caching logic.
        """

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                args_key = self._make_args_key(*args, **kwargs)
                key = self._make_cache_key(func.__name__, args_key, scope, kwargs)
            except (TypeError, ValueError) as e:
                logging.warning(f"{func.__name__}: {e}. Skipping cache")
                return await func(*args, **kwargs)  # type: ignore

            cached = await asyncio.to_thread(self._get_from_storage, key)
            if cached is not None:
                return cached  # type: ignore

            result = await func(*args, **kwargs)  # type: ignore
            await asyncio.to_thread(self._set_in_storage, key, result, ttl_seconds)
            return result  # type: ignore

        return wrapper  # type: ignore

    def get(
        self, key: Any, scope: _CacheScope = "global", scope_params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> Optional[Any]:
        """Retrieves a value from the cache manually (programmatic access).

        Args:
            key (Any): The unique identifier of the data (e.g., "my_key").
            scope (_CacheScope): Cache scope (default: "global").
            scope_params (Optional[Dict[str, Any]]): Dict of parameters to resolve the scope.
            **kwargs: Scope parameters as kwargs (merged with scope_params).

        Returns:
            Optional[Any]: Cached value or None.

        Examples:
            >>> cache.get("user_data", scope="user", user_id="456")
        """
        params = {**(scope_params or {}), **kwargs}
        cache_key = self._make_programmatic_key(key, scope, params)
        return self._get_from_storage(cache_key)

    def set(
        self,
        key: Any,
        value: Any,
        ttl_seconds: Union[int, float],
        scope: _CacheScope = "global",
        scope_params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Sets a value in the cache manually.

        Args:
            key (Any): The unique identifier.
            value (Any): The data to be cached.
            ttl_seconds (Union[int, float]): TTL in seconds.
            scope (_CacheScope): Scope (default: "global").
            scope_params (Optional[Dict[str, Any]]): Dict of scope parameters.
            **kwargs: Scope parameters as kwargs.
        """
        params = {**(scope_params or {}), **kwargs}
        cache_key = self._make_programmatic_key(key, scope, params)
        self._set_in_storage(cache_key, value, ttl_seconds)

    def evict(
        self, key: Any, scope: _CacheScope = "global", scope_params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> None:
        """Manually removes an item from the cache.

        Args:
            key (Any): The identifier of the item to remove.
            scope (_CacheScope): Scope.
            scope_params (Optional[Dict[str, Any]]): Dict of scope parameters.
            **kwargs: Scope parameters as kwargs.
        """
        params = {**(scope_params or {}), **kwargs}
        cache_key = self._make_programmatic_key(key, scope, params)
        self._evict_from_storage(cache_key)

    def clear(self) -> None:
        """Clears the ENTIRE cache storage and resets internal statistics."""
        self._storage.clear()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        logging.warning("Cache cleared completely")

    async def aget(
        self, key: Any, scope: _CacheScope = "global", scope_params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> Optional[Any]:
        """Asynchronous version (non-blocking) of `get`. Delegates execution of the synchronous `get` method to
        a separate thread, ensuring the asyncio Event Loop is not blocked by storage I/O.

        Args:
            key (Any): Identifier.
            scope (_CacheScope): Scope.
            scope_params (Optional[Dict[str, Any]]): Scope parameters.
            **kwargs: Scope kwargs.

        Returns:
            Optional[Any]: Value or None.
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
        """Asynchronous version (non-blocking) of `set`. Executes the write to storage in a separate thread.

        Args:
            key (Any): Identifier.
            value (Any): Value.
            ttl_seconds (Union[int, float]): TTL.
            scope (_CacheScope): Scope.
            scope_params (Optional[Dict[str, Any]]): Scope parameters.
            **kwargs: Scope kwargs.
        """
        await asyncio.to_thread(self.set, key, value, ttl_seconds, scope, scope_params, **kwargs)

    async def aevict(
        self, key: Any, scope: _CacheScope = "global", scope_params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> None:
        """Asynchronous version (non-blocking) of `evict`.

        Args:
            key (Any): Identifier.
            scope (_CacheScope): Scope.
            scope_params (Optional[Dict[str, Any]]): Scope parameters.
            **kwargs: Scope kwargs.
        """
        await asyncio.to_thread(self.evict, key, scope, scope_params, **kwargs)

    async def aclear(self) -> None:
        """Asynchronous version (non-blocking) of `clear`."""
        await asyncio.to_thread(self.clear)

    def stats(self) -> Dict[str, Any]:
        """Returns cache usage statistics. Combines internal metrics (hits/misses in object memory) with statistics
        reported by the storage backend.

        Returns:
            Dict[str, Any]: Dict containing keys like 'hits', 'misses', 'evictions'.
        """
        stats = {
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
        }
        stats.update(self._storage.get_stats())
        return stats

    def evict_by_scope(self, scope: _CacheScope, scope_params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> int:
        """Evicts all cache items belonging to a specific scope hierarchy.

        Args:
            scope (_CacheScope): The target scope to clear.
            scope_params (Optional[Dict[str, Any]]): Parameters to resolve the scope prefix.
            **kwargs: Additional parameters.

        Returns:
            int: Number of items removed.
        """
        params = {**(scope_params or {}), **kwargs}
        try:
            prefix = self._build_scope_prefix(scope, params)
        except ValueError as e:
            logging.error(f"Invalid scope for eviction: {e}")
            return 0

        count = 0
        for key_str in self._storage.get_all_keys():
            cache_key = CacheKey.from_string(key_str)
            if cache_key.scope_prefix == prefix or self._scope_config.is_descendant_of(cache_key.scope_prefix, prefix):
                self._evict_from_storage(cache_key)
                count += 1

        if count > 0:
            logging.warning(f"Evicted {count} items from scope {prefix}")

        return count
