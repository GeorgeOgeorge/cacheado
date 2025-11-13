import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from cache import create_cache
from cache_policies.cache_policy_manager import CachePolicyManager
from cache_scopes.scope_config import ScopeConfig, ScopeLevel
from eviction_policies.lre_eviction import LRUEvictionPolicy
from storages.in_memory import InMemory


class TestIntegration:
    """Integration tests for the complete cache system."""

    def test_full_system_integration(self):
        """Test complete system working together."""

        scope_config = ScopeConfig([ScopeLevel("organization", "org_id", [ScopeLevel("user", "user_id")])])

        storage = InMemory()
        eviction_policy = LRUEvictionPolicy()
        policy_manager = CachePolicyManager(cleanup_interval=1, policy=eviction_policy, max_size=10)

        cache = create_cache(storage, policy_manager, scope_config)

        cache.set("key1", "value1", 60, "global")
        assert cache.get("key1", "global") == "value1"

        cache.set("key2", "org_value", 60, "organization", org_id="org_123")
        cache.set("key3", "user_value", 60, "user", org_id="org_123", user_id="user_456")

        assert cache.get("key2", "organization", org_id="org_123") == "org_value"
        assert cache.get("key3", "user", org_id="org_123", user_id="user_456") == "user_value"

        evicted = cache.evict_by_scope("organization", org_id="org_123")
        assert evicted >= 1

        policy_manager.stop_background_cleanup()

    def test_decorator_integration(self):
        """Test decorator integration with full system."""
        cache = create_cache(
            InMemory(),
            CachePolicyManager(1, LRUEvictionPolicy(), 100),
            ScopeConfig([ScopeLevel("organization", "org_id")]),
        )

        call_count = 0

        @cache.cache(ttl_seconds=60, scope="organization")
        def expensive_function(data, org_id=None):
            nonlocal call_count
            call_count += 1
            return f"result_{data}_{org_id}"

        result1 = expensive_function("test", org_id="org_123")
        assert result1 == "result_test_org_123"
        assert call_count == 1

        result2 = expensive_function("test", org_id="org_123")
        assert result2 == "result_test_org_123"
        assert call_count == 1

        result3 = expensive_function("test", org_id="org_456")
        assert result3 == "result_test_org_456"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_async_integration(self):
        """Test async operations integration."""
        cache = create_cache(InMemory(), CachePolicyManager(1, LRUEvictionPolicy(), 100), ScopeConfig())

        await cache.aset("async_key", "async_value", 60, "global")
        result = await cache.aget("async_key", "global")
        assert result == "async_value"

        call_count = 0

        @cache.cache(ttl_seconds=60, scope="global")
        async def async_function(x):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return x * 2

        result1 = await async_function(5)
        result2 = await async_function(5)

        assert result1 == 10
        assert result2 == 10
        assert call_count == 1

    def test_eviction_policy_integration(self):
        """Test eviction policy integration with cache."""
        cache = create_cache(InMemory(), CachePolicyManager(1, LRUEvictionPolicy(), 3), ScopeConfig())

        for i in range(5):
            cache.set(f"key_{i}", f"value_{i}", 60, "global")

        stats = cache.stats()
        assert stats["evictions"] > 0
        assert stats["current_size"] <= 3

    def test_ttl_expiration_integration(self):
        """Test TTL expiration with background cleanup."""
        cache = create_cache(InMemory(), CachePolicyManager(0.1, LRUEvictionPolicy(), 100), ScopeConfig())

        cache.set("expire_key", "value", 0.2, "global")
        assert cache.get("expire_key", "global") == "value"

        time.sleep(0.5)

        result = cache.get("expire_key", "global")
        assert result is None

    def test_concurrent_operations_integration(self):
        """Test concurrent operations across the system."""
        cache = create_cache(
            InMemory(),
            CachePolicyManager(1, LRUEvictionPolicy(), 1000),
            ScopeConfig([ScopeLevel("organization", "org_id")]),
        )

        results = []
        lock = threading.Lock()

        def worker(worker_id):
            cache.set(f"key_{worker_id}", f"value_{worker_id}", 60, "global")
            cache.set(f"org_key_{worker_id}", f"org_value_{worker_id}", 60, "organization", org_id=f"org_{worker_id}")

            result1 = cache.get(f"key_{worker_id}", "global")
            result2 = cache.get(f"org_key_{worker_id}", "organization", org_id=f"org_{worker_id}")

            with lock:
                results.append((worker_id, result1, result2))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, i) for i in range(10)]
            for future in futures:
                future.result()

        assert len(results) == 10
        results.sort(key=lambda x: x[0])
        for worker_id, result1, result2 in results:
            assert result1 == f"value_{worker_id}"
            assert result2 == f"org_value_{worker_id}"

    def test_stampede_protection_integration(self):
        """Test stampede protection in real scenario."""
        cache = create_cache(InMemory(), CachePolicyManager(1, LRUEvictionPolicy(), 100), ScopeConfig())

        call_count = 0

        @cache.cache(ttl_seconds=60, scope="global")
        def slow_function(x):
            nonlocal call_count
            call_count += 1
            time.sleep(0.2)
            return x * 2

        def worker():
            return slow_function(42)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker) for _ in range(10)]
            results = [f.result() for f in futures]

        assert all(r == 84 for r in results)

        assert call_count == 1

    def test_namespace_limits_integration(self):
        """Test namespace-specific limits integration."""
        cache = create_cache(InMemory(), CachePolicyManager(1, LRUEvictionPolicy(), 100), ScopeConfig())

        @cache.cache(ttl_seconds=60, scope="global", max_items=3)
        def limited_function(x):
            return x

        for i in range(10):
            limited_function(i)

        stats = cache.stats()

        assert stats["evictions"] > 0

    def test_multiple_scope_hierarchies_integration(self):
        """Test multiple scope hierarchies working together."""
        scope_config = ScopeConfig(
            [
                ScopeLevel("organization", "org_id", [ScopeLevel("user", "user_id")]),
                ScopeLevel("tenant", "tenant_id", [ScopeLevel("project", "project_id")]),
            ]
        )

        cache = create_cache(InMemory(), CachePolicyManager(1, LRUEvictionPolicy(), 100), scope_config)

        cache.set("org_data", "org_value", 60, "organization", org_id="org_123")
        cache.set("user_data", "user_value", 60, "user", org_id="org_123", user_id="user_456")
        cache.set("tenant_data", "tenant_value", 60, "tenant", tenant_id="tenant_123")
        cache.set("project_data", "project_value", 60, "project", tenant_id="tenant_123", project_id="proj_456")

        assert cache.get("org_data", "organization", org_id="org_123") == "org_value"
        assert cache.get("user_data", "user", org_id="org_123", user_id="user_456") == "user_value"
        assert cache.get("tenant_data", "tenant", tenant_id="tenant_123") == "tenant_value"
        assert cache.get("project_data", "project", tenant_id="tenant_123", project_id="proj_456") == "project_value"

        evicted_org = cache.evict_by_scope("organization", org_id="org_123")
        evicted_tenant = cache.evict_by_scope("tenant", tenant_id="tenant_123")

        assert evicted_org >= 1
        assert evicted_tenant >= 1

    def test_error_recovery_integration(self):
        """Test system recovery from various error conditions."""
        cache = create_cache(
            InMemory(),
            CachePolicyManager(1, LRUEvictionPolicy(), 100),
            ScopeConfig([ScopeLevel("organization", "org_id")]),
        )

        call_count = 0

        @cache.cache(ttl_seconds=60, scope="global")
        def func_with_unpickleable(obj):
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

        try:
            cache.set("key", "value", 60, "organization")
        except ValueError:
            pass

        cache.set("normal_key", "normal_value", 60, "global")
        assert cache.get("normal_key", "global") == "normal_value"

    def test_statistics_integration(self):
        """Test statistics collection across the system."""
        storage = InMemory()
        eviction_policy = LRUEvictionPolicy()
        policy_manager = CachePolicyManager(cleanup_interval=1, policy=eviction_policy, max_size=5)

        cache = create_cache(storage, policy_manager, ScopeConfig())

        initial_stats = cache.stats()
        initial_hits = initial_stats["hits"]
        initial_misses = initial_stats["misses"]
        initial_evictions = initial_stats["evictions"]

        for i in range(10):
            cache.set(f"key_{i}", f"value_{i}", 60, "global")

        for i in range(5):
            result = cache.get(f"key_{i}", "global")
            if result is not None:
                assert result == f"value_{i}"

        for i in range(15, 20):
            cache.get(f"key_{i}", "global")

        stats = cache.stats()

        assert stats["hits"] >= initial_hits
        assert stats["misses"] >= initial_misses + 5
        assert stats["evictions"] >= initial_evictions + 5
        assert stats["current_size"] <= 5
        assert "tracked_namespaces" in stats
        assert "total_calc_locks" in stats

        policy_manager.stop_background_cleanup()

    @pytest.mark.asyncio
    async def test_mixed_sync_async_integration(self):
        """Test mixing synchronous and asynchronous operations."""
        cache = create_cache(InMemory(), CachePolicyManager(1, LRUEvictionPolicy(), 100), ScopeConfig())

        cache.set("sync_key", "sync_value", 60, "global")

        await cache.aset("async_key", "async_value", 60, "global")

        sync_result = cache.get("sync_key", "global")
        async_result = await cache.aget("async_key", "global")
        cross_result1 = cache.get("async_key", "global")
        cross_result2 = await cache.aget("sync_key", "global")

        assert sync_result == "sync_value"
        assert async_result == "async_value"
        assert cross_result1 == "async_value"
        assert cross_result2 == "sync_value"

    def test_cache_clear_integration(self):
        """Test cache clearing across all components."""
        cache = create_cache(
            InMemory(),
            CachePolicyManager(1, LRUEvictionPolicy(), 100),
            ScopeConfig([ScopeLevel("organization", "org_id")]),
        )

        cache.set("global_key", "global_value", 60, "global")
        cache.set("org_key", "org_value", 60, "organization", org_id="org_123")

        assert cache.get("global_key", "global") == "global_value"
        assert cache.get("org_key", "organization", org_id="org_123") == "org_value"

        cache.clear()

        assert cache.get("global_key", "global") is None
        assert cache.get("org_key", "organization", org_id="org_123") is None

        stats = cache.stats()
        assert stats["current_size"] == 0
