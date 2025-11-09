import asyncio
import pytest
import time
import threading
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cache import Cache, create_cache
from cache_types import _CacheKey


class TestCache:
    """Test cases for the main Cache class."""

    def test_cache_initialization(self):
        """Test cache initialization."""
        cache = Cache()
        assert cache._storage is None
        assert cache._policy_manager is None
        assert cache._scope_config is None
        assert cache._hits == 0
        assert cache._misses == 0
        assert cache._evictions == 0

    def test_cache_configuration(self, storage, policy_manager, scope_config):
        """Test cache configuration."""
        cache = Cache()
        cache.configure(storage, policy_manager, scope_config)
        
        assert cache._storage is storage
        assert cache._policy_manager is policy_manager
        assert cache._scope_config is scope_config

    def test_basic_get_set(self, cache):
        """Test basic get/set operations."""
        cache.set("test_key", "test_value", 60, "global")
        result = cache.get("test_key", "global")
        assert result == "test_value"

    def test_get_nonexistent_key(self, cache):
        """Test getting non-existent key returns None."""
        result = cache.get("nonexistent", "global")
        assert result is None

    def test_ttl_expiration(self, cache):
        """Test TTL expiration."""
        cache.set("expire_key", "value", 0.1, "global")
        time.sleep(0.2)
        result = cache.get("expire_key", "global")
        assert result is None

    def test_scoped_cache(self, cache):
        """Test scoped cache operations."""
        cache.set("key", "org_value", 60, "organization", org_id="org_123")
        cache.set("key", "user_value", 60, "user", org_id="org_123", user_id="user_456")
        
        org_result = cache.get("key", "organization", org_id="org_123")
        user_result = cache.get("key", "user", org_id="org_123", user_id="user_456")
        
        assert org_result == "org_value"
        assert user_result == "user_value"

    def test_cache_decorator_sync(self, cache):
        """Test synchronous cache decorator."""
        call_count = 0
        
        @cache.cache(ttl_seconds=60, scope="global")
        def test_func(x, y):
            nonlocal call_count
            call_count += 1
            return x + y
        
        result1 = test_func(1, 2)
        result2 = test_func(1, 2)
        
        assert result1 == 3
        assert result2 == 3
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_cache_decorator_async(self, cache):
        """Test asynchronous cache decorator."""
        call_count = 0
        
        @cache.cache(ttl_seconds=60, scope="global")
        async def async_func(x):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return x * 2
        
        result1 = await async_func(5)
        result2 = await async_func(5)
        
        assert result1 == 10
        assert result2 == 10
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_operations(self, cache):
        """Test async get/set operations."""
        await cache.aset("async_key", "async_value", 60, "global")
        result = await cache.aget("async_key", "global")
        assert result == "async_value"

    def test_evict_by_scope(self, cache):
        """Test scope-based eviction."""
        cache.set("data1", "value1", 60, "organization", org_id="org_123")
        cache.set("data2", "value2", 60, "organization", org_id="org_456")
        cache.set("data3", "value3", 60, "user", org_id="org_123", user_id="user_789")
        
        evicted = cache.evict_by_scope("organization", org_id="org_123")
        assert evicted >= 1
        
        result1 = cache.get("data1", "organization", org_id="org_123")
        result2 = cache.get("data2", "organization", org_id="org_456")
        
        assert result1 is None
        assert result2 == "value2"

    def test_clear_cache(self, cache):
        """Test cache clearing."""
        cache.set("key1", "value1", 60, "global")
        cache.set("key2", "value2", 60, "global")
        
        assert cache.get("key1", "global") == "value1"
        assert cache.get("key2", "global") == "value2"
        
        cache.clear()
        
        assert cache.get("key1", "global") is None
        assert cache.get("key2", "global") is None
        
        stats = cache.stats()
        assert stats["current_size"] == 0  # Cache should be empty

    def test_stats(self, cache):
        """Test cache statistics."""
        initial_stats = cache.stats()
        initial_hits = initial_stats["hits"]
        initial_misses = initial_stats["misses"]
        
        cache.set("key1", "value1", 60, "global")
        result = cache.get("key1", "global")
        assert result == "value1"
        
        cache.get("nonexistent", "global")
        
        stats = cache.stats()
        assert stats["hits"] >= initial_hits + 1
        assert stats["misses"] >= initial_misses + 1
        assert "current_size" in stats
        assert "tracked_namespaces" in stats

    def test_thread_safety(self, cache):
        """Test thread safety with concurrent operations."""
        call_count = 0
        
        @cache.cache(ttl_seconds=60, scope="global")
        def thread_func(x):
            nonlocal call_count
            call_count += 1
            time.sleep(0.1)
            return x * 2
        
        def worker():
            return thread_func(10)
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker) for _ in range(5)]
            results = [f.result() for f in futures]
        
        assert all(r == 20 for r in results)
        assert call_count == 1

    def test_unpickleable_args(self, cache):
        """Test handling of unpickleable arguments."""
        call_count = 0
        
        @cache.cache(ttl_seconds=60, scope="global")
        def func_with_unpickleable(func_arg):
            nonlocal call_count
            call_count += 1
            return "result"
        
        import threading
        unpickleable_obj = threading.Lock()
        
        result1 = func_with_unpickleable(unpickleable_obj)
        result2 = func_with_unpickleable(unpickleable_obj)
        assert result1 == "result"
        assert result2 == "result"
        assert call_count == 2

    def test_invalid_scope_params(self, cache):
        """Test invalid scope parameters."""
        with pytest.raises(ValueError):
            cache.set("key", "value", 60, "organization")  # Missing org_id

    def test_zero_ttl(self, cache):
        """Test zero TTL handling."""
        cache.set("key", "value", 0, "global")
        result = cache.get("key", "global")
        assert result is None

    def test_namespace_limits(self, cache):
        """Test namespace-specific limits."""
        @cache.cache(ttl_seconds=60, scope="global", max_items=2)
        def limited_func(x):
            return x
        
        # Fill beyond limit
        for i in range(5):
            limited_func(i)
        
        stats = cache.stats()
        assert stats["evictions"] > 0

    def test_make_args_key_error_handling(self, cache):
        """Test error handling in _make_args_key."""
        import threading
        unpickleable_obj = threading.Lock()
        
        with pytest.raises(TypeError):
            cache._make_args_key(unpickleable_obj)

    def test_scope_prefix_generation(self, cache):
        """Test scope prefix generation."""
        prefix = cache._get_scope_prefix("global")
        assert prefix == "global"
        
        prefix = cache._get_scope_prefix("organization", org_id="org_123")
        assert prefix == "organization:org_123"

    def test_programmatic_key_creation(self, cache):
        """Test programmatic key creation."""
        key = cache._make_programmatic_key("test", "global")
        assert key[0] == "global"
        assert key[1] == "__programmatic__"
        assert key[2] == ("test",)

    def test_cache_key_creation(self, cache):
        """Test cache key creation for decorated functions."""
        args_key = cache._make_args_key(1, 2, name="test")
        key = cache._make_cache_key("func_name", args_key, "global", {})
        
        assert key[0] == "global"
        assert key[1] == "func_name"
        assert key[2] == args_key

    def test_evict_operation(self, cache):
        """Test evict operation."""
        cache.set("evict_key", "value", 60, "global")
        assert cache.get("evict_key", "global") == "value"
        
        cache.evict("evict_key", "global")
        assert cache.get("evict_key", "global") is None

    @pytest.mark.asyncio
    async def test_async_evict_and_clear(self, cache):
        """Test async evict and clear operations."""
        await cache.aset("key", "value", 60, "global")
        await cache.aevict("key", "global")
        result = await cache.aget("key", "global")
        assert result is None
        
        await cache.aset("key2", "value2", 60, "global")
        await cache.aclear()
        result = await cache.aget("key2", "global")
        assert result is None

    def test_create_cache_factory(self, storage, policy_manager, scope_config):
        """Test create_cache factory function."""
        cache = create_cache(storage, policy_manager, scope_config)
        assert isinstance(cache, Cache)
        assert cache._storage is storage
        assert cache._policy_manager is policy_manager
        assert cache._scope_config is scope_config

    def test_cache_without_configuration(self):
        """Test cache operations without configuration."""
        cache = Cache()
        
        result = cache.get("key", "global")
        assert result is None
        
        try:
            cache.set("key", "value", 60, "global")
        except RuntimeError:
            pass
        
        result = cache.get("key", "global")
        assert result is None

    def test_decorator_with_scope_params(self, cache):
        """Test decorator with scope parameters."""
        @cache.cache(ttl_seconds=60, scope="user")
        def user_func(data, org_id=None, user_id=None):
            return f"result_{data}_{user_id}"
        
        result = user_func("test", org_id="org_123", user_id="user_456")
        assert result == "result_test_user_456"

    def test_multiple_scope_hierarchies(self, cache):
        """Test multiple scope hierarchies."""
        cache.set("tenant_data", "value", 60, "tenant", tenant_id="tenant_123")
        cache.set("project_data", "value", 60, "project", 
                 tenant_id="tenant_123", project_id="proj_456")
        
        tenant_result = cache.get("tenant_data", "tenant", tenant_id="tenant_123")
        project_result = cache.get("project_data", "project", 
                                  tenant_id="tenant_123", project_id="proj_456")
        
        assert tenant_result == "value"
        assert project_result == "value"