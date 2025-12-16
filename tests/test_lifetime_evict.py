import time
import unittest

from storages.rules.lifetime_evict import LifeTimeEvict
from utils.cache_types import StorageRuleAction


class TestLifeTimeEvict(unittest.TestCase):
    def setUp(self):
        self.rule = LifeTimeEvict()

    def test_on_set(self):
        effect = self.rule.on_set("key1", "value1", 10)
        self.assertIsNone(effect)

    def test_on_get_not_expired(self):
        self.rule.on_set("key1", "value1", 10)
        effect = self.rule.on_get("key1")
        self.assertIsNone(effect)

    def test_on_get_expired(self):
        self.rule.on_set("key1", "value1", 0.01)
        time.sleep(0.02)
        effect = self.rule.on_get("key1")
        self.assertIsNotNone(effect)
        self.assertEqual(effect.action, StorageRuleAction.EVICT)

    def test_on_evict(self):
        self.rule.on_set("key1", "value1", 10)
        effect = self.rule.on_evict("key1")
        self.assertIsNone(effect)

    def test_on_clear(self):
        self.rule.on_set("key1", "value1", 10)
        effect = self.rule.on_clear()
        self.assertIsNone(effect)

    def test_on_get_all_keys(self):
        effect = self.rule.on_get_all_keys()
        self.assertIsNone(effect)

    def test_on_get_nonexistent_key(self):
        effect = self.rule.on_get("nonexistent")
        self.assertIsNone(effect)

    def test_on_evict_nonexistent_key(self):
        effect = self.rule.on_evict("nonexistent")
        self.assertIsNone(effect)
