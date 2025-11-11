from unittest.mock import Mock, patch

import pytest

from cache_types import _CacheKey, _CacheValue
from storages.redis_storage import RedisStorage


class TestRedisStorage:
    """Test suite for RedisStorage provider."""

    def test_init_with_valid_connection_string(self):
        """Test initialization with valid connection string."""
        with patch("redis.from_url") as mock_redis:
            mock_client = Mock()
            mock_redis.return_value = mock_client

            RedisStorage("redis://localhost:6379/0")

            mock_redis.assert_called_once_with("redis://localhost:6379/0")
            mock_client.ping.assert_called_once()

    def test_init_with_empty_connection_string(self):
        """Test initialization fails with empty connection string."""
        with pytest.raises(ValueError, match="Connection string is required"):
            RedisStorage("")

    def test_init_with_connection_failure(self):
        """Test initialization fails when Redis connection fails."""
        with patch("redis.from_url") as mock_redis:
            mock_client = Mock()
            mock_client.ping.side_effect = Exception("Connection failed")
            mock_redis.return_value = mock_client

            with pytest.raises(Exception):
                RedisStorage("redis://localhost:6379/0")

    def test_set_and_get(self):
        """Test setting and getting values."""
        with patch("redis.from_url") as mock_redis:
            mock_client = Mock()
            mock_redis.return_value = mock_client

            storage = RedisStorage("redis://localhost:6379/0")

            key: _CacheKey = ("scope", "namespace", ("arg1", "arg2"))
            value: _CacheValue = ("cached_data", 1234567890.0)

            # Test set
            storage.set(key, value)
            mock_client.set.assert_called_once()

            # Test get
            import pickle

            serialized_value = pickle.dumps(value)
            mock_client.get.return_value = serialized_value

            result = storage.get(key)
            assert result == value

    def test_get_nonexistent_key(self):
        """Test getting a non-existent key returns None."""
        with patch("redis.from_url") as mock_redis:
            mock_client = Mock()
            mock_client.get.return_value = None
            mock_redis.return_value = mock_client

            storage = RedisStorage("redis://localhost:6379/0")
            key: _CacheKey = ("scope", "namespace", ("arg1",))

            result = storage.get(key)
            assert result is None

    def test_get_with_deserialization_error(self):
        """Test get returns None when deserialization fails."""
        with patch("redis.from_url") as mock_redis:
            mock_client = Mock()
            mock_client.get.return_value = b"invalid_pickle_data"
            mock_redis.return_value = mock_client

            storage = RedisStorage("redis://localhost:6379/0")
            key: _CacheKey = ("scope", "namespace", ("arg1",))

            result = storage.get(key)
            assert result is None

    def test_evict(self):
        """Test evicting a key."""
        with patch("redis.from_url") as mock_redis:
            mock_client = Mock()
            mock_redis.return_value = mock_client

            storage = RedisStorage("redis://localhost:6379/0")
            key: _CacheKey = ("scope", "namespace", ("arg1",))

            storage.evict(key)
            mock_client.delete.assert_called_once()

    def test_get_all_keys(self):
        """Test getting all keys."""
        with patch("redis.from_url") as mock_redis:
            mock_client = Mock()
            mock_redis.return_value = mock_client

            storage = RedisStorage("redis://localhost:6379/0")

            # Mock Redis keys response
            import pickle

            key1: _CacheKey = ("scope1", "ns1", ("arg1",))
            key2: _CacheKey = ("scope2", "ns2", ("arg2",))

            serialized_keys = [pickle.dumps(key1).hex().encode(), pickle.dumps(key2).hex().encode()]
            mock_client.keys.return_value = serialized_keys

            result = storage.get_all_keys()
            assert len(result) == 2
            assert key1 in result
            assert key2 in result

    def test_clear(self):
        """Test clearing all data."""
        with patch("redis.from_url") as mock_redis:
            mock_client = Mock()
            mock_redis.return_value = mock_client

            storage = RedisStorage("redis://localhost:6379/0")

            storage.clear()
            mock_client.flushdb.assert_called_once()

    def test_get_value_no_lock(self):
        """Test get_value_no_lock delegates to get."""
        with patch("redis.from_url") as mock_redis:
            mock_client = Mock()
            mock_redis.return_value = mock_client

            storage = RedisStorage("redis://localhost:6379/0")
            key: _CacheKey = ("scope", "namespace", ("arg1",))

            import pickle

            value: _CacheValue = ("data", 123.0)
            serialized_value = pickle.dumps(value)
            mock_client.get.return_value = serialized_value

            result = storage.get_value_no_lock(key)
            assert result == value

    def test_deserialize_invalid_key_format(self):
        """Test deserialization fails with invalid key format."""
        with patch("redis.from_url") as mock_redis:
            mock_client = Mock()
            mock_redis.return_value = mock_client

            storage = RedisStorage("redis://localhost:6379/0")

            # Test invalid key format (not a 3-tuple)
            import pickle

            invalid_key = ("scope", "namespace")  # Missing third element
            serialized_key = pickle.dumps(invalid_key).hex()

            with pytest.raises(ValueError, match="Invalid cache key format"):
                storage._deserialize_key(serialized_key)

    def test_deserialize_invalid_value_format(self):
        """Test deserialization fails with invalid value format."""
        with patch("redis.from_url") as mock_redis:
            mock_client = Mock()
            mock_redis.return_value = mock_client

            storage = RedisStorage("redis://localhost:6379/0")

            # Test invalid value format (not a 2-tuple)
            import pickle

            invalid_value = ("data",)  # Missing expiry timestamp
            serialized_value = pickle.dumps(invalid_value)

            with pytest.raises(ValueError, match="Invalid cache value format"):
                storage._deserialize_value(serialized_value)
