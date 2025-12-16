import unittest

from storages.rules.lru_evict import LRUEvict
from utils.cache_types import StorageRuleAction


class TestLRUEvict(unittest.TestCase):
    def test_on_set_under_limit(self):
        rule = LRUEvict(max_items=2)
        effect = rule.on_set("key1", "value1", 10)
        self.assertIsNone(effect)

    def test_on_set_over_limit(self):
        rule = LRUEvict(max_items=2)
        rule.on_set("key1", "value1", 10)
        rule.on_set("key2", "value2", 10)
        effect = rule.on_set("key3", "value3", 10)
        self.assertIsNotNone(effect)
        self.assertEqual(effect.action, StorageRuleAction.EVICT)
        self.assertEqual(effect.cache_key, "key1")

    def test_on_get(self):
        rule = LRUEvict(max_items=2)
        rule.on_set("key1", "value1", 10)
        effect = rule.on_get("key1")
        self.assertIsNone(effect)

    def test_on_evict(self):
        rule = LRUEvict(max_items=2)
        rule.on_set("key1", "value1", 10)
        effect = rule.on_evict("key1")
        self.assertIsNone(effect)

    def test_on_clear(self):
        rule = LRUEvict(max_items=2)
        rule.on_set("key1", "value1", 10)
        effect = rule.on_clear()
        self.assertIsNone(effect)

    def test_on_get_all_keys(self):
        rule = LRUEvict(max_items=2)
        effect = rule.on_get_all_keys()
        self.assertIsNone(effect)

    def test_on_get_nonexistent_key(self):
        rule = LRUEvict(max_items=2)
        effect = rule.on_get("nonexistent")
        self.assertIsNone(effect)

    def test_on_evict_nonexistent_key(self):
        rule = LRUEvict(max_items=2)
        effect = rule.on_evict("nonexistent")
        self.assertIsNone(effect)

    def test_on_set_updates_existing(self):
        rule = LRUEvict(max_items=2)
        rule.on_set("key1", "value1", 10)
        rule.on_set("key1", "value2", 10)
        effect = rule.on_set("key2", "value2", 10)
        self.assertIsNone(effect)
