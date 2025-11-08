import asyncio
import logging
import pickle
import threading
import time
from collections import defaultdict
from functools import wraps
from typing import Any, Callable, DefaultDict, Dict, Optional, Tuple, Union, cast

from typing_extensions import Self

from cache_policies.cache_policy_manager import CachePolicyManager
from eviction_policies.lre_eviction import LRUEvictionPolicy
from protocols.eviction_policy import IEvictionPolicy
from protocols.storage_provider import IStorageProvider
from storages.in_memory import InMemory
from cache_types import _CacheKey, _CacheScope, _CacheValue, _FuncT


class Cache:
    """
    Singleton implementation of the ICache protocol.
    
    This class is the central orchestrator. It manages:
    - Tenancy (scoping)
    - Stampede Protection (calculation locks)
    - Statistics (hits/misses)
    
    It delegates storage to an injected IStorageProvider and
    eviction/cleanup to an injected IEvictionPolicy via the
    CachePolicyManager.
    """
    _instance: Optional[Self] = None
    _instance_lock: threading.Lock = threading.Lock()
    _storage: Optional[IStorageProvider]
    _policy_manager: Optional[CachePolicyManager]
    _calculation_locks: DefaultDict[_CacheKey, threading.Lock]
    _hits: int
    _misses: int
    _evictions: int

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        """
        Implements the thread-safe Singleton pattern.

        Args:
            *args: Positional arguments (ignored).
            **kwargs: Keyword arguments (ignored).
        """
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_cache()
        return cls._instance

    @classmethod
    def instance(cls) -> Self:
        """Convenience access method to get the Singleton instance.

        Returns:
            The unique instance of the Cache.
        """
        return cls()

    def _init_cache(self) -> None:
        """Initializes the orchestrator's state."""
        self._storage = None
        self._policy_manager = None
        self._calculation_locks = defaultdict(threading.Lock)
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def configure(
        self,
        backend: IStorageProvider,
        policy: IEvictionPolicy,
        max_size: int = 1000,
        cleanup_interval: int = 60
    ) -> None:
        """
        Configures and starts the cache. Must be called once.

        Args:
            backend (IStorageProvider): The storage backend (e.g., InMemoryStorageProvider).
            policy (IEvictionPolicy): The eviction policy (e.g., LRUEvictionPolicy).
            max_size (int): Max number of items to store globally. Defaults to 1000.
            cleanup_interval (int): Interval (in seconds) for background cleanup. Defaults to 60.
        """
        if self._policy_manager is None:
            with self._instance_lock:
                if self._policy_manager is None:
                    self._storage = backend
                    self._policy_manager = CachePolicyManager(
                        cache_instance=self,
                        cleanup_interval=cleanup_interval,
                        policy=policy,
                        max_size=max_size
                    )
                    self._policy_manager.start_background_cleanup()
                else:
                    logging.warning("Cache has already been configured.")
        else:
            logging.warning("Cache has already been configured.")

    def _get_all_keys_from_storage(self) -> list[_CacheKey]:
        """
        (Hook) Returns all keys from the injected storage provider.
        
        Returns:
            list[_CacheKey]: A copy of the current cache keys.
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
            return None

        value, expiry = value_tuple
        
        if time.monotonic() > expiry:
            self._internal_evict(key, namespace, notify_policy=True)
            return None

        self._hits += 1
        self._policy_manager.notify_get(key, namespace)
        return value

    def _internal_set(
        self,
        key: _CacheKey,
        value: Any,
        ttl_seconds: Union[int, float],
        namespace: str,
        max_items: Optional[int]
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
            serialized_key = pickle.dumps(key_representation,  protocol=pickle.HIGHEST_PROTOCOL)
        except (pickle.PicklingError, TypeError) as e:
            logging.warning(f"Failed to serialize arguments for caching. Object may be unpickleable: {e}")
            raise TypeError(f"Unhashable (unpickleable) arguments: {e}")
        
        return (serialized_key, )

    def _get_scope_prefix(
        self,
        scope: _CacheScope,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> str:
        """
        Gets the tenancy prefix based on the scope.
        
        Args:
            scope (_CacheScope): The scope ('global', 'organization', 'user').
            organization_id (Optional[str]): ID required for 'organization' scope.
            user_id (Optional[str]): ID required for 'user' scope.

        Returns:
            str: The scope prefix (e.g., "org:123").
        """
        match scope:
            case "organization":
                if organization_id is None:
                    raise ValueError(
                        "Organization scope requested, but 'organization_id' was not provided"
                        + " where the function was called."
                    )
                return f"org:{organization_id}"
            
            case "user":
                if user_id is None:
                    raise ValueError(
                        "User scope requested, but 'user_id' was not provided where the function was called."
                    )
                return f"user:{user_id}"
            
            case "global":
                return "global"
            
            case _:
                raise ValueError(f"Unknown cache scope: {scope}")

    def _make_cache_key(
        self,
        func_name: str,
        args_key: Tuple[Any, ...],
        scope: _CacheScope,
        func_kwargs: Dict[str, Any]
    ) -> _CacheKey:
        """
        Creates the final composite key for decorated functions.
        
        Args:
            func_name (str): The name of the decorated function.
            args_key (Tuple[Any, ...]): The hashable key from function args.
            scope (_CacheScope): The scope for this cache entry.
            func_kwargs (Dict[str, Any]): The kwargs passed to the function (to find tenant IDs).

        Returns:
            _CacheKey: The final composite internal key.
        """
        org_id = func_kwargs.get("organization_id")
        usr_id = func_kwargs.get("user_id")
        prefix = self._get_scope_prefix(scope, organization_id=org_id, user_id=usr_id)
        return (prefix, func_name, args_key)

    def _make_programmatic_key(
        self,
        key: Any,
        scope: _CacheScope,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> _CacheKey:
        """
        Creates the final composite key for programmatic access.
        
        Args:
            key (Any): The public key provided by the user.
            scope (_CacheScope): The scope for this cache entry.
            organization_id (Optional[str]): ID required for 'organization' scope.
            user_id (Optional[str]): ID required for 'user' scope.

        Returns:
            _CacheKey: The final composite internal key.
        """
        prefix = self._get_scope_prefix(scope, organization_id=organization_id, user_id=user_id)
        namespace = "__programmatic__"
        return (prefix, namespace, (key,))

    def cache(
        self,
        ttl_seconds: Union[int, float],
        scope: _CacheScope = "global",
        max_items: Optional[int] = None
    ) -> Callable[[_FuncT], _FuncT]:
        """
        Decorator factory for caching function results.

        Args:
            ttl_seconds (Union[int, float]): Time-to-live (in seconds) for cached items.
            scope (_CacheScope): The cache scope ('global', 'organization', 'user').
                If 'organization' or 'user', the decorated function MUST
                accept `organization_id` or `user_id` as a kwarg.
            max_items (Optional[int]): Max number of items to cache for this specific
                function.

        Returns:
            Callable[[_FuncT], _FuncT]: A decorator function.
        """
        def _decorator(func: _FuncT) -> _FuncT:
            namespace = func.__name__ 
            
            if asyncio.iscoroutinefunction(func):
                wrapper = self._create_async_wrapper(func, ttl_seconds, scope, namespace, max_items)
            else:
                wrapper = self._create_sync_wrapper(func, ttl_seconds, scope, namespace, max_items)
            
            wrapped_func = wraps(func)(wrapper)
            return cast(_FuncT, wrapped_func)
        return _decorator

    def _create_sync_wrapper(
        self,
        func: Callable[..., Any],
        ttl_seconds: Union[int, float],
        scope: _CacheScope,
        namespace: str,
        max_items: Optional[int]
    ) -> Callable[..., Any]:
        """
        Creates sync wrapper with stampede protection.
        
        Args:
            func (Callable): The synchronous function to wrap.
            ttl_seconds (Union[int, float]): The TTL for cache entries.
            scope (_CacheScope): The scope for this function.
            namespace (str): The namespace (function name) for policy tracking.
            max_items (Optional[int]): The max_items limit for this namespace.

        Returns:
            Callable[..., Any]: The wrapped synchronous function.
        """
        def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
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
                return cached_value

            self._misses += 1
            calc_lock = self._calculation_locks[key]
            
            with calc_lock:
                cached_value = self._internal_get(key, namespace)
                if cached_value is not None:
                    return cached_value

                logging.info(f"Cache miss and calculation for key: {key}")
                new_value = func(*args, **kwargs)
                
                self._internal_set(key, new_value, ttl_seconds, namespace, max_items)
                return new_value
        return _sync_wrapper

    def _create_async_wrapper(
        self,
        func: Callable[..., Any],
        ttl_seconds: Union[int, float],
        scope: _CacheScope,
        namespace: str,
        max_items: Optional[int]
    ) -> Callable[..., Any]:
        """
        Creates async wrapper with stampede protection.

        Args:
            func (Callable): The asynchronous function to wrap.
            ttl_seconds (Union[int, float]): The TTL for cache entries.
            scope (_CacheScope): The scope for this function.
            namespace (str): The namespace (function name) for policy tracking.
            max_items (Optional[int]): The max_items limit for this namespace.

        Returns:
            Callable[..., Any]: The wrapped asynchronous function.
        """
        async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                args_key = self._make_args_key(*args, **kwargs)
                key = self._make_cache_key(func.__name__, args_key, scope, kwargs)
            except TypeError as e:
                logging.warning(f"Unhashable arguments in {func.__name__}: {e}. Skipping cache.")
                return await func(*args, **kwargs)  
            except ValueError as e:
                logging.warning(f"Cache scope error for {func.__name__}: {e}. Skipping cache.")
                return await func(*args, **kwargs)
            
            cached_value = await asyncio.to_thread(self._internal_get, key, namespace)
            if cached_value is not None:
                return cached_value

            self._misses += 1
            calc_lock = self._calculation_locks[key]
            
            await asyncio.to_thread(calc_lock.acquire)
            try:
                cached_value = await asyncio.to_thread(self._internal_get, key, namespace)
                if cached_value is not None:
                    return cached_value

                logging.info(f"Cache miss and calculation for key: {key}")
                new_value = await func(*args, **kwargs)
                
                await asyncio.to_thread(
                    self._internal_set, key, new_value, ttl_seconds, namespace, max_items
                )
                return new_value
            finally:
                calc_lock.release()
        return _async_wrapper

    def get(
        self,
        key: Any,
        scope: _CacheScope = "global",
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None
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
        cache_key = self._make_programmatic_key(key, scope, organization_id=organization_id, user_id=user_id)
        namespace = cache_key[1]
        return self._internal_get(cache_key, namespace)

    def set(
        self,
        key: Any,
        value: Any,
        ttl_seconds: Union[int, float],
        scope: _CacheScope = "global",
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None
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
        cache_key = self._make_programmatic_key(key, scope, organization_id=organization_id, user_id=user_id)
        namespace = cache_key[1]
        self._internal_set(cache_key, value, ttl_seconds, namespace, max_items=None)

    def evict(
        self,
        key: Any,
        scope: _CacheScope = "global",
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> None:
        """
        Removes a specific item programmatically from the cache.

        Args:
            key (Any): The key to remove (must be hashable).
            scope (_CacheScope): The scope ('global', 'organization', 'user').
            organization_id (Optional[str]): Required if scope='organization'.
            user_id (Optional[str]): Required if scope='user'.
        """
        cache_key = self._make_programmatic_key(key, scope, organization_id=organization_id, user_id=user_id)
        namespace = cache_key[1]
        self._internal_evict(cache_key, namespace, notify_policy=True)

    def clear(self) -> None:
        """
        Safely clears the entire cache (storage and policy).
        """
        with self._instance_lock:
            if self._storage:
                self._storage.clear()
            
            if self._policy_manager:
                self._policy_manager.notify_clear()
            
            # Reset stats and calculation locks
            self._calculation_locks.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0

            logging.warning("Cache has been cleared.")

    async def aget(
        self,
        key: Any,
        scope: _CacheScope = "global",
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Optional[Any]:
        """
        Asynchronously gets an item programmatically from the cache.
        (Runs the synchronous 'get' in a separate thread).

        Args:
            key (Any): The key to look up (must be hashable).
            scope (_CacheScope): The scope ('global', 'organization', 'user').
            organization_id (Optional[str]): Required if scope='organization'.
            user_id (Optional[str]): Required if scope='user'.

        Returns:
            Optional[Any]: The cached value or None.
        """
        return await asyncio.to_thread(self.get, key, scope=scope, organization_id=organization_id, user_id=user_id)

    async def aset(
        self,
        key: Any,
        value: Any,
        ttl_seconds: Union[int, float],
        scope: _CacheScope = "global",
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> None:
        """
        Asynchronously sets an item programmatically in the cache.
        (Runs the synchronous 'set' in a separate thread).

        Args:
            key (Any): The key (must be hashable).
            value (Any): The value to store.
            ttl_seconds (Union[int, float]): Time-to-live in seconds.
            scope (_CacheScope): The scope ('global', 'organization', 'user').
            organization_id (Optional[str]): Required if scope='organization'.
            user_id (Optional[str]): Required if scope='user'.
        """
        await asyncio.to_thread(
            self.set, key, value, ttl_seconds, scope=scope, organization_id=organization_id, user_id=user_id
        )

    async def aevict(
        self,
        key: Any,
        scope: _CacheScope = "global",
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> None:
        """
        Asynchronously removes a specific item programmatically.
        (Runs the synchronous 'evict' in a separate thread).

        Args:
            key (Any): The key to remove (must be hashable).
            scope (_CacheScope): The scope ('global', 'organization', 'user').
            organization_id (Optional[str]): Required if scope='organization'.
            user_id (Optional[str]): Required if scope='user'.
        """
        await asyncio.to_thread(self.evict, key, scope=scope, organization_id=organization_id, user_id=user_id)

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

    def evict_by_scope(
        self,
        scope: _CacheScope,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> int:
        """
        Granularly evicts all items belonging to a specific tenant.

        Example:
            evict_by_scope("organization", organization_id="org_123")

        Args:
            scope (_CacheScope): The scope to target ('organization' or 'user').
            organization_id (Optional[str]): Required if scope='organization'.
            user_id (Optional[str]): Required if scope='user'.

        Returns:
            int: The number of items successfully evicted.
        """
        if not self._storage:
            logging.error("Cache used before 'configure()' was called.")
            return 0
            
        try:
            prefix = self._get_scope_prefix(scope, organization_id=organization_id, user_id=user_id)
        except ValueError as e:
            logging.error(f"Failed to evict by scope: {e}")
            return 0
        
        all_keys = self._storage.get_all_keys()
        
        keys_to_evict = [key for key in all_keys if key[0] == prefix]
        
        if keys_to_evict:
            logging.warning(f"Evicting {len(keys_to_evict)} items for scope: {prefix}")
            for key in keys_to_evict:
                namespace = key[1]
                self._internal_evict(key, namespace, notify_policy=True)
        
        return len(keys_to_evict)


in_memory = Cache.instance()
in_memory.configure(backend=InMemory(), policy=LRUEvictionPolicy())
