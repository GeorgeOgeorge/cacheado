import unittest
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from storages.mongodb import MongoDBStorage


class TestMongoDBStorage(unittest.TestCase):
    @patch("storages.mongodb.MongoClient")
    @patch("storages.mongodb.AsyncMongoClient")
    def test_init(self, mock_async_client, mock_sync_client):
        mock_client = MagicMock()
        mock_client.admin.command.return_value = True
        mock_sync_client.return_value = mock_client

        storage = MongoDBStorage("mongodb://localhost:27017")
        self.assertIsNotNone(storage)
        mock_client.admin.command.assert_called_once_with("ping")

    @patch("storages.mongodb.MongoClient")
    @patch("storages.mongodb.AsyncMongoClient")
    def test_init_connection_error(self, mock_async_client, mock_sync_client):
        mock_client = MagicMock()
        mock_client.admin.command.side_effect = Exception("Connection failed")
        mock_sync_client.return_value = mock_client

        with self.assertRaises(ConnectionError):
            MongoDBStorage("mongodb://localhost:27017")

    @patch("storages.mongodb.MongoClient")
    @patch("storages.mongodb.AsyncMongoClient")
    def test_check_collection(self, mock_async_client, mock_sync_client):
        mock_client = MagicMock()
        mock_client.admin.command.return_value = True
        mock_sync_client.return_value = mock_client

        mock_collection = MagicMock()
        mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection

        MongoDBStorage.check_collection(mock_client, "test_db", "test_collection")
        mock_collection.create_index.assert_called_once()

    @patch("storages.mongodb.MongoClient")
    @patch("storages.mongodb.AsyncMongoClient")
    def test_set(self, mock_async_client, mock_sync_client):
        mock_client = MagicMock()
        mock_client.admin.command.return_value = True
        mock_sync_client.return_value = mock_client

        mock_collection = MagicMock()
        mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection

        storage = MongoDBStorage("mongodb://localhost:27017")
        storage.set("key1", "value1", 10)

        mock_collection.update_one.assert_called_once()

    @patch("storages.mongodb.MongoClient")
    @patch("storages.mongodb.AsyncMongoClient")
    def test_get(self, mock_async_client, mock_sync_client):
        mock_client = MagicMock()
        mock_client.admin.command.return_value = True
        mock_sync_client.return_value = mock_client

        mock_collection = MagicMock()
        mock_collection.find_one.return_value = {"key": "key1", "value": "value1", "ttl_seconds": 100.0}
        mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection

        storage = MongoDBStorage("mongodb://localhost:27017")
        result = storage.get("key1")

        self.assertIsNotNone(result)
        self.assertEqual(result[0], "value1")

    @patch("storages.mongodb.MongoClient")
    @patch("storages.mongodb.AsyncMongoClient")
    def test_get_none(self, mock_async_client, mock_sync_client):
        mock_client = MagicMock()
        mock_client.admin.command.return_value = True
        mock_sync_client.return_value = mock_client

        mock_collection = MagicMock()
        mock_collection.find_one.return_value = None
        mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection

        storage = MongoDBStorage("mongodb://localhost:27017")
        result = storage.get("key1")

        self.assertIsNone(result)

    @patch("storages.mongodb.MongoClient")
    @patch("storages.mongodb.AsyncMongoClient")
    def test_evict(self, mock_async_client, mock_sync_client):
        mock_client = MagicMock()
        mock_client.admin.command.return_value = True
        mock_sync_client.return_value = mock_client

        mock_collection = MagicMock()
        mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection

        storage = MongoDBStorage("mongodb://localhost:27017")
        storage.evict("key1")

        mock_collection.delete_one.assert_called_once()

    @patch("storages.mongodb.MongoClient")
    @patch("storages.mongodb.AsyncMongoClient")
    def test_get_all_keys(self, mock_async_client, mock_sync_client):
        mock_client = MagicMock()
        mock_client.admin.command.return_value = True
        mock_sync_client.return_value = mock_client

        mock_collection = MagicMock()
        mock_collection.distinct.return_value = ["key1", "key2"]
        mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection

        storage = MongoDBStorage("mongodb://localhost:27017")
        keys = storage.get_all_keys()

        self.assertEqual(len(keys), 2)
        self.assertIn("key1", keys)

    @patch("storages.mongodb.MongoClient")
    @patch("storages.mongodb.AsyncMongoClient")
    def test_clear(self, mock_async_client, mock_sync_client):
        mock_client = MagicMock()
        mock_client.admin.command.return_value = True
        mock_sync_client.return_value = mock_client

        mock_collection = MagicMock()
        mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection

        storage = MongoDBStorage("mongodb://localhost:27017")
        storage.clear()

        mock_collection.delete_many.assert_called_once()

    @patch("storages.mongodb.MongoClient")
    @patch("storages.mongodb.AsyncMongoClient")
    def test_get_sync_collection(self, mock_async_client, mock_sync_client):
        mock_client = MagicMock()
        mock_client.admin.command.return_value = True
        mock_sync_client.return_value = mock_client

        storage = MongoDBStorage("mongodb://localhost:27017")
        collection = storage.get_sync_collection()

        self.assertIsNotNone(collection)


class TestMongoDBStorageAsync(IsolatedAsyncioTestCase):
    @patch("storages.mongodb.MongoClient")
    @patch("storages.mongodb.AsyncMongoClient")
    async def test_aget(self, mock_async_client_class, mock_sync_client):
        mock_sync = MagicMock()
        mock_sync.admin.command.return_value = True
        mock_sync_client.return_value = mock_sync

        mock_async = MagicMock()
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = {"key": "key1", "value": "value1", "ttl_seconds": 100.0}
        mock_async.__getitem__.return_value.__getitem__.return_value = mock_collection
        mock_async_client_class.return_value = mock_async

        storage = MongoDBStorage("mongodb://localhost:27017")
        result = await storage.aget("key1")

        self.assertIsNotNone(result)
        self.assertEqual(result[0], "value1")

    @patch("storages.mongodb.MongoClient")
    @patch("storages.mongodb.AsyncMongoClient")
    async def test_aget_none(self, mock_async_client_class, mock_sync_client):
        mock_sync = MagicMock()
        mock_sync.admin.command.return_value = True
        mock_sync_client.return_value = mock_sync

        mock_async = MagicMock()
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = None
        mock_async.__getitem__.return_value.__getitem__.return_value = mock_collection
        mock_async_client_class.return_value = mock_async

        storage = MongoDBStorage("mongodb://localhost:27017")
        result = await storage.aget("key1")

        self.assertIsNone(result)

    @patch("storages.mongodb.MongoClient")
    @patch("storages.mongodb.AsyncMongoClient")
    async def test_aset(self, mock_async_client_class, mock_sync_client):
        mock_sync = MagicMock()
        mock_sync.admin.command.return_value = True
        mock_sync_client.return_value = mock_sync

        mock_async = MagicMock()
        mock_collection = AsyncMock()
        mock_async.__getitem__.return_value.__getitem__.return_value = mock_collection
        mock_async_client_class.return_value = mock_async

        storage = MongoDBStorage("mongodb://localhost:27017")
        await storage.aset("key1", "value1", 10)

        mock_collection.update_one.assert_called_once()

    @patch("storages.mongodb.MongoClient")
    @patch("storages.mongodb.AsyncMongoClient")
    async def test_aevict(self, mock_async_client_class, mock_sync_client):
        mock_sync = MagicMock()
        mock_sync.admin.command.return_value = True
        mock_sync_client.return_value = mock_sync

        mock_async = MagicMock()
        mock_collection = AsyncMock()
        mock_async.__getitem__.return_value.__getitem__.return_value = mock_collection
        mock_async_client_class.return_value = mock_async

        storage = MongoDBStorage("mongodb://localhost:27017")
        await storage.aevict("key1")

        mock_collection.delete_one.assert_called_once()

    @patch("storages.mongodb.MongoClient")
    @patch("storages.mongodb.AsyncMongoClient")
    async def test_aget_all_keys(self, mock_async_client_class, mock_sync_client):
        mock_sync = MagicMock()
        mock_sync.admin.command.return_value = True
        mock_sync_client.return_value = mock_sync

        mock_async = MagicMock()
        mock_collection = AsyncMock()
        mock_collection.distinct.return_value = ["key1", "key2"]
        mock_async.__getitem__.return_value.__getitem__.return_value = mock_collection
        mock_async_client_class.return_value = mock_async

        storage = MongoDBStorage("mongodb://localhost:27017")
        keys = await storage.aget_all_keys()

        self.assertEqual(len(keys), 2)
        self.assertIn("key1", keys)

    @patch("storages.mongodb.MongoClient")
    @patch("storages.mongodb.AsyncMongoClient")
    async def test_aclear(self, mock_async_client_class, mock_sync_client):
        mock_sync = MagicMock()
        mock_sync.admin.command.return_value = True
        mock_sync_client.return_value = mock_sync

        mock_async = MagicMock()
        mock_collection = AsyncMock()
        mock_async.__getitem__.return_value.__getitem__.return_value = mock_collection
        mock_async_client_class.return_value = mock_async

        storage = MongoDBStorage("mongodb://localhost:27017")
        await storage.aclear()

        mock_collection.delete_many.assert_called_once()

    @patch("storages.mongodb.MongoClient")
    @patch("storages.mongodb.AsyncMongoClient")
    async def test_get_async_collection(self, mock_async_client_class, mock_sync_client):
        mock_sync = MagicMock()
        mock_sync.admin.command.return_value = True
        mock_sync_client.return_value = mock_sync

        mock_async = MagicMock()
        mock_async_client_class.return_value = mock_async

        storage = MongoDBStorage("mongodb://localhost:27017")
        async with storage.get_async_collection() as collection:
            self.assertIsNotNone(collection)
