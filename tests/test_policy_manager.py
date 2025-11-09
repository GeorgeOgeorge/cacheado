import pytest
import time
import threading
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cache_policies.cache_policy_manager import CachePolicyManager
from eviction_policies.lre_eviction import LRUEvictionPolicy
from cache_types import _CacheKey


class TestCachePolicyManager:
    """Test cases for CachePolicyManager."""

    def test_initialization(self):
        """Test policy manager initialization."""
        cache_mock = Mock()
        policy = LRUEvictionPolicy()
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=5,
            policy=policy,
            max_size=100
        )
        
        assert manager._cache is cache_mock
        assert manager._cleanup_interval == 5
        assert manager._policy is policy
        assert manager._global_max_size == 100

    def test_start_background_cleanup(self):
        """Test starting background cleanup thread."""
        cache_mock = Mock()
        policy = LRUEvictionPolicy()
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=1,
            policy=policy,
            max_size=100
        )
        
        manager.start_background_cleanup()
        
        assert manager._cleanup_thread is not None
        assert manager._cleanup_thread.is_alive()
        
        # Cleanup
        manager.stop_background_cleanup()

    def test_stop_background_cleanup(self):
        """Test stopping background cleanup thread."""
        cache_mock = Mock()
        policy = LRUEvictionPolicy()
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=1,
            policy=policy,
            max_size=100
        )
        
        manager.start_background_cleanup()
        assert manager._cleanup_thread.is_alive()
        
        manager.stop_background_cleanup()
        assert not manager._cleanup_thread.is_alive()

    def test_notify_set_delegation(self):
        """Test that notify_set delegates to policy."""
        cache_mock = Mock()
        policy_mock = Mock()
        policy_mock.notify_set.return_value = None
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=5,
            policy=policy_mock,
            max_size=100
        )
        
        key: _CacheKey = ("global", "test_ns", ("arg1",))
        result = manager.notify_set(key, "test_ns", 10)
        
        policy_mock.notify_set.assert_called_once_with(key, "test_ns", 10, 100)
        assert result is None

    def test_notify_get_delegation(self):
        """Test that notify_get delegates to policy."""
        cache_mock = Mock()
        policy_mock = Mock()
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=5,
            policy=policy_mock,
            max_size=100
        )
        
        key: _CacheKey = ("global", "test_ns", ("arg1",))
        manager.notify_get(key, "test_ns")
        
        policy_mock.notify_get.assert_called_once_with(key, "test_ns")

    def test_notify_evict_delegation(self):
        """Test that notify_evict delegates to policy."""
        cache_mock = Mock()
        policy_mock = Mock()
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=5,
            policy=policy_mock,
            max_size=100
        )
        
        key: _CacheKey = ("global", "test_ns", ("arg1",))
        manager.notify_evict(key, "test_ns")
        
        policy_mock.notify_evict.assert_called_once_with(key, "test_ns")

    def test_notify_clear_delegation(self):
        """Test that notify_clear delegates to policy."""
        cache_mock = Mock()
        policy_mock = Mock()
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=5,
            policy=policy_mock,
            max_size=100
        )
        
        manager.notify_clear()
        
        policy_mock.notify_clear.assert_called_once()

    def test_get_namespace_count_delegation(self):
        """Test that get_namespace_count delegates to policy."""
        cache_mock = Mock()
        policy_mock = Mock()
        policy_mock.get_namespace_count.return_value = 5
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=5,
            policy=policy_mock,
            max_size=100
        )
        
        result = manager.get_namespace_count()
        
        policy_mock.get_namespace_count.assert_called_once()
        assert result == 5

    def test_get_global_size_delegation(self):
        """Test that get_global_size delegates to policy."""
        cache_mock = Mock()
        policy_mock = Mock()
        policy_mock.get_global_size.return_value = 42
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=5,
            policy=policy_mock,
            max_size=100
        )
        
        result = manager.get_global_size()
        
        policy_mock.get_global_size.assert_called_once()
        assert result == 42

    def test_properties(self):
        """Test property accessors."""
        cache_mock = Mock()
        policy = LRUEvictionPolicy()
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=5,
            policy=policy,
            max_size=100
        )
        
        assert manager.policy is policy
        assert manager.global_max_size == 100
        assert manager.cleanup_interval == 5

    def test_cleanup_loop_with_expired_items(self):
        """Test cleanup loop handles expired items."""
        cache_mock = Mock()
        
        # Mock expired item
        expired_key: _CacheKey = ("global", "test_ns", ("arg1",))
        expired_value = ("value", time.monotonic() - 10)  # Expired
        
        cache_mock._get_all_keys_from_storage.return_value = [expired_key]
        cache_mock._get_value_no_lock_from_storage.return_value = expired_value
        
        policy = LRUEvictionPolicy()
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=0.1,
            policy=policy,
            max_size=100
        )
        
        # Start cleanup and let it run briefly
        manager.start_background_cleanup()
        time.sleep(0.2)
        manager.stop_background_cleanup()
        
        # Should have called _internal_get to trigger expiration
        cache_mock._internal_get.assert_called()

    def test_cleanup_loop_with_no_keys(self):
        """Test cleanup loop handles empty cache."""
        cache_mock = Mock()
        cache_mock._get_all_keys_from_storage.return_value = []
        
        policy = LRUEvictionPolicy()
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=0.1,
            policy=policy,
            max_size=100
        )
        
        # Start cleanup and let it run briefly
        manager.start_background_cleanup()
        time.sleep(0.2)
        manager.stop_background_cleanup()
        
        # Should not crash
        cache_mock._get_all_keys_from_storage.assert_called()

    def test_error_handling_in_notify_methods(self):
        """Test error handling in notify methods."""
        cache_mock = Mock()
        policy_mock = Mock()
        policy_mock.notify_set.side_effect = Exception("Test error")
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=5,
            policy=policy_mock,
            max_size=100
        )
        
        key: _CacheKey = ("global", "test_ns", ("arg1",))
        
        # Should not raise exception, should return None
        result = manager.notify_set(key, "test_ns", 10)
        assert result is None

    def test_cleanup_loop_error_handling(self):
        """Test error handling in cleanup loop."""
        cache_mock = Mock()
        cache_mock._get_all_keys_from_storage.side_effect = Exception("Test error")
        
        policy = LRUEvictionPolicy()
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=0.1,
            policy=policy,
            max_size=100
        )
        
        # Start cleanup and let it run briefly
        manager.start_background_cleanup()
        time.sleep(0.2)
        manager.stop_background_cleanup()
        
        # Should not crash despite errors

    def test_multiple_start_stop_cycles(self):
        """Test multiple start/stop cycles."""
        cache_mock = Mock()
        policy = LRUEvictionPolicy()
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=1,
            policy=policy,
            max_size=100
        )
        
        # Multiple start/stop cycles
        for _ in range(3):
            manager.start_background_cleanup()
            assert manager._cleanup_thread.is_alive()
            
            manager.stop_background_cleanup()
            assert not manager._cleanup_thread.is_alive()

    def test_start_when_already_running(self):
        """Test starting cleanup when already running."""
        cache_mock = Mock()
        policy = LRUEvictionPolicy()
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=1,
            policy=policy,
            max_size=100
        )
        
        manager.start_background_cleanup()
        first_thread = manager._cleanup_thread
        
        # Start again - should not create new thread
        manager.start_background_cleanup()
        second_thread = manager._cleanup_thread
        
        assert first_thread is second_thread
        
        manager.stop_background_cleanup()

    def test_stop_when_not_running(self):
        """Test stopping cleanup when not running."""
        cache_mock = Mock()
        policy = LRUEvictionPolicy()
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=1,
            policy=policy,
            max_size=100
        )
        
        # Should not raise exception
        manager.stop_background_cleanup()

    def test_daemon_thread_property(self):
        """Test that cleanup thread is daemon."""
        cache_mock = Mock()
        policy = LRUEvictionPolicy()
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=1,
            policy=policy,
            max_size=100
        )
        
        manager.start_background_cleanup()
        
        assert manager._cleanup_thread.daemon is True
        
        manager.stop_background_cleanup()

    def test_cleanup_with_valid_items(self):
        """Test cleanup loop with valid (non-expired) items."""
        cache_mock = Mock()
        
        # Mock valid item
        valid_key: _CacheKey = ("global", "test_ns", ("arg1",))
        valid_value = ("value", time.monotonic() + 60)  # Not expired
        
        cache_mock._get_all_keys_from_storage.return_value = [valid_key]
        cache_mock._get_value_no_lock_from_storage.return_value = valid_value
        
        policy = LRUEvictionPolicy()
        
        manager = CachePolicyManager(
            cache_instance=cache_mock,
            cleanup_interval=0.1,
            policy=policy,
            max_size=100
        )
        
        # Start cleanup and let it run briefly
        manager.start_background_cleanup()
        time.sleep(0.2)
        manager.stop_background_cleanup()
        
        # Should still call _internal_get but item won't be expired
        cache_mock._internal_get.assert_called()