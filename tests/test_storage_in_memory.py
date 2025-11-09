import pytest
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storages.in_memory import InMemory
from cache_types import _CacheKey, _CacheValue


class TestInMemoryStorage:
    """Test cases for InMemory storage provider."""

    def test_initialization(self):
        """Test storage initialization."""
        storage = InMemory()
        assert len(storage._cache) == 0
        assert len(storage._key_locks) == 0

    def test_basic_get_set(self):
        """Test basic get/set operations."""
        storage = InMemory()
        key: _CacheKey = ("global", "test", ("arg1",))
        value: _CacheValue = ("test_value", time.monotonic() + 60)
        
        storage.set(key, value)
        result = storage.get(key)
        
        assert result == value

    def test_get_nonexistent_key(self):
        """Test getting non-existent key."""
        storage = InMemory()
        key: _CacheKey = ("global", "nonexistent", ("arg1",))
        
        result = storage.get(key)
        assert result is None

    def test_evict_key(self):
        """Test key eviction."""
        storage = InMemory()
        key: _CacheKey = ("global", "test", ("arg1",))
        value: _CacheValue = ("test_value", time.monotonic() + 60)
        
        storage.set(key, value)
        assert storage.get(key) == value
        
        storage.evict(key)
        assert storage.get(key) is None

    def test_get_all_keys(self):
        """Test getting all keys."""
        storage = InMemory()
        key1: _CacheKey = ("global", "test1", ("arg1",))
        key2: _CacheKey = ("global", "test2", ("arg2",))
        value: _CacheValue = ("test_value", time.monotonic() + 60)
        
        storage.set(key1, value)
        storage.set(key2, value)
        
        all_keys = storage.get_all_keys()
        assert len(all_keys) == 2
        assert key1 in all_keys
        assert key2 in all_keys

    def test_clear_storage(self):
        """Test clearing storage."""
        storage = InMemory()
        key: _CacheKey = ("global", "test", ("arg1",))
        value: _CacheValue = ("test_value", time.monotonic() + 60)
        
        storage.set(key, value)
        assert len(storage.get_all_keys()) == 1
        
        storage.clear()
        assert len(storage.get_all_keys()) == 0

    def test_get_value_no_lock(self):
        """Test non-locking get operation."""
        storage = InMemory()
        key: _CacheKey = ("global", "test", ("arg1",))
        value: _CacheValue = ("test_value", time.monotonic() + 60)
        
        storage.set(key, value)
        result = storage.get_value_no_lock(key)
        
        assert result == value

    def test_thread_safety(self):
        """Test thread safety of storage operations."""
        storage = InMemory()
        results = []
        
        def worker(thread_id):
            key: _CacheKey = ("global", f"test_{thread_id}", (f"arg_{thread_id}",))
            value: _CacheValue = (f"value_{thread_id}", time.monotonic() + 60)
            
            storage.set(key, value)
            result = storage.get(key)
            results.append(result)
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, i) for i in range(10)]
            for future in futures:
                future.result()
        
        assert len(results) == 10
        for i, result in enumerate(results):
            assert result[0] == f"value_{i}"

    def test_concurrent_access_same_key(self):
        """Test concurrent access to the same key."""
        storage = InMemory()
        key: _CacheKey = ("global", "shared", ("arg1",))
        
        def setter():
            for i in range(100):
                value: _CacheValue = (f"value_{i}", time.monotonic() + 60)
                storage.set(key, value)
        
        def getter():
            for _ in range(100):
                storage.get(key)
        
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=setter))
            threads.append(threading.Thread(target=getter))
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should not crash and final value should exist
        final_value = storage.get(key)
        assert final_value is not None

    def test_evict_nonexistent_key(self):
        """Test evicting non-existent key."""
        storage = InMemory()
        key: _CacheKey = ("global", "nonexistent", ("arg1",))
        
        # Should not raise exception
        storage.evict(key)

    def test_lock_cleanup_on_evict(self):
        """Test that locks are cleaned up on eviction."""
        storage = InMemory()
        key: _CacheKey = ("global", "test", ("arg1",))
        value: _CacheValue = ("test_value", time.monotonic() + 60)
        
        storage.set(key, value)
        assert key in storage._key_locks
        
        storage.evict(key)
        assert key not in storage._key_locks

    def test_error_handling_in_get(self):
        """Test error handling in get operation."""
        storage = InMemory()
        
        # Mock an error condition
        with pytest.raises(Exception):
            # This should trigger error handling
            storage._cache = None
            storage.get(("test", "key", ("arg",)))

    def test_error_handling_in_set(self):
        """Test error handling in set operation."""
        storage = InMemory()
        key: _CacheKey = ("global", "test", ("arg1",))
        
        # Mock an error condition by making _cache None
        storage._cache = None
        
        with pytest.raises(Exception):
            storage.set(key, ("value", time.monotonic() + 60))

    def test_multiple_keys_operations(self):
        """Test operations with multiple keys."""
        storage = InMemory()
        keys_values = []
        
        # Set multiple keys
        for i in range(100):
            key: _CacheKey = ("global", f"test_{i}", (f"arg_{i}",))
            value: _CacheValue = (f"value_{i}", time.monotonic() + 60)
            keys_values.append((key, value))
            storage.set(key, value)
        
        # Verify all keys exist
        all_keys = storage.get_all_keys()
        assert len(all_keys) == 100
        
        # Verify all values are correct
        for key, expected_value in keys_values:
            actual_value = storage.get(key)
            assert actual_value == expected_value
        
        # Evict half the keys
        for i in range(0, 100, 2):
            key = keys_values[i][0]
            storage.evict(key)
        
        # Verify remaining keys
        remaining_keys = storage.get_all_keys()
        assert len(remaining_keys) == 50

    def test_storage_isolation(self):
        """Test that different storage instances are isolated."""
        storage1 = InMemory()
        storage2 = InMemory()
        
        key: _CacheKey = ("global", "test", ("arg1",))
        value1: _CacheValue = ("value1", time.monotonic() + 60)
        value2: _CacheValue = ("value2", time.monotonic() + 60)
        
        storage1.set(key, value1)
        storage2.set(key, value2)
        
        assert storage1.get(key) == value1
        assert storage2.get(key) == value2