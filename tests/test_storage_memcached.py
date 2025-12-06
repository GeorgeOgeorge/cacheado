from unittest.mock import Mock, patch

import pytest

from cache_types import _CacheKey, _CacheValue
from storages.memcached_storage import MemcachedStorage


class TestMemcachedStorage:
    """Test suite for MemcachedStorage provider."""

    def test_init_with_valid_server(self):
        """Test initialization with valid server address."""
        with patch("pymemcache.client.base.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            MemcachedStorage("localhost:11211")

            mock_client_class.assert_called_once_with("localhost:11211")
            mock_client.version.assert_called_once()

    def test_init_with_empty_server(self):
        """Test initialization fails with empty server address."""
        with pytest.raises(ValueError, match="Server address is required"):
            MemcachedStorage("")

    def test_init_with_connection_failure(self):
        """Test initialization fails when Memcached connection fails."""
        with patch("pymemcache.client.base.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.version.side_effect = Exception("Connection failed")
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception):
                MemcachedStorage("localhost:11211")

    def test_set_and_get(self):
        """Test setting and getting values."""
        with patch("pymemcache.client.base.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            storage = MemcachedStorage("localhost:11211")

            key: _CacheKey = ("scope", "namespace", ("arg1", "arg2"))
            value = "cached_data"

            # Test set
            storage.set(key, value, 60)
            mock_client.set.assert_called_once()

            # Test get
            import pickle
            import time

            value_tuple: _CacheValue = (value, time.monotonic() + 60)
            serialized_value = pickle.dumps(value_tuple)
            mock_client.get.return_value = serialized_value

            result = storage.get(key)
            assert result is not None
            assert result[0] == value

    def test_get_nonexistent_key(self):
        """Test getting a non-existent key returns None."""
        with patch("pymemcache.client.base.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.get.return_value = None
            mock_client_class.return_value = mock_client

            storage = MemcachedStorage("localhost:11211")
            key: _CacheKey = ("scope", "namespace", ("arg1",))

            result = storage.get(key)
            assert result is None

    def test_get_with_deserialization_error(self):
        """Test get returns None when deserialization fails."""
        with patch("pymemcache.client.base.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.get.return_value = b"invalid_pickle_data"
            mock_client_class.return_value = mock_client

            storage = MemcachedStorage("localhost:11211")
            key: _CacheKey = ("scope", "namespace", ("arg1",))

            result = storage.get(key)
            assert result is None

    def test_evict(self):
        """Test evicting a key."""
        with patch("pymemcache.client.base.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            storage = MemcachedStorage("localhost:11211")
            key: _CacheKey = ("scope", "namespace", ("arg1",))

            storage.evict(key)
            mock_client.delete.assert_called_once()

    def test_get_all_keys(self):
        """Test getting all keys returns empty list (Memcached limitation)."""
        with patch("pymemcache.client.base.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            storage = MemcachedStorage("localhost:11211")

            result = storage.get_all_keys()
            assert result == []

    def test_clear(self):
        """Test clearing all data."""
        with patch("pymemcache.client.base.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            storage = MemcachedStorage("localhost:11211")

            storage.clear()
            mock_client.flush_all.assert_called_once()

    def test_deserialize_invalid_key_format(self):
        """Test deserialization fails with invalid key format."""
        with patch("pymemcache.client.base.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            storage = MemcachedStorage("localhost:11211")

            # Test invalid key format (not a 3-tuple)
            import pickle

            invalid_key = ("scope", "namespace")  # Missing third element
            serialized_key = pickle.dumps(invalid_key).hex()

            with pytest.raises(ValueError, match="Invalid cache key format"):
                storage._deserialize_key(serialized_key)

    def test_deserialize_invalid_value_format(self):
        """Test get fails with invalid value format and returns None."""
        with patch("pymemcache.client.base.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            storage = MemcachedStorage("localhost:11211")
            key: _CacheKey = ("scope", "namespace", ("arg1",))

            # Test invalid value format (not a 2-tuple)
            import pickle

            invalid_value = ("data",)  # Missing expiry timestamp
            serialized_value = pickle.dumps(invalid_value)
            mock_client.get.return_value = serialized_value

            result = storage.get(key)
            assert result is None
