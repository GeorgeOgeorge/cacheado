import threading
import time
from unittest.mock import Mock, patch

import pytest

from cache import Cache, create_cache
from cache_scope_config import ScopeConfig, ScopeLevel
from storages.in_memory import InMemory


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_cache_basic_operations(self, cache):
        """Test basic cache operations."""
        cache.set("key1", "value1", 60, "global")
        assert cache.get("key1", "global") == "value1"

    def test_in_memory_storage_error_handling(self):
        """Test InMemory storage error handling."""
        storage = InMemory()
        key = ("global", "test", ("arg",))

        result = storage.get(key)
        assert result is None

        storage.evict(key)

        storage.set(key, "value", 60)
        keys = storage.get_all_keys()
        assert key in keys

    def test_cache_clear(self, cache):
        """Test cache clear."""
        cache.set("key1", "value1", 60, "global")
        cache.clear()
        assert cache.get("key1", "global") is None

    def test_cache_evict_by_scope(self, cache):
        """Test evict_by_scope."""
        cache.set("key1", "value1", 60, "organization", org_id="org1")
        result = cache.evict_by_scope("organization", org_id="org1")
        assert result >= 1

    def test_cache_decorator(self, cache):
        """Test cache decorator."""
        call_count = 0

        @cache.cache(ttl_seconds=60, scope="global")
        def test_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = test_func(5)
        assert result1 == 10
        assert call_count == 1

        result2 = test_func(5)
        assert result2 == 10
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_cache_async_decorator(self, cache):
        """Test async cache decorator."""
        call_count = 0

        @cache.cache(ttl_seconds=60, scope="global")
        async def async_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = await async_func(5)
        assert result1 == 10
        assert call_count == 1

        result2 = await async_func(5)
        assert result2 == 10
        assert call_count == 1

    def test_cache_zero_ttl(self, cache):
        """Test cache with zero TTL."""
        cache.set("key1", "value1", 0, "global")
        result = cache.get("key1", "global")
        assert result is None

    def test_cache_unpickleable_args(self, cache):
        """Test cache with unpickleable arguments."""
        lock = threading.Lock()

        @cache.cache(ttl_seconds=60, scope="global")
        def func_with_lock(x):
            return "result"

        result = func_with_lock(lock)
        assert result == "result"

    def test_cache_programmatic_operations(self, cache):
        """Test programmatic cache operations."""
        cache.set("test_key", "value", 60, scope="organization", org_id="org1")
        result = cache.get("test_key", scope="organization", org_id="org1")
        assert result == "value"

        cache.evict("test_key", scope="organization", org_id="org1")
        result = cache.get("test_key", scope="organization", org_id="org1")
        assert result is None
