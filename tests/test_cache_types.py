import unittest

from utils.cache_types import CacheKey, RuleSideEffect, StorageRuleAction


class TestCacheKey(unittest.TestCase):
    def test_as_string(self):
        key = CacheKey("global", "func", (b"args",))
        self.assertIn("::", key.as_string())

    def test_from_string(self):
        key_str = "global::func::123"
        key = CacheKey.from_string(key_str)
        self.assertEqual(key.scope_prefix, "global")
        self.assertEqual(key.namespace, "func")
        self.assertEqual(key.args_hash, 123)

    def test_from_string_invalid(self):
        with self.assertRaises(ValueError):
            CacheKey.from_string("invalid")

    def test_extract_namespace(self):
        self.assertEqual(CacheKey.extract_namespace("global::func::123"), "func")

    def test_extract_scope_prefix(self):
        self.assertEqual(CacheKey.extract_scope_prefix("global::func::123"), "global")

    def test_extract_args_hash(self):
        self.assertEqual(CacheKey.extract_args_hash("global::func::123"), 123)

    def test_equality(self):
        key1 = CacheKey("global", "func", (b"args",))
        key2 = CacheKey("global", "func", (b"args",))
        self.assertEqual(key1, key2)

    def test_hash(self):
        key = CacheKey("global", "func", (b"args",))
        self.assertIsInstance(hash(key), int)

    def test_extract_namespace_empty(self):
        result = CacheKey.extract_namespace("")
        self.assertEqual(result, "")

    def test_extract_namespace_single_part(self):
        result = CacheKey.extract_namespace("global")
        self.assertEqual(result, "")

    def test_extract_scope_prefix_empty(self):
        result = CacheKey.extract_scope_prefix("")
        self.assertEqual(result, "")

    def test_extract_args_hash_empty(self):
        result = CacheKey.extract_args_hash("")
        self.assertEqual(result, 0)

    def test_extract_args_hash_invalid(self):
        with self.assertRaises(ValueError):
            CacheKey.extract_args_hash("global::func::invalid")

    def test_from_string_two_parts(self):
        with self.assertRaises(ValueError):
            CacheKey.from_string("global::func")

    def test_from_string_four_parts(self):
        with self.assertRaises(ValueError):
            CacheKey.from_string("global::func::123::extra")


class TestStorageRuleAction(unittest.TestCase):
    def test_evict(self):
        self.assertEqual(StorageRuleAction.EVICT, "evict")

    def test_set(self):
        self.assertEqual(StorageRuleAction.SET, "set")

    def test_get(self):
        self.assertEqual(StorageRuleAction.GET, "get")

    def test_clear(self):
        self.assertEqual(StorageRuleAction.CLEAR, "clear")


class TestRuleSideEffect(unittest.TestCase):
    def test_creation(self):
        effect = RuleSideEffect(cache_key="key1", action=StorageRuleAction.EVICT)
        self.assertEqual(effect.cache_key, "key1")
        self.assertEqual(effect.action, StorageRuleAction.EVICT)
