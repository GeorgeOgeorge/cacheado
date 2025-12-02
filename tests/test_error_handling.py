import threading
import time
from unittest.mock import Mock, patch

import pytest
from cache_policies.cache_policy_manager import CachePolicyManager

from cache import Cache, create_cache
from cache_scope_config import ScopeConfig, ScopeLevel
from eviction_policies.lre_eviction import LRUEvictionPolicy
from storages.in_memory import InMemory


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_cache_without_configuration_error_paths(self):
        """Test cache operations without configuration - error paths."""
        cache = Cache()

        # Test _get_all_keys_from_storage without storage
        keys = cache._get_all_keys_from_storage()
        assert keys == []

    def test_cache_policy_manager_error_handling(self):
        """Test CachePolicyManager error handling."""
        cache_mock = Mock()
        policy_mock = Mock()

        # Test start_background_cleanup error
        manager = CachePolicyManager(1, policy_mock, 100)
        manager.set_cache_instance(cache_mock)

        with patch("threading.Thread") as mock_thread:
            mock_thread.side_effect = Exception("Thread creation failed")
            with pytest.raises(Exception):
                manager.start_background_cleanup()

    def test_cache_policy_manager_stop_error(self):
        """Test CachePolicyManager stop error handling."""
        cache_mock = Mock()
        policy_mock = Mock()
        manager = CachePolicyManager(1, policy_mock, 100)
        manager.set_cache_instance(cache_mock)

        # Mock thread that raises exception on join
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        mock_thread.join.side_effect = Exception("Join failed")
        manager._cleanup_thread = mock_thread

        # Should not raise exception
        manager.stop_background_cleanup()

    def test_lru_eviction_error_handling(self):
        """Test LRU eviction policy error handling."""
        policy = LRUEvictionPolicy()

        # Test notify_set with exception in popitem
        key1 = ("global", "test", ("arg1",))
        key2 = ("global", "test", ("arg2",))
        key3 = ("global", "test", ("arg3",))

        policy.notify_set(key1, "test", None, None)
        policy.notify_set(key2, "test", None, None)

        # Mock OrderedDict to raise exception
        with patch.object(policy._namespaced_lru_trackers["test"], "popitem") as mock_pop:
            mock_pop.side_effect = Exception("Pop failed")
            result = policy.notify_set(key3, "test", 2, None)
            assert result is None

    def test_in_memory_storage_error_handling(self):
        """Test InMemory storage error handling."""
        storage = InMemory()
        key = ("global", "test", ("arg",))

        # Test get with corrupted cache
        storage._cache = None
        result = storage.get(key)
        assert result is None

        # Reset storage
        storage = InMemory()

        # Test set with corrupted cache
        storage._cache = None
        with pytest.raises(Exception):
            storage.set(key, ("value", time.monotonic() + 60))

        # Reset storage
        storage = InMemory()

        # Test evict with exception
        with patch.object(storage, "_cache") as mock_cache:
            mock_cache.__contains__.side_effect = Exception("Contains failed")
            # Should not raise exception
            storage.evict(key)

        # Test get_all_keys with exception
        storage = InMemory()
        with patch.object(storage, "_cache") as mock_cache:
            mock_cache.keys.side_effect = Exception("Keys failed")
            result = storage.get_all_keys()
            assert result == []

        # Test clear with exception
        storage = InMemory()
        with patch.object(storage, "_cache") as mock_cache:
            mock_cache.clear.side_effect = Exception("Clear failed")
            # Should not raise exception
            storage.clear()

    def test_cache_configuration_double_configure(self, storage, policy_manager, scope_config):
        """Test double configuration warning."""
        cache = Cache()

        # First configuration
        cache.configure(storage, policy_manager, scope_config)

        # Second configuration should log warning
        import logging

        with patch.object(logging, "warning") as mock_warning:
            cache.configure(storage, policy_manager, scope_config)
            mock_warning.assert_called()

    def test_cache_clear_error_handling(self, cache):
        """Test cache clear error handling."""
        # Mock storage to raise exception
        with patch.object(cache._storage, "clear") as mock_clear:
            mock_clear.side_effect = Exception("Clear failed")
            with pytest.raises(Exception):
                cache.clear()

    def test_scope_config_edge_case(self):
        """Test ScopeConfig edge case."""
        # Test with empty param name
        level = ScopeLevel("test", "")
        config = ScopeConfig([level])

        # Should handle empty param gracefully
        path = config.build_scope_path({})
        assert path == "global"

    def test_cache_evict_by_scope_error(self, cache):
        """Test evict_by_scope error handling."""
        # Test with invalid scope params
        result = cache.evict_by_scope("organization")  # Missing org_id
        assert result == 0

    def test_cache_stampede_protection_edge_cases(self, cache):
        """Test stampede protection edge cases."""
        call_count = 0

        @cache.cache(ttl_seconds=60, scope="global")
        def test_func_with_exception():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First call fails")
            return "success"

        # First call should be caught by wrapper and return function result
        # The cache wrapper catches exceptions and calls the function directly
        result1 = test_func_with_exception()
        assert result1 == "success"  # Exception was caught, function called again

        # Second call should use cached result
        result2 = test_func_with_exception()
        assert result2 == "success"
        # Function may be called multiple times due to exception handling and retry logic
        assert call_count >= 2

    def test_cache_async_error_handling(self, cache):
        """Test async cache error handling."""
        call_count = 0

        @cache.cache(ttl_seconds=60, scope="global")
        async def async_func_with_error():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Async error")
            return "async_success"

        # Test async error handling
        import asyncio

        async def test_async():
            # First call should be caught by wrapper and return function result
            result1 = await async_func_with_error()
            assert result1 == "async_success"  # Exception was caught, function called again

            # Second call should use cached result
            result2 = await async_func_with_error()
            assert result2 == "async_success"
            # Function may be called multiple times due to exception handling and retry logic
            assert call_count >= 2

        asyncio.run(test_async())

    def test_cache_internal_evict_without_policy(self):
        """Test _internal_evict without policy manager."""
        cache = Cache()
        # Should not raise exception
        cache._internal_evict(("test", "key", ("arg",)), "namespace")

    def test_cache_internal_set_zero_ttl(self, cache):
        """Test _internal_set with zero TTL."""
        key = ("global", "test", ("arg",))

        # Should not set anything with zero TTL
        cache._internal_set(key, "value", 0, "test", None)

        # Verify nothing was set
        result = cache._internal_get(key, "test")
        assert result is None

    def test_cache_make_args_key_error(self, cache):
        """Test _make_args_key with unpickleable objects."""
        # Create unpickleable object
        lock = threading.Lock()

        with pytest.raises(TypeError):
            cache._make_args_key(lock)

    def test_cache_get_scope_prefix_invalid_scope(self, cache):
        """Test _get_scope_prefix with invalid scope type."""
        with pytest.raises(ValueError):
            cache._get_scope_prefix(123)  # Invalid scope type

    def test_cache_programmatic_operations_error_handling(self, cache):
        """Test programmatic operations error handling."""
        # Test get with invalid scope (causes ValueError)
        result = cache.get("test_key", scope="organization")  # Missing org_id
        assert result is None

        # Test set with invalid scope (causes ValueError)
        with pytest.raises(ValueError):
            cache.set("test_key", "value", 60, scope="organization")  # Missing org_id

        # Test evict with invalid scope (should not raise exception)
        cache.evict("test_key", scope="organization")  # Missing org_id - logs error but doesn't raise

    def test_create_cache_with_policy_manager_cache_attribute(self):
        """Test create_cache with policy manager that has _cache attribute."""
        storage = InMemory()
        policy = LRUEvictionPolicy()
        policy_manager = CachePolicyManager(1, policy, 100)
        scope_config = ScopeConfig()

        # Ensure _cache is None initially
        assert policy_manager._cache is None

        cache = create_cache(storage, policy_manager, scope_config)

        # Verify _cache was set
        assert policy_manager._cache is cache

    def test_cache_without_scope_config_runtime_error(self):
        """Test cache operations without scope config."""
        cache = Cache()
        cache._storage = Mock()
        cache._policy_manager = Mock()
        # Don't set _scope_config

        with pytest.raises(RuntimeError, match="Cache not configured"):
            cache._get_scope_prefix("organization", {"org_id": "123"})
