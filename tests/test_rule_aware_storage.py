import unittest
from unittest import IsolatedAsyncioTestCase

from storages.in_memory import InMemory
from storages.rule_aware_storage import RuleAwareStorage
from storages.rules.lifetime_evict import LifeTimeEvict


class TestRuleAwareStorage(unittest.TestCase):
    def setUp(self):
        storage = InMemory()
        rule = LifeTimeEvict()
        self.aware = RuleAwareStorage(storage, [rule])

    def test_set(self):
        self.aware.set("key1", "value1", 10)
        result = self.aware.get("key1")
        self.assertEqual(result[0], "value1")

    def test_get(self):
        self.aware.set("key1", "value1", 10)
        result = self.aware.get("key1")
        self.assertIsNotNone(result)

    def test_evict(self):
        self.aware.set("key1", "value1", 10)
        self.aware.evict("key1")
        self.assertIsNone(self.aware.get("key1"))

    def test_clear(self):
        self.aware.set("key1", "value1", 10)
        self.aware.clear()
        self.assertIsNone(self.aware.get("key1"))

    def test_get_all_keys(self):
        self.aware.set("key1", "value1", 10)
        keys = self.aware.get_all_keys()
        self.assertIn("key1", keys)

    def test_get_stats(self):
        stats = self.aware.get_stats()
        self.assertIn("storage_type", stats)


class TestRuleAwareStorageAsync(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        storage = InMemory()
        rule = LifeTimeEvict()
        self.aware = RuleAwareStorage(storage, [rule])

    async def test_aset(self):
        await self.aware.aset("key1", "value1", 10)
        result = await self.aware.aget("key1")
        self.assertEqual(result[0], "value1")

    async def test_aget(self):
        await self.aware.aset("key1", "value1", 10)
        result = await self.aware.aget("key1")
        self.assertIsNotNone(result)

    async def test_aevict(self):
        await self.aware.aset("key1", "value1", 10)
        await self.aware.aevict("key1")
        result = await self.aware.aget("key1")
        self.assertIsNone(result)

    async def test_aclear(self):
        await self.aware.aset("key1", "value1", 10)
        await self.aware.aclear()
        result = await self.aware.aget("key1")
        self.assertIsNone(result)

    async def test_aget_all_keys(self):
        await self.aware.aset("key1", "value1", 10)
        await self.aware.aset("key2", "value2", 10)
        keys = await self.aware.aget_all_keys()
        self.assertIn("key1", keys)
        self.assertIn("key2", keys)
