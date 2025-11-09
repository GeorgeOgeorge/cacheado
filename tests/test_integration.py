import asyncio
import pytest
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cache import create_cache
from storages.in_memory import InMemory
from eviction_policies.lre_eviction import LRUEvictionPolicy
from cache_policies.cache_policy_manager import CachePolicyManager
from cache_scopes.scope_config import ScopeConfig, ScopeLevel


class TestIntegration:
    """Integration tests for the complete cache system."""

    def test_full_system_integration(self):
        """Test complete system working together."""
        # Setup
        scope_config = ScopeConfig([
            ScopeLevel("organization", "org_id", [
                ScopeLevel("user", "user_id")
            ])
        ])
        
        storage = InMemory()
        eviction_policy = LRUEvictionPolicy()
        policy_manager = CachePolicyManager(
            cache_instance=None,
            cleanup_interval=1,
            policy=eviction_policy,
            max_size=10
        )
        
        cache = create_cache(storage, policy_manager, scope_config)
        
        # Test basic operations
        cache.set("key1", "value1", 60, "global")
        assert cache.get("key1", "global") == "value1"
        
        # Test scoped operations
        cache.set("key2", "org_value", 60, "organization", org_id="org_123")
        cache.set("key3", "user_value", 60, "user", org_id="org_123", user_id="user_456")
        
        assert cache.get("key2", "organization", org_id="org_123") == "org_value"
        assert cache.get("key3", "user", org_id="org_123", user_id="user_456") == "user_value"
        
        # Test eviction by scope
        evicted = cache.evict_by_scope("organization", org_id="org_123")
        assert evicted >= 1
        
        # Cleanup
        policy_manager.stop_background_cleanup()

    def test_decorator_integration(self):
        """Test decorator integration with full system."""
        cache = create_cache(
            InMemory(),
            CachePolicyManager(None, 1, LRUEvictionPolicy(), 100),
            ScopeConfig([ScopeLevel("organization", "org_id")])
        )
        
        call_count = 0
        
        @cache.cache(ttl_seconds=60, scope="organization")
        def expensive_function(data, org_id=None):
            nonlocal call_count
            call_count += 1
            return f"result_{data}_{org_id}"
        
        # First call
        result1 = expensive_function("test", org_id="org_123")
        assert result1 == "result_test_org_123"
        assert call_count == 1
        
        # Second call (should use cache)
        result2 = expensive_function("test", org_id="org_123")
        assert result2 == "result_test_org_123"
        assert call_count == 1
        
        # Different org (should call function)
        result3 = expensive_function("test", org_id="org_456")
        assert result3 == "result_test_org_456"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_async_integration(self):
        """Test async operations integration."""
        cache = create_cache(
            InMemory(),
            CachePolicyManager(None, 1, LRUEvictionPolicy(), 100),
            ScopeConfig()
        )
        
        # Async programmatic operations
        await cache.aset("async_key", "async_value", 60, "global")
        result = await cache.aget("async_key", "global")
        assert result == "async_value"
        
        # Async decorator
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
        cache = create_cache(
            InMemory(),
            CachePolicyManager(None, 1, LRUEvictionPolicy(), 3),  # Small limit
            ScopeConfig()
        )
        
        # Fill cache beyond limit
        for i in range(5):
            cache.set(f"key_{i}", f"value_{i}", 60, "global")
        
        stats = cache.stats()
        assert stats["evictions"] > 0
        assert stats["current_size"] <= 3

    def test_ttl_expiration_integration(self):
        """Test TTL expiration with background cleanup."""
        cache = create_cache(
            InMemory(),
            CachePolicyManager(None, 0.1, LRUEvictionPolicy(), 100),  # Fast cleanup
            ScopeConfig()
        )
        
        # Set item with short TTL
        cache.set("expire_key", "value", 0.2, "global")
        assert cache.get("expire_key", "global") == "value"
        
        # Wait for expiration and cleanup
        time.sleep(0.5)
        
        result = cache.get("expire_key", "global")
        assert result is None

    def test_concurrent_operations_integration(self):
        """Test concurrent operations across the system."""
        cache = create_cache(
            InMemory(),
            CachePolicyManager(None, 1, LRUEvictionPolicy(), 1000),
            ScopeConfig([ScopeLevel("organization", "org_id")])
        )
        
        results = []
        
        def worker(worker_id):
            # Mix of operations
            cache.set(f"key_{worker_id}", f"value_{worker_id}", 60, "global")
            cache.set(f"org_key_{worker_id}", f"org_value_{worker_id}", 60, 
                     "organization", org_id=f"org_{worker_id}")
            
            result1 = cache.get(f"key_{worker_id}", "global")
            result2 = cache.get(f"org_key_{worker_id}", "organization", 
                               org_id=f"org_{worker_id}")
            
            results.append((result1, result2))
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, i) for i in range(10)]
            for future in futures:
                future.result()
        
        assert len(results) == 10
        for i, (result1, result2) in enumerate(results):
            assert result1 == f"value_{i}"
            assert result2 == f"org_value_{i}"

    def test_stampede_protection_integration(self):
        """Test stampede protection in real scenario."""
        cache = create_cache(
            InMemory(),
            CachePolicyManager(None, 1, LRUEvictionPolicy(), 100),
            ScopeConfig()
        )
        
        call_count = 0
        
        @cache.cache(ttl_seconds=60, scope="global")
        def slow_function(x):
            nonlocal call_count
            call_count += 1
            time.sleep(0.2)  # Simulate slow operation
            return x * 2
        
        def worker():
            return slow_function(42)
        
        # Multiple threads calling same function simultaneously
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker) for _ in range(10)]
            results = [f.result() for f in futures]
        
        # All should get same result
        assert all(r == 84 for r in results)
        # Function should only be called once due to stampede protection
        assert call_count == 1

    def test_namespace_limits_integration(self):
        """Test namespace-specific limits integration."""
        cache = create_cache(
            InMemory(),
            CachePolicyManager(None, 1, LRUEvictionPolicy(), 100),
            ScopeConfig()
        )
        
        @cache.cache(ttl_seconds=60, scope="global", max_items=3)
        def limited_function(x):
            return x
        
        # Fill beyond namespace limit
        for i in range(10):
            limited_function(i)
        
        stats = cache.stats()
        # Should have evictions due to namespace limit
        assert stats["evictions"] > 0

    def test_multiple_scope_hierarchies_integration(self):
        """Test multiple scope hierarchies working together."""
        scope_config = ScopeConfig([
            ScopeLevel("organization", "org_id", [
                ScopeLevel("user", "user_id")
            ]),
            ScopeLevel("tenant", "tenant_id", [
                ScopeLevel("project", "project_id")
            ])
        ])
        
        cache = create_cache(
            InMemory(),
            CachePolicyManager(None, 1, LRUEvictionPolicy(), 100),
            scope_config
        )
        
        # Test both hierarchies
        cache.set("org_data", "org_value", 60, "organization", org_id="org_123")
        cache.set("user_data", "user_value", 60, "user", 
                 org_id="org_123", user_id="user_456")
        cache.set("tenant_data", "tenant_value", 60, "tenant", tenant_id="tenant_123")
        cache.set("project_data", "project_value", 60, "project", 
                 tenant_id="tenant_123", project_id="proj_456")
        
        # Verify all data
        assert cache.get("org_data", "organization", org_id="org_123") == "org_value"
        assert cache.get("user_data", "user", org_id="org_123", user_id="user_456") == "user_value"
        assert cache.get("tenant_data", "tenant", tenant_id="tenant_123") == "tenant_value"
        assert cache.get("project_data", "project", 
                        tenant_id="tenant_123", project_id="proj_456") == "project_value"
        
        # Test scope-based eviction
        evicted_org = cache.evict_by_scope("organization", org_id="org_123")
        evicted_tenant = cache.evict_by_scope("tenant", tenant_id="tenant_123")
        
        assert evicted_org >= 1
        assert evicted_tenant >= 1

    def test_error_recovery_integration(self):
        """Test system recovery from various error conditions."""
        cache = create_cache(
            InMemory(),
            CachePolicyManager(None, 1, LRUEvictionPolicy(), 100),
            ScopeConfig([ScopeLevel("organization", "org_id")])
        )
        
        # Test unpickleable arguments
        @cache.cache(ttl_seconds=60, scope="global")
        def func_with_unpickleable(func_arg):
            return "result"
        
        # Should not crash
        result = func_with_unpickleable(lambda x: x)
        assert result == "result"
        
        # Test invalid scope parameters
        try:
            cache.set("key", "value", 60, "organization")  # Missing org_id
        except ValueError:
            pass  # Expected
        
        # Cache should still work normally
        cache.set("normal_key", "normal_value", 60, "global")
        assert cache.get("normal_key", "global") == "normal_value"

    def test_statistics_integration(self):
        """Test statistics collection across the system."""
        cache = create_cache(
            InMemory(),
            CachePolicyManager(None, 1, LRUEvictionPolicy(), 5),  # Small limit for evictions
            ScopeConfig()
        )
        
        # Generate various activities
        for i in range(10):
            cache.set(f"key_{i}", f"value_{i}", 60, "global")
        
        for i in range(15):
            cache.get(f"key_{i % 8}", "global")  # Some hits, some misses
        
        stats = cache.stats()
        
        assert stats["hits"] > 0
        assert stats["misses"] > 0
        assert stats["evictions"] > 0
        assert stats["current_size"] <= 5
        assert "tracked_namespaces" in stats
        assert "total_calc_locks" in stats

    @pytest.mark.asyncio
    async def test_mixed_sync_async_integration(self):
        """Test mixing synchronous and asynchronous operations."""
        cache = create_cache(
            InMemory(),
            CachePolicyManager(None, 1, LRUEvictionPolicy(), 100),
            ScopeConfig()
        )
        
        # Sync operations
        cache.set("sync_key", "sync_value", 60, "global")
        
        # Async operations
        await cache.aset("async_key", "async_value", 60, "global")
        
        # Mixed retrieval
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
            CachePolicyManager(None, 1, LRUEvictionPolicy(), 100),
            ScopeConfig([ScopeLevel("organization", "org_id")])
        )
        
        # Add data to various scopes
        cache.set("global_key", "global_value", 60, "global")
        cache.set("org_key", "org_value", 60, "organization", org_id="org_123")
        
        # Verify data exists
        assert cache.get("global_key", "global") == "global_value"
        assert cache.get("org_key", "organization", org_id="org_123") == "org_value"
        
        # Clear cache
        cache.clear()
        
        # Verify all data is gone
        assert cache.get("global_key", "global") is None
        assert cache.get("org_key", "organization", org_id="org_123") is None
        
        # Verify stats are reset
        stats = cache.stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["evictions"] == 0
        assert stats["current_size"] == 0