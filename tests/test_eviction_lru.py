import pytest
import threading
from concurrent.futures import ThreadPoolExecutor
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eviction_policies.lre_eviction import LRUEvictionPolicy
from cache_types import _CacheKey


class TestLRUEvictionPolicy:
    """Test cases for LRU eviction policy."""

    def test_initialization(self):
        """Test LRU policy initialization."""
        policy = LRUEvictionPolicy()
        assert len(policy._lru_tracker) == 0
        assert len(policy._namespaced_lru_trackers) == 0

    def test_notify_set_basic(self):
        """Test basic notify_set operation."""
        policy = LRUEvictionPolicy()
        key: _CacheKey = ("global", "test_ns", ("arg1",))
        
        result = policy.notify_set(key, "test_ns", None, None)
        
        assert result is None  # No eviction needed
        assert key in policy._lru_tracker
        assert key in policy._namespaced_lru_trackers["test_ns"]

    def test_notify_set_with_global_limit(self):
        """Test notify_set with global limit enforcement."""
        policy = LRUEvictionPolicy()
        
        # Add items up to limit
        for i in range(3):
            key: _CacheKey = ("global", "test_ns", (f"arg{i}",))
            result = policy.notify_set(key, "test_ns", None, 2)
            
            if i < 2:
                assert result is None
            else:
                assert result is not None  # Should evict oldest

    def test_notify_set_with_namespace_limit(self):
        """Test notify_set with namespace limit enforcement."""
        policy = LRUEvictionPolicy()
        
        # Add items to same namespace
        for i in range(3):
            key: _CacheKey = ("global", "test_ns", (f"arg{i}",))
            result = policy.notify_set(key, "test_ns", 2, None)
            
            if i < 2:
                assert result is None
            else:
                assert result is not None  # Should evict oldest from namespace

    def test_notify_get_updates_order(self):
        """Test that notify_get updates LRU order."""
        policy = LRUEvictionPolicy()
        
        key1: _CacheKey = ("global", "test_ns", ("arg1",))
        key2: _CacheKey = ("global", "test_ns", ("arg2",))
        
        # Add two keys
        policy.notify_set(key1, "test_ns", None, None)
        policy.notify_set(key2, "test_ns", None, None)
        
        # Access first key (should move to end)
        policy.notify_get(key1, "test_ns")
        
        # Add third key with limit of 2
        key3: _CacheKey = ("global", "test_ns", ("arg3",))
        evicted = policy.notify_set(key3, "test_ns", None, 2)
        
        # Should evict key2 (oldest), not key1 (recently accessed)
        assert evicted == key2

    def test_notify_evict(self):
        """Test notify_evict removes key from trackers."""
        policy = LRUEvictionPolicy()
        key: _CacheKey = ("global", "test_ns", ("arg1",))
        
        # Add key
        policy.notify_set(key, "test_ns", None, None)
        assert key in policy._lru_tracker
        assert key in policy._namespaced_lru_trackers["test_ns"]
        
        # Evict key
        policy.notify_evict(key, "test_ns")
        assert key not in policy._lru_tracker
        assert key not in policy._namespaced_lru_trackers["test_ns"]

    def test_notify_clear(self):
        """Test notify_clear removes all keys."""
        policy = LRUEvictionPolicy()
        
        # Add multiple keys
        for i in range(5):
            key: _CacheKey = ("global", f"ns_{i}", (f"arg{i}",))
            policy.notify_set(key, f"ns_{i}", None, None)
        
        assert len(policy._lru_tracker) == 5
        assert len(policy._namespaced_lru_trackers) == 5
        
        # Clear all
        policy.notify_clear()
        assert len(policy._lru_tracker) == 0
        assert len(policy._namespaced_lru_trackers) == 0

    def test_get_namespace_count(self):
        """Test get_namespace_count returns correct count."""
        policy = LRUEvictionPolicy()
        
        # Add keys to different namespaces
        for i in range(3):
            key: _CacheKey = ("global", f"ns_{i}", (f"arg{i}",))
            policy.notify_set(key, f"ns_{i}", None, None)
        
        assert policy.get_namespace_count() == 3

    def test_get_global_size(self):
        """Test get_global_size returns correct size."""
        policy = LRUEvictionPolicy()
        
        # Add multiple keys
        for i in range(5):
            key: _CacheKey = ("global", "test_ns", (f"arg{i}",))
            policy.notify_set(key, "test_ns", None, None)
        
        assert policy.get_global_size() == 5

    def test_thread_safety(self):
        """Test thread safety of LRU operations."""
        policy = LRUEvictionPolicy()
        results = []
        
        def worker(thread_id):
            for i in range(10):
                key: _CacheKey = ("global", f"ns_{thread_id}", (f"arg{i}",))
                result = policy.notify_set(key, f"ns_{thread_id}", None, None)
                results.append(result)
                
                if i % 2 == 0:
                    policy.notify_get(key, f"ns_{thread_id}")
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker, i) for i in range(5)]
            for future in futures:
                future.result()
        
        # Should complete without errors
        assert policy.get_global_size() == 50
        assert policy.get_namespace_count() == 5

    def test_namespace_cleanup_on_empty(self):
        """Test that empty namespaces are cleaned up."""
        policy = LRUEvictionPolicy()
        key: _CacheKey = ("global", "test_ns", ("arg1",))
        
        # Add and then evict key
        policy.notify_set(key, "test_ns", None, None)
        assert "test_ns" in policy._namespaced_lru_trackers
        
        policy.notify_evict(key, "test_ns")
        assert "test_ns" not in policy._namespaced_lru_trackers

    def test_lru_order_preservation(self):
        """Test that LRU order is correctly preserved."""
        policy = LRUEvictionPolicy()
        keys = []
        
        # Add keys in order
        for i in range(5):
            key: _CacheKey = ("global", "test_ns", (f"arg{i}",))
            keys.append(key)
            policy.notify_set(key, "test_ns", None, None)
        
        # Access middle key
        policy.notify_get(keys[2], "test_ns")
        
        # Add new key with limit to force eviction
        new_key: _CacheKey = ("global", "test_ns", ("new_arg",))
        evicted = policy.notify_set(new_key, "test_ns", None, 5)
        
        # Should evict keys[0] (oldest unaccessed)
        assert evicted == keys[0]

    def test_multiple_namespaces_isolation(self):
        """Test that different namespaces are properly isolated."""
        policy = LRUEvictionPolicy()
        
        # Add keys to different namespaces
        key1: _CacheKey = ("global", "ns1", ("arg1",))
        key2: _CacheKey = ("global", "ns2", ("arg1",))
        
        policy.notify_set(key1, "ns1", None, None)
        policy.notify_set(key2, "ns2", None, None)
        
        # Evict from ns1 should not affect ns2
        policy.notify_evict(key1, "ns1")
        
        assert key1 not in policy._lru_tracker
        assert key2 in policy._lru_tracker
        assert "ns1" not in policy._namespaced_lru_trackers
        assert "ns2" in policy._namespaced_lru_trackers

    def test_namespace_limit_vs_global_limit(self):
        """Test interaction between namespace and global limits."""
        policy = LRUEvictionPolicy()
        
        # Add keys to different namespaces
        key1: _CacheKey = ("global", "ns1", ("arg1",))
        key2: _CacheKey = ("global", "ns1", ("arg2",))
        key3: _CacheKey = ("global", "ns2", ("arg1",))
        
        policy.notify_set(key1, "ns1", None, None)
        policy.notify_set(key2, "ns1", None, None)
        policy.notify_set(key3, "ns2", None, None)
        
        # Add key with namespace limit (should evict from ns1)
        key4: _CacheKey = ("global", "ns1", ("arg3",))
        evicted = policy.notify_set(key4, "ns1", 2, None)
        
        assert evicted == key1  # Oldest in ns1

    def test_error_handling_in_notify_get(self):
        """Test error handling in notify_get for non-existent keys."""
        policy = LRUEvictionPolicy()
        key: _CacheKey = ("global", "test_ns", ("arg1",))
        
        # Should not raise exception for non-existent key
        policy.notify_get(key, "test_ns")

    def test_error_handling_in_notify_evict(self):
        """Test error handling in notify_evict for non-existent keys."""
        policy = LRUEvictionPolicy()
        key: _CacheKey = ("global", "test_ns", ("arg1",))
        
        # Should not raise exception for non-existent key
        policy.notify_evict(key, "test_ns")

    def test_concurrent_evictions(self):
        """Test concurrent evictions don't cause issues."""
        policy = LRUEvictionPolicy()
        
        # Add many keys
        keys = []
        for i in range(100):
            key: _CacheKey = ("global", "test_ns", (f"arg{i}",))
            keys.append(key)
            policy.notify_set(key, "test_ns", None, None)
        
        def evictor(start_idx):
            for i in range(start_idx, start_idx + 10):
                if i < len(keys):
                    policy.notify_evict(keys[i], "test_ns")
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(evictor, i * 10) for i in range(5)]
            for future in futures:
                future.result()
        
        # Should complete without errors
        assert policy.get_global_size() == 50