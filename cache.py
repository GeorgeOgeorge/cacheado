import asyncio
import logging
import pickle
import threading
import time
from collections import defaultdict
from functools import wraps
from typing import Any, Callable, DefaultDict, Dict, List, Optional, Tuple, Union

from typing_extensions import ParamSpec, TypeVar

from cache_scopes.scope_config import ScopeConfig
from cache_types import _CacheKey, _CacheScope, _CacheValue
from protocols.cache_policy_manager_protocol import ICachePolicyManager
from protocols.storage_provider import IStorageProvider

P = ParamSpec("P")
T = TypeVar("T")


class Cache:
    """
    Cache implementation using Dependency Injection instead of Singleton pattern.

    This class is the central orchestrator. It manages:
    - Tenancy (scoping)
    - Stampede Protection (calculation locks)
    - Statistics (hits/misses)

    It delegates storage to an injected IStorageProvider and
    eviction/cleanup to an injected IEvictionPolicy via the
    CachePolicyManager.
    """

    __slots__ = (
        "_storage",
        "_policy_manager",
        "_scope_config",
        "_calculation_locks",
        "_hits",
        "_misses",
        "_evictions",
        "_instance_lock",
    )

    def __init__(self) -> None:
        """Initializes the cache orchestrator's state."""
        self._storage: Optional[IStorageProvider] = None
        self._policy_manager: Optional[ICachePolicyManager] = None
        self._scope_config: Optional[ScopeConfig] = None
        self._calculation_locks: DefaultDict[_CacheKey, threading.Lock] = defaultdict(threading.Lock)
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0
        self._instance_lock: threading.Lock = threading.Lock()

    def configure(self, backend: IStorageProvider, policy_manager: ICachePolicyManager, scope_config: ScopeConfig) -> None:
        """
        Configures and starts the cache. Must be called once.

        Args:
            backend (IStorageProvider): The storage backend (e.g., InMemoryStorageProvider).
            policy_manager (ICachePolicyManager): Policy manager (required).
            scope_config (ScopeConfig): Scope configuration (defaults to DEFAULT_SCOPE_CONFIG).
        """
        if self._policy_manager is None:
            with self._instance_lock:
                if self._policy_manager is None:
                    self._storage = backend
                    self._scope_config = scope_config
                    self._policy_manager = policy_manager
                    self._policy_manager.start_background_cleanup()
                else:
                    logging.warning("Cache has already been configured.")
        else:
            logging.warning("Cache has already been configured.")

    def _get_all_keys_from_storage(self) -> List[_CacheKey]:
        """
        (Hook) Returns all keys from the injected storage provider.

        Returns:
            List[_CacheKey]: A copy of the current cache keys.
        """
        if self._storage:
            return self._storage.get_all_keys()
        return []

    def _get_value_no_lock_from_storage(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        (Hook) Performs a non-locking read from storage.

        Args:
            key (_CacheKey): The internal key to look up.

        Returns:
            Optional[_CacheValue]: The stored tuple (value, expiry) or None.
        """
        if self._storage:
            return self._storage.get_value_no_lock(key)
        return None

    def _internal_get(self, key: _CacheKey, namespace: str) -> Optional[Any]:
        """
        Orchestrates getting an item. Delegates storage, checks expiry, notifies policy.

        Args:
            key (_CacheKey): The internal key to get.
            namespace (str): The namespace of the key (for policy tracking).

        Returns:
            Optional[Any]: The cached value or None if not found/expired.
        """
        if not self._storage or not self._policy_manager:
            logging.error("Cache used before 'configure()' was called.")
            return None

        value_tuple = self._storage.get(key)

        if value_tuple is None:
            self._misses += 1
            return None

        value, expiry = value_tuple
        current_time = time.monotonic()

        if current_time > expiry:
            self._internal_evict(key, namespace, notify_policy=True)
            self._misses += 1
            return None

        self._hits += 1
        self._policy_manager.notify_get(key, namespace)
        return value

    def _internal_set(
        self, key: _CacheKey, value: Any, ttl_seconds: Union[int, float], namespace: str, max_items: Optional[int]
    ) -> None:
        """
        Orchestrates setting an item.
        Delegates storage, then notifies policy to check limits.

        Args:
            key (_CacheKey): The internal key to set.
            value (Any): The value to store.
            ttl_seconds (Union[int, float]): The time-to-live in seconds.
            namespace (str): The namespace of the key.
            max_items (Optional[int]): The max_items limit for this namespace.
        """
        if not self._storage or not self._policy_manager:
            logging.error("Cache used before 'configure()' was called.")
            return

        if ttl_seconds <= 0:
            return

        expiry = time.monotonic() + ttl_seconds
        self._storage.set(key, (value, expiry))

        key_to_evict = self._policy_manager.notify_set(key, namespace, max_items)
        if key_to_evict:
            evicted_ns = key_to_evict[1]
            self._internal_evict(key_to_evict, evicted_ns, notify_policy=True)

    def _internal_evict(self, key: _CacheKey, namespace: str, notify_policy: bool = True) -> None:
        """
        Orchestrates evicting an item.
        Delegates to storage, cleans up calculation locks, notifies policy.

        Args:
            key (_CacheKey): The internal key to evict.
            namespace (str): The namespace of the key.
            notify_policy (bool): Whether to notify the policy manager.
        """
        if not self._storage or not self._policy_manager:
            logging.error("Cache used before 'configure()' was called.")
            return

        self._storage.evict(key)
        self._evictions += 1

        if key in self._calculation_locks:
            del self._calculation_locks[key]

        if notify_policy:
            self._policy_manager.notify_evict(key, namespace)

    def _make_args_key(self, *args: Any, **kwargs: Any) -> Tuple[Any, ...]:
        """
        Creates a hashable key from function arguments using pickle.

        This method serializes all arguments, including complex objects
        like Pydantic models, dictionaries, and lists, into a stable
        byte representation, which is then wrapped in a tuple to conform
        to the _CacheKey structure.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Tuple[Any, ...]: A hashable tuple containing the serialized arguments.

        Raises:
            TypeError: If the arguments cannot be serialized by pickle,
                which is caught by the cache wrappers to skip caching.
        """
        try:
            key_representation = (args, tuple(sorted(kwargs.items())))
            serialized_key = pickle.dumps(key_representation, protocol=pickle.HIGHEST_PROTOCOL)
        except (pickle.PicklingError, TypeError) as e:
            logging.warning(f"Failed to serialize arguments for caching. Object may be unpickleable: {e}")
            raise TypeError(f"Unhashable (unpickleable) arguments: {e}")

        return (serialized_key,)

    def _get_scope_prefix(self, scope: _CacheScope, scope_params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> str:
        """
        Gets the tenancy prefix based on the scope using the configured scope hierarchy.

        Args:
            scope (_CacheScope): The scope level name or tuple of scope path.
            scope_params (Optional[Dict[str, Any]]): Parameters for scope construction.
            **kwargs: Additional parameters (for backward compatibility).

        Returns:
            str: The scope prefix path.
        """
        all_params = scope_params or {}
        all_params.update(kwargs)

        if not self._scope_config:
            raise RuntimeError("Cache not configured")

        if scope == "global":
            return "global"

        if isinstance(scope, str):
            self._scope_config.validate_scope_params(scope, all_params)
            return self._scope_config.build_scope_path(all_params)
        elif isinstance(scope, tuple):
            target_level = scope[-1]
            self._scope_config.validate_scope_params(target_level, all_params)
            return self._scope_config.build_scope_path(all_params)
        else:
            raise ValueError(f"Invalid scope type: {type(scope)}")

    def _make_cache_key(
        self, func_name: str, args_key: Tuple[Any, ...], scope: _CacheScope, func_kwargs: Dict[str, Any]
    ) -> _CacheKey:
        """
        Creates the final composite key for decorated functions.

        Args:
            func_name (str): The name of the decorated function.
            args_key (Tuple[Any, ...]): The hashable key from function args.
            scope (_CacheScope): The scope for this cache entry.
            func_kwargs (Dict[str, Any]): The kwargs passed to the function (to find scope params).

        Returns:
            _CacheKey: The final composite internal key.
        """
        prefix = self._get_scope_prefix(scope, scope_params=func_kwargs)
        return (prefix, func_name, args_key)

    def _make_programmatic_key(
        self, key: Any, scope: _CacheScope, scope_params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> _CacheKey:
        """
        Creates the final composite key for programmatic access.

        Args:
            key (Any): The public key provided by the user.
            scope (_CacheScope): The scope for this cache entry.
            scope_params (Optional[Dict[str, Any]]): Parameters for scope construction.
            **kwargs: Additional parameters (for backward compatibility).

        Returns:
            _CacheKey: The final composite internal key.
        """
        all_params = scope_params or {}
        all_params.update(kwargs)
        prefix = self._get_scope_prefix(scope, scope_params=all_params)
        namespace = "__programmatic__"
        return (prefix, namespace, (key,))

    def cache(
        self, ttl_seconds: Union[int, float], scope: _CacheScope = "global", max_items: Optional[int] = None
    ) -> Callable[[Callable[P, T]], Callable[P, T]]:
        """
        Decorator factory for caching function results with proper type preservation.

        Args:
            ttl_seconds (Union[int, float]): Time-to-live (in seconds) for cached items.
            scope (_CacheScope): The cache scope ('global', 'organization', 'user').
                If 'organization' or 'user', the decorated function MUST
                accept `organization_id` or `user_id` as a kwarg.
            max_items (Optional[int]): Max number of items to cache for this specific
                function.

        Returns:
            Callable: A decorator function that preserves the original function signature.
        """

        def _decorator(func: Callable[P, T]) -> Callable[P, T]:
            namespace = func.__name__

            wrapper = (
                self._create_async_wrapper(func, ttl_seconds, scope, namespace, max_items)  # type: ignore
                if asyncio.iscoroutinefunction(func)
                else self._create_sync_wrapper(func, ttl_seconds, scope, namespace, max_items)  # type: ignore
            )

            return wraps(func)(wrapper)  # type: ignore

        return _decorator

    def _create_sync_wrapper(
        self,
        func: Callable[P, T],
        ttl_seconds: Union[int, float],
        scope: _CacheScope,
        namespace: str,
        max_items: Optional[int],
    ) -> Callable[P, T]:
        """
        Creates sync wrapper with stampede protection and proper type preservation.

        Args:
            func (Callable): The synchronous function to wrap.
            ttl_seconds (Union[int, float]): The TTL for cache entries.
            scope (_CacheScope): The scope for this function.
            namespace (str): The namespace (function name) for policy tracking.
            max_items (Optional[int]): The max_items limit for this namespace.

        Returns:
            Callable: The wrapped synchronous function with preserved signature.
        """

        @wraps(func)
        def _sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                args_key = self._make_args_key(*args, **kwargs)
                key = self._make_cache_key(func.__name__, args_key, scope, kwargs)
            except TypeError as e:
                logging.warning(f"Unhashable arguments in {func.__name__}: {e}. Skipping cache.")
                return func(*args, **kwargs)
            except ValueError as e:
                logging.warning(f"Cache scope error for {func.__name__}: {e}. Skipping cache.")
                return func(*args, **kwargs)

            cached_value = self._internal_get(key, namespace)
            if cached_value is not None:
                return cached_value  # type: ignore

            calc_lock = self._calculation_locks[key]

            with calc_lock:
                try:
                    cached_value = self._internal_get(key, namespace)
                    if cached_value is not None:
                        return cached_value  # type: ignore

                    logging.info(f"Cache miss and calculation for key: {key}")
                    new_value = func(*args, **kwargs)

                    self._internal_set(key, new_value, ttl_seconds, namespace, max_items)
                    return new_value
                except Exception as e:
                    logging.error(f"Error in cache wrapper for {func.__name__}: {e}")
                    return func(*args, **kwargs)  # type: ignore

        return _sync_wrapper

    def _create_async_wrapper(
        self,
        func: Callable[P, T],
        ttl_seconds: Union[int, float],
        scope: _CacheScope,
        namespace: str,
        max_items: Optional[int],
    ) -> Callable[P, T]:
        """
        Creates async wrapper with stampede protection and proper type preservation.

        Args:
            func (Callable): The asynchronous function to wrap.
            ttl_seconds (Union[int, float]): The TTL for cache entries.
            scope (_CacheScope): The scope for this function.
            namespace (str): The namespace (function name) for policy tracking.
            max_items (Optional[int]): The max_items limit for this namespace.

        Returns:
            Callable: The wrapped asynchronous function with preserved signature.
        """

        @wraps(func)
        async def _async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                args_key = self._make_args_key(*args, **kwargs)
                key = self._make_cache_key(func.__name__, args_key, scope, kwargs)
            except TypeError as e:
                logging.warning(f"Unhashable arguments in {func.__name__}: {e}. Skipping cache.")
                return await func(*args, **kwargs)  # type: ignore[misc,no-any-return]
            except ValueError as e:
                logging.warning(f"Cache scope error for {func.__name__}: {e}. Skipping cache.")
                return await func(*args, **kwargs)  # type: ignore[misc,no-any-return]

            cached_value = await asyncio.to_thread(self._internal_get, key, namespace)
            if cached_value is not None:
                return cached_value  # type: ignore

            calc_lock = self._calculation_locks[key]

            await asyncio.to_thread(calc_lock.acquire)
            try:
                try:
                    cached_value = await asyncio.to_thread(self._internal_get, key, namespace)
                    if cached_value is not None:
                        return cached_value  # type: ignore

                    logging.info(f"Cache miss and calculation for key: {key}")
                    new_value = await func(*args, **kwargs)  # type: ignore

                    await asyncio.to_thread(self._internal_set, key, new_value, ttl_seconds, namespace, max_items)
                    return new_value  # type: ignore[no-any-return]
                except Exception as e:
                    logging.error(f"Error in async cache wrapper for {func.__name__}: {e}")
                    return await func(*args, **kwargs)  # type: ignore[misc,no-any-return]
            finally:
                calc_lock.release()

        return _async_wrapper  # type: ignore

    def get(
        self, key: Any, scope: _CacheScope = "global", scope_params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> Optional[Any]:
        """
        Gets an item programmatically from the cache.

        Args:
            key (Any): The key to look up (must be hashable).
            scope (_CacheScope): The scope level or path.
            scope_params (Optional[Dict[str, Any]]): Parameters for scope construction.
            **kwargs: Additional parameters (for backward compatibility).

        Returns:
            Optional[Any]: The cached value or None if not found or expired.
        """
        try:
            cache_key = self._make_programmatic_key(key, scope, scope_params=scope_params, **kwargs)
            namespace = cache_key[1]
            return self._internal_get(cache_key, namespace)
        except Exception as e:
            logging.error(f"Error in cache get operation: {e}")
            return None

    def set(
        self,
        key: Any,
        value: Any,
        ttl_seconds: Union[int, float],
        scope: _CacheScope = "global",
        scope_params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Sets an item programmatically in the cache.

        Args:
            key (Any): The key (must be hashable).
            value (Any): The value to store.
            ttl_seconds (Union[int, float]): Time-to-live in seconds.
            scope (_CacheScope): The scope level or path.
            scope_params (Optional[Dict[str, Any]]): Parameters for scope construction.
            **kwargs: Additional parameters (for backward compatibility).
        """
        try:
            cache_key = self._make_programmatic_key(key, scope, scope_params=scope_params, **kwargs)
            namespace = cache_key[1]
            self._internal_set(cache_key, value, ttl_seconds, namespace, max_items=None)
        except Exception as e:
            logging.error(f"Error in cache set operation: {e}")
            raise

    def evict(
        self, key: Any, scope: _CacheScope = "global", scope_params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> None:
        """
        Removes a specific item programmatically from the cache.

        Args:
            key (Any): The key to remove (must be hashable).
            scope (_CacheScope): The scope level or path.
            scope_params (Optional[Dict[str, Any]]): Parameters for scope construction.
            **kwargs: Additional parameters (for backward compatibility).
        """
        try:
            cache_key = self._make_programmatic_key(key, scope, scope_params=scope_params, **kwargs)
            namespace = cache_key[1]
            self._internal_evict(cache_key, namespace, notify_policy=True)
        except Exception as e:
            logging.error(f"Error in cache evict operation: {e}")

    def clear(self) -> None:
        """
        Safely clears the entire cache (storage and policy).
        """
        try:
            with self._instance_lock:
                if self._storage:
                    self._storage.clear()

                if self._policy_manager:
                    self._policy_manager.notify_clear()

                self._calculation_locks.clear()
                self._hits = 0
                self._misses = 0
                self._evictions = 0

                logging.warning("Cache has been cleared.")
        except Exception as e:
            logging.error(f"Error clearing cache: {e}")
            raise

    async def aget(
        self, key: Any, scope: _CacheScope = "global", scope_params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> Optional[Any]:
        """
        Asynchronously gets an item programmatically from the cache.
        (Runs the synchronous 'get' in a separate thread).

        Args:
            key (Any): The key to look up (must be hashable).
            scope (_CacheScope): The scope level or path.
            scope_params (Optional[Dict[str, Any]]): Parameters for scope construction.
            **kwargs: Additional parameters (for backward compatibility).

        Returns:
            Optional[Any]: The cached value or None.
        """
        return await asyncio.to_thread(self.get, key, scope=scope, scope_params=scope_params, **kwargs)

    async def aset(
        self,
        key: Any,
        value: Any,
        ttl_seconds: Union[int, float],
        scope: _CacheScope = "global",
        scope_params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Asynchronously sets an item programmatically in the cache.
        (Runs the synchronous 'set' in a separate thread).

        Args:
            key (Any): The key (must be hashable).
            value (Any): The value to store.
            ttl_seconds (Union[int, float]): Time-to-live in seconds.
            scope (_CacheScope): The scope level or path.
            scope_params (Optional[Dict[str, Any]]): Parameters for scope construction.
            **kwargs: Additional parameters (for backward compatibility).
        """
        await asyncio.to_thread(self.set, key, value, ttl_seconds, scope=scope, scope_params=scope_params, **kwargs)

    async def aevict(
        self, key: Any, scope: _CacheScope = "global", scope_params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> None:
        """
        Asynchronously removes a specific item programmatically.
        (Runs the synchronous 'evict' in a separate thread).

        Args:
            key (Any): The key to remove (must be hashable).
            scope (_CacheScope): The scope level or path.
            scope_params (Optional[Dict[str, Any]]): Parameters for scope construction.
            **kwargs: Additional parameters (for backward compatibility).
        """
        await asyncio.to_thread(self.evict, key, scope=scope, scope_params=scope_params, **kwargs)

    async def aclear(self) -> None:
        """
        Asynchronously clears the entire cache.
        (Runs the synchronous 'clear' in a separate thread).
        """
        await asyncio.to_thread(self.clear)

    def stats(self) -> Dict[str, Any]:
        """
        Returns a dictionary of cache observability statistics.

        Returns:
            Dict[str, Any]: A dict containing keys like 'hits', 'misses',
            'evictions', 'current_size', etc.
        """
        with self._instance_lock:
            g_size = 0
            ns_count = 0
            if self._policy_manager:
                g_size = self._policy_manager.get_global_size()
                ns_count = self._policy_manager.get_namespace_count()

            return {
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "current_size": g_size,
                "tracked_namespaces": ns_count,
                "total_calc_locks": len(self._calculation_locks),
            }

    def evict_by_scope(self, scope: _CacheScope, scope_params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> int:
        """
        Granularly evicts all items belonging to a specific scope.

        Example:
            evict_by_scope("organization", scope_params={"organization_id": "org_123"})

        Args:
            scope (_CacheScope): The scope to target.
            scope_params (Optional[Dict[str, Any]]): Parameters for scope construction.
            **kwargs: Additional parameters (for backward compatibility).

        Returns:
            int: The number of items successfully evicted.
        """
        if not self._storage or not self._policy_manager or not self._scope_config:
            logging.error("Cache used before 'configure()' was called.")
            return 0

        try:
            all_params = scope_params or {}
            all_params.update(kwargs)
            prefix = self._get_scope_prefix(scope, scope_params=all_params)
        except ValueError as e:
            logging.error(f"Failed to evict by scope: {e}")
            return 0

        all_keys = self._storage.get_all_keys()
        evicted_count = 0

        for key in all_keys:
            if key[0] == prefix or (self._scope_config and self._scope_config.is_descendant_of(key[0], prefix)):
                namespace = key[1]
                self._internal_evict(key, namespace, notify_policy=True)
                evicted_count += 1

        if evicted_count > 0:
            logging.warning(f"Evicted {evicted_count} items for scope: {prefix}")

        return evicted_count


def create_cache(
    backend: IStorageProvider, policy_manager: ICachePolicyManager, scope_config: Optional[ScopeConfig] = None
) -> Cache:
    """
    Factory function to create and configure a Cache instance.

    This replaces the Singleton pattern with explicit dependency injection.

    Args:
        backend: Storage backend (required)
        policy_manager: Policy manager (required)
        scope_config: Scope configuration

    Returns:
        Configured Cache instance
    """
    cache = Cache()

    if hasattr(policy_manager, "_cache") and policy_manager._cache is None:
        policy_manager._cache = cache

    cache.configure(backend=backend, policy_manager=policy_manager, scope_config=scope_config or ScopeConfig())
    return cache
