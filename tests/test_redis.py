import unittest
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from storages.redis import RedisStorage


class TestRedisStorage(unittest.TestCase):
    @patch("storages.redis.redis.from_url")
    @patch("storages.redis.async_redis.from_url")
    def test_init(self, mock_async_redis, mock_redis):
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client

        storage = RedisStorage("redis://localhost:6379")
        self.assertIsNotNone(storage)
        mock_client.ping.assert_called_once()

    @patch("storages.redis.redis.from_url")
    @patch("storages.redis.async_redis.from_url")
    def test_init_connection_error(self, mock_async_redis, mock_redis):
        from redis.exceptions import ConnectionError as RedisConnectionError

        mock_client = MagicMock()
        mock_client.ping.side_effect = RedisConnectionError("Connection failed")
        mock_redis.return_value = mock_client

        with self.assertRaises(ConnectionError):
            RedisStorage("redis://localhost:6379")

    @patch("storages.redis.redis.from_url")
    @patch("storages.redis.async_redis.from_url")
    def test_set(self, mock_async_redis, mock_redis):
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client

        storage = RedisStorage("redis://localhost:6379")
        storage.set("key1", "value1", 10)

        mock_client.set.assert_called_once()

    @patch("storages.redis.redis.from_url")
    @patch("storages.redis.async_redis.from_url")
    def test_get(self, mock_async_redis, mock_redis):
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.get.return_value = '{"value": "value1", "ttl_seconds": 100.0}'
        mock_redis.return_value = mock_client

        storage = RedisStorage("redis://localhost:6379")
        result = storage.get("key1")

        self.assertIsNotNone(result)
        self.assertEqual(result[0], "value1")

    @patch("storages.redis.redis.from_url")
    @patch("storages.redis.async_redis.from_url")
    def test_get_none(self, mock_async_redis, mock_redis):
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.get.return_value = None
        mock_redis.return_value = mock_client

        storage = RedisStorage("redis://localhost:6379")
        result = storage.get("key1")

        self.assertIsNone(result)

    @patch("storages.redis.redis.from_url")
    @patch("storages.redis.async_redis.from_url")
    def test_evict(self, mock_async_redis, mock_redis):
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client

        storage = RedisStorage("redis://localhost:6379")
        storage.evict("key1")

        mock_client.delete.assert_called_once_with("key1")

    @patch("storages.redis.redis.from_url")
    @patch("storages.redis.async_redis.from_url")
    def test_get_all_keys(self, mock_async_redis, mock_redis):
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.keys.return_value = ["key1", "key2"]
        mock_redis.return_value = mock_client

        storage = RedisStorage("redis://localhost:6379")
        keys = storage.get_all_keys()

        self.assertEqual(len(keys), 2)
        self.assertIn("key1", keys)

    @patch("storages.redis.redis.from_url")
    @patch("storages.redis.async_redis.from_url")
    def test_clear(self, mock_async_redis, mock_redis):
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client

        storage = RedisStorage("redis://localhost:6379")
        storage.clear()

        mock_client.flushdb.assert_called_once()

    @patch("storages.redis.redis.from_url")
    @patch("storages.redis.async_redis.from_url")
    def test_get_sync_client(self, mock_async_redis, mock_redis):
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client

        storage = RedisStorage("redis://localhost:6379")
        client = storage.get_sync_client()

        self.assertIsNotNone(client)


class TestRedisStorageAsync(IsolatedAsyncioTestCase):
    @patch("storages.redis.redis.from_url")
    @patch("storages.redis.async_redis.from_url")
    async def test_aget(self, mock_async_redis, mock_redis):
        mock_sync_client = MagicMock()
        mock_sync_client.ping.return_value = True
        mock_redis.return_value = mock_sync_client

        mock_async_client = AsyncMock()
        mock_async_client.get.return_value = '{"value": "value1", "ttl_seconds": 100.0}'
        mock_async_redis.return_value = mock_async_client

        storage = RedisStorage("redis://localhost:6379")
        result = await storage.aget("key1")

        self.assertIsNotNone(result)
        self.assertEqual(result[0], "value1")

    @patch("storages.redis.redis.from_url")
    @patch("storages.redis.async_redis.from_url")
    async def test_aget_none(self, mock_async_redis, mock_redis):
        mock_sync_client = MagicMock()
        mock_sync_client.ping.return_value = True
        mock_redis.return_value = mock_sync_client

        mock_async_client = AsyncMock()
        mock_async_client.get.return_value = None
        mock_async_redis.return_value = mock_async_client

        storage = RedisStorage("redis://localhost:6379")
        result = await storage.aget("key1")

        self.assertIsNone(result)

    @patch("storages.redis.redis.from_url")
    @patch("storages.redis.async_redis.from_url")
    async def test_aset(self, mock_async_redis, mock_redis):
        mock_sync_client = MagicMock()
        mock_sync_client.ping.return_value = True
        mock_redis.return_value = mock_sync_client

        mock_async_client = AsyncMock()
        mock_async_redis.return_value = mock_async_client

        storage = RedisStorage("redis://localhost:6379")
        await storage.aset("key1", "value1", 10)

        mock_async_client.set.assert_called_once()

    @patch("storages.redis.redis.from_url")
    @patch("storages.redis.async_redis.from_url")
    async def test_aevict(self, mock_async_redis, mock_redis):
        mock_sync_client = MagicMock()
        mock_sync_client.ping.return_value = True
        mock_redis.return_value = mock_sync_client

        mock_async_client = AsyncMock()
        mock_async_redis.return_value = mock_async_client

        storage = RedisStorage("redis://localhost:6379")
        await storage.aevict("key1")

        mock_async_client.delete.assert_called_once()

    @patch("storages.redis.redis.from_url")
    @patch("storages.redis.async_redis.from_url")
    async def test_aget_all_keys(self, mock_async_redis, mock_redis):
        mock_sync_client = MagicMock()
        mock_sync_client.ping.return_value = True
        mock_redis.return_value = mock_sync_client

        mock_async_client = AsyncMock()
        mock_async_client.keys.return_value = ["key1", "key2"]
        mock_async_redis.return_value = mock_async_client

        storage = RedisStorage("redis://localhost:6379")
        keys = await storage.aget_all_keys()

        self.assertEqual(len(keys), 2)
        self.assertIn("key1", keys)

    @patch("storages.redis.redis.from_url")
    @patch("storages.redis.async_redis.from_url")
    async def test_aclear(self, mock_async_redis, mock_redis):
        mock_sync_client = MagicMock()
        mock_sync_client.ping.return_value = True
        mock_redis.return_value = mock_sync_client

        mock_async_client = AsyncMock()
        mock_async_redis.return_value = mock_async_client

        storage = RedisStorage("redis://localhost:6379")
        await storage.aclear()

        mock_async_client.flushdb.assert_called_once()

    @patch("storages.redis.redis.from_url")
    @patch("storages.redis.async_redis.from_url")
    async def test_get_async_client(self, mock_async_redis, mock_redis):
        mock_sync_client = MagicMock()
        mock_sync_client.ping.return_value = True
        mock_redis.return_value = mock_sync_client

        mock_async_client = AsyncMock()
        mock_async_redis.return_value = mock_async_client

        storage = RedisStorage("redis://localhost:6379")
        async with storage.get_async_client() as client:
            self.assertIsNotNone(client)
