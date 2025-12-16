import unittest
from unittest import IsolatedAsyncioTestCase

from storages.in_memory import InMemory


class TestInMemory(unittest.TestCase):
    def setUp(self):
        self.storage = InMemory()

    def test_set_and_get(self):
        self.storage.set("key1", "value1", 10)
        result = self.storage.get("key1")
        self.assertEqual(result[0], "value1")

    def test_get_nonexistent(self):
        self.assertIsNone(self.storage.get("missing"))

    def test_evict(self):
        self.storage.set("key1", "value1", 10)
        self.storage.evict("key1")
        self.assertIsNone(self.storage.get("key1"))

    def test_clear(self):
        self.storage.set("key1", "value1", 10)
        self.storage.set("key2", "value2", 10)
        self.storage.clear()
        self.assertIsNone(self.storage.get("key1"))
        self.assertIsNone(self.storage.get("key2"))

    def test_get_all_keys(self):
        self.storage.set("key1", "value1", 10)
        self.storage.set("key2", "value2", 10)
        keys = self.storage.get_all_keys()
        self.assertEqual(len(keys), 2)
        self.assertIn("key1", keys)

    def test_get_stats(self):
        self.storage.set("key1", "value1", 10)
        stats = self.storage.get_stats()
        self.assertEqual(stats["storage_type"], "in_memory")
        self.assertEqual(stats["total_keys"], 1)

    def test_evict_nonexistent(self):
        self.storage.evict("nonexistent")
        self.assertIsNone(self.storage.get("nonexistent"))

    def test_multiple_sets_same_key(self):
        self.storage.set("key1", "value1", 10)
        self.storage.set("key1", "value2", 10)
        result = self.storage.get("key1")
        self.assertEqual(result[0], "value2")

    def test_get_all_keys_empty(self):
        keys = self.storage.get_all_keys()
        self.assertEqual(len(keys), 0)

    def test_clear_empty(self):
        self.storage.clear()
        keys = self.storage.get_all_keys()
        self.assertEqual(len(keys), 0)


class TestInMemoryAsync(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.storage = InMemory()

    async def test_aget(self):
        self.storage.set("key1", "value1", 10)
        result = await self.storage.aget("key1")
        self.assertEqual(result[0], "value1")

    async def test_aset(self):
        await self.storage.aset("key1", "value1", 10)
        result = self.storage.get("key1")
        self.assertEqual(result[0], "value1")

    async def test_aevict(self):
        self.storage.set("key1", "value1", 10)
        await self.storage.aevict("key1")
        self.assertIsNone(self.storage.get("key1"))

    async def test_aclear(self):
        self.storage.set("key1", "value1", 10)
        await self.storage.aclear()
        self.assertIsNone(self.storage.get("key1"))

    async def test_aget_all_keys(self):
        self.storage.set("key1", "value1", 10)
        keys = await self.storage.aget_all_keys()
        self.assertIn("key1", keys)

    async def test_aget_all_keys_empty(self):
        keys = await self.storage.aget_all_keys()
        self.assertEqual(len(keys), 0)
