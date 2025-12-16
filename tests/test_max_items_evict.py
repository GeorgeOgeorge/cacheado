import unittest

from storages.rules.max_items_evict import MaxItemsEvict
from utils.cache_types import StorageRuleAction


class TestMaxItemsEvict(unittest.TestCase):
    def test_on_set_under_limit(self):
        rule = MaxItemsEvict(max_items=2)
        effect = rule.on_set("key1", "value1", 10)
        self.assertIsNone(effect)

    def test_on_set_at_limit(self):
        rule = MaxItemsEvict(max_items=2)
        rule.on_set("key1", "value1", 10)
        rule.on_set("key2", "value2", 10)
        effect = rule.on_set("key3", "value3", 10)
        self.assertIsNotNone(effect)
        self.assertEqual(effect.action, StorageRuleAction.EVICT)
        self.assertEqual(effect.cache_key, "key3")

    def test_on_set_existing_key(self):
        rule = MaxItemsEvict(max_items=2)
        rule.on_set("key1", "value1", 10)
        effect = rule.on_set("key1", "new_value", 10)
        self.assertIsNone(effect)

    def test_on_get(self):
        rule = MaxItemsEvict(max_items=2)
        effect = rule.on_get("key1")
        self.assertIsNone(effect)

    def test_on_evict(self):
        rule = MaxItemsEvict(max_items=2)
        rule.on_set("key1", "value1", 10)
        effect = rule.on_evict("key1")
        self.assertIsNone(effect)

    def test_on_clear(self):
        rule = MaxItemsEvict(max_items=2)
        rule.on_set("key1", "value1", 10)
        effect = rule.on_clear()
        self.assertIsNone(effect)

    def test_on_get_all_keys(self):
        rule = MaxItemsEvict(max_items=2)
        effect = rule.on_get_all_keys()
        self.assertIsNone(effect)

    def test_on_evict_nonexistent_key(self):
        rule = MaxItemsEvict(max_items=2)
        effect = rule.on_evict("nonexistent")
        self.assertIsNone(effect)

    def test_multiple_evictions(self):
        rule = MaxItemsEvict(max_items=2)
        rule.on_set("key1", "value1", 10)
        rule.on_evict("key1")
        rule.on_evict("key1")
        self.assertIsNone(rule.on_get("key1"))
