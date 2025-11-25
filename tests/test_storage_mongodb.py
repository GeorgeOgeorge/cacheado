from unittest.mock import Mock, patch

import pytest

from cache_types import _CacheKey, _CacheValue
from storages.mongodb_storage import MongoDBStorage


class TestMongoDBStorage:
    """Test suite for MongoDBStorage provider."""

    @patch("storages.mongodb_storage.MongoClient")
    def test_init_with_valid_connection_string(self, mock_client_class):
        """Test initialization with valid connection string."""
        mock_client = Mock()
        mock_db = Mock()
        mock_collection = Mock()
        mock_client.admin.command.return_value = None
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_db.__getitem__ = Mock(return_value=mock_collection)
        mock_client_class.return_value = mock_client

        MongoDBStorage("mongodb://localhost:27017")

        mock_client_class.assert_called_once_with("mongodb://localhost:27017")
        mock_client.admin.command.assert_called_once_with("ping")

    @patch("storages.mongodb_storage.MongoClient")
    def test_init_with_custom_database_and_collection(self, mock_client_class):
        """Test initialization with custom database and collection names."""
        mock_client = Mock()
        mock_db = Mock()
        mock_collection = Mock()
        mock_client.admin.command.return_value = None
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_db.__getitem__ = Mock(return_value=mock_collection)
        mock_client_class.return_value = mock_client

        MongoDBStorage("mongodb://localhost:27017", "custom_db", "custom_collection")

        mock_client.__getitem__.assert_called_with("custom_db")
        mock_db.__getitem__.assert_called_with("custom_collection")

    def test_init_with_empty_connection_string(self):
        """Test initialization fails with empty connection string."""
        with pytest.raises(ValueError, match="Connection string is required"):
            MongoDBStorage("")

    @patch("storages.mongodb_storage.MongoClient")
    def test_init_with_connection_failure(self, mock_client_class):
        """Test initialization fails when MongoDB connection fails."""
        mock_client = Mock()
        mock_client.admin.command.side_effect = Exception("Connection failed")
        mock_client_class.return_value = mock_client

        with pytest.raises(Exception):
            MongoDBStorage("mongodb://localhost:27017")

    @patch("storages.mongodb_storage.MongoClient")
    def test_serialize_deserialize_key(self, mock_client_class):
        """Test key serialization and deserialization."""
        mock_client = Mock()
        mock_db = Mock()
        mock_collection = Mock()
        mock_client.admin.command.return_value = None
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_db.__getitem__ = Mock(return_value=mock_collection)
        mock_client_class.return_value = mock_client

        storage = MongoDBStorage("mongodb://localhost:27017")
        key: _CacheKey = ("scope", "namespace", ("arg1", "arg2"))

        serialized = storage._serialize_key(key)
        deserialized = storage._deserialize_key(serialized)

        assert deserialized == key

    @patch("storages.mongodb_storage.MongoClient")
    def test_deserialize_invalid_key_format(self, mock_client_class):
        """Test deserialization fails with invalid key format."""
        mock_client = Mock()
        mock_db = Mock()
        mock_collection = Mock()
        mock_client.admin.command.return_value = None
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_db.__getitem__ = Mock(return_value=mock_collection)
        mock_client_class.return_value = mock_client

        storage = MongoDBStorage("mongodb://localhost:27017")

        import pickle

        invalid_key = ("scope", "namespace")  # Missing third element
        serialized_key = pickle.dumps(invalid_key).hex()

        with pytest.raises(ValueError, match="Invalid cache key format"):
            storage._deserialize_key(serialized_key)

    @patch("storages.mongodb_storage.MongoClient")
    def test_set_and_get(self, mock_client_class):
        """Test setting and getting values."""
        mock_client = Mock()
        mock_db = Mock()
        mock_collection = Mock()
        mock_client.admin.command.return_value = None
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_db.__getitem__ = Mock(return_value=mock_collection)
        mock_client_class.return_value = mock_client

        storage = MongoDBStorage("mongodb://localhost:27017")
        key: _CacheKey = ("scope", "namespace", ("arg1", "arg2"))
        value: _CacheValue = ("cached_data", 1234567890.0)

        # Test set
        storage.set(key, value)
        mock_collection.replace_one.assert_called_once()

        # Test get
        import pickle

        serialized_value = pickle.dumps(value)
        mock_collection.find_one.return_value = {"value": serialized_value}

        result = storage.get(key)
        assert result == value

    @patch("storages.mongodb_storage.MongoClient")
    def test_get_nonexistent_key(self, mock_client_class):
        """Test getting a non-existent key returns None."""
        mock_client = Mock()
        mock_db = Mock()
        mock_collection = Mock()
        mock_collection.find_one.return_value = None
        mock_client.admin.command.return_value = None
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_db.__getitem__ = Mock(return_value=mock_collection)
        mock_client_class.return_value = mock_client

        storage = MongoDBStorage("mongodb://localhost:27017")
        key: _CacheKey = ("scope", "namespace", ("arg1",))

        result = storage.get(key)
        assert result is None

    @patch("storages.mongodb_storage.MongoClient")
    def test_get_with_deserialization_error(self, mock_client_class):
        """Test get returns None when deserialization fails."""
        mock_client = Mock()
        mock_db = Mock()
        mock_collection = Mock()
        mock_collection.find_one.return_value = {"value": b"invalid_pickle_data"}
        mock_client.admin.command.return_value = None
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_db.__getitem__ = Mock(return_value=mock_collection)
        mock_client_class.return_value = mock_client

        storage = MongoDBStorage("mongodb://localhost:27017")
        key: _CacheKey = ("scope", "namespace", ("arg1",))

        result = storage.get(key)
        assert result is None

    @patch("storages.mongodb_storage.MongoClient")
    def test_evict(self, mock_client_class):
        """Test evicting a key."""
        mock_client = Mock()
        mock_db = Mock()
        mock_collection = Mock()
        mock_client.admin.command.return_value = None
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_db.__getitem__ = Mock(return_value=mock_collection)
        mock_client_class.return_value = mock_client

        storage = MongoDBStorage("mongodb://localhost:27017")
        key: _CacheKey = ("scope", "namespace", ("arg1",))

        storage.evict(key)
        mock_collection.delete_one.assert_called_once()

    @patch("storages.mongodb_storage.MongoClient")
    def test_get_all_keys(self, mock_client_class):
        """Test getting all keys."""
        mock_client = Mock()
        mock_db = Mock()
        mock_collection = Mock()
        mock_client.admin.command.return_value = None
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_db.__getitem__ = Mock(return_value=mock_collection)
        mock_client_class.return_value = mock_client

        storage = MongoDBStorage("mongodb://localhost:27017")

        import pickle

        key1: _CacheKey = ("scope1", "ns1", ("arg1",))
        key2: _CacheKey = ("scope2", "ns2", ("arg2",))

        serialized_keys = [{"_id": pickle.dumps(key1).hex()}, {"_id": pickle.dumps(key2).hex()}]
        mock_collection.find.return_value = serialized_keys

        result = storage.get_all_keys()
        assert len(result) == 2
        assert key1 in result
        assert key2 in result

    @patch("storages.mongodb_storage.MongoClient")
    def test_get_all_keys_with_error(self, mock_client_class):
        """Test get_all_keys returns empty list on error."""
        mock_client = Mock()
        mock_db = Mock()
        mock_collection = Mock()
        mock_collection.find.side_effect = Exception("Database error")
        mock_client.admin.command.return_value = None
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_db.__getitem__ = Mock(return_value=mock_collection)
        mock_client_class.return_value = mock_client

        storage = MongoDBStorage("mongodb://localhost:27017")

        result = storage.get_all_keys()
        assert result == []

    @patch("storages.mongodb_storage.MongoClient")
    def test_clear(self, mock_client_class):
        """Test clearing all data."""
        mock_client = Mock()
        mock_db = Mock()
        mock_collection = Mock()
        mock_client.admin.command.return_value = None
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_db.__getitem__ = Mock(return_value=mock_collection)
        mock_client_class.return_value = mock_client

        storage = MongoDBStorage("mongodb://localhost:27017")

        storage.clear()
        mock_collection.delete_many.assert_called_once_with({})

    @patch("storages.mongodb_storage.MongoClient")
    def test_set_with_error(self, mock_client_class):
        """Test set raises exception on database error."""
        mock_client = Mock()
        mock_db = Mock()
        mock_collection = Mock()
        mock_collection.replace_one.side_effect = Exception("Database error")
        mock_client.admin.command.return_value = None
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_db.__getitem__ = Mock(return_value=mock_collection)
        mock_client_class.return_value = mock_client

        storage = MongoDBStorage("mongodb://localhost:27017")
        key: _CacheKey = ("scope", "namespace", ("arg1",))
        value: _CacheValue = ("data", 123.0)

        with pytest.raises(Exception):
            storage.set(key, value)

    @patch("storages.mongodb_storage.MongoClient")
    def test_evict_with_error_logs_but_continues(self, mock_client_class):
        """Test evict logs error but doesn't raise exception."""
        mock_client = Mock()
        mock_db = Mock()
        mock_collection = Mock()
        mock_collection.delete_one.side_effect = Exception("Database error")
        mock_client.admin.command.return_value = None
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_db.__getitem__ = Mock(return_value=mock_collection)
        mock_client_class.return_value = mock_client

        storage = MongoDBStorage("mongodb://localhost:27017")
        key: _CacheKey = ("scope", "namespace", ("arg1",))

        # Should not raise exception
        storage.evict(key)

    @patch("storages.mongodb_storage.MongoClient")
    def test_clear_with_error_logs_but_continues(self, mock_client_class):
        """Test clear logs error but doesn't raise exception."""
        mock_client = Mock()
        mock_db = Mock()
        mock_collection = Mock()
        mock_collection.delete_many.side_effect = Exception("Database error")
        mock_client.admin.command.return_value = None
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_db.__getitem__ = Mock(return_value=mock_collection)
        mock_client_class.return_value = mock_client

        storage = MongoDBStorage("mongodb://localhost:27017")

        # Should not raise exception
        storage.clear()
