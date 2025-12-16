import time
import unittest
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock

from cache import Cache
from storages.in_memory import InMemory
from storages.rules.lifetime_evict import LifeTimeEvict
from storages.rules.lru_evict import LRUEvict
from utils.cache_scope_config import ScopeConfig, ScopeLevel


class TestCache(unittest.TestCase):
    def setUp(self):
        self.cache = Cache()

    def test_init(self):
        self.assertIsNotNone(self.cache)

    def test_set_and_get(self):
        self.cache.set("key1", "value1", 10)
        result = self.cache.get("key1")
        self.assertEqual(result, "value1")

    def test_get_nonexistent(self):
        result = self.cache.get("missing")
        self.assertIsNone(result)

    def test_evict(self):
        self.cache.set("key1", "value1", 10)
        self.cache.evict("key1")
        self.assertIsNone(self.cache.get("key1"))

    def test_clear(self):
        self.cache.set("key1", "value1", 10)
        self.cache.clear()
        self.assertIsNone(self.cache.get("key1"))

    def test_stats(self):
        self.cache.set("key1", "value1", 10)
        self.cache.get("key1")
        stats = self.cache.stats()
        self.assertEqual(stats["hits"], 1)

    def test_decorator_sync(self):
        @self.cache.cache(ttl_seconds=10)
        def func(x):
            return x * 2

        result1 = func(5)
        result2 = func(5)
        self.assertEqual(result1, 10)
        self.assertEqual(result2, 10)

    def test_with_scope(self):
        self.cache.set("key1", "value1", 10, scope="global")
        result = self.cache.get("key1", scope="global")
        self.assertEqual(result, "value1")

    def test_evict_by_scope(self):
        self.cache.set("key1", "value1", 10, scope="global")
        count = self.cache.evict_by_scope("global")
        self.assertGreaterEqual(count, 0)


class TestCacheAsync(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.cache = Cache()

    async def test_decorator_async(self):
        @self.cache.cache(ttl_seconds=10)
        async def func(x):
            return x * 2

        result1 = await func(5)
        result2 = await func(5)
        self.assertEqual(result1, 10)
        self.assertEqual(result2, 10)

    async def test_aget(self):
        self.cache.set("key1", "value1", 10)
        result = await self.cache.aget("key1")
        self.assertEqual(result, "value1")

    async def test_aset(self):
        await self.cache.aset("key1", "value1", 10)
        result = self.cache.get("key1")
        self.assertEqual(result, "value1")

    async def test_aevict(self):
        self.cache.set("key1", "value1", 10)
        await self.cache.aevict("key1")
        self.assertIsNone(self.cache.get("key1"))

    async def test_aclear(self):
        self.cache.set("key1", "value1", 10)
        await self.cache.aclear()
        self.assertIsNone(self.cache.get("key1"))


class TestCacheBuildScopePrefix(unittest.TestCase):
    def test_global(self):
        cache = Cache()
        prefix = cache._build_scope_prefix("global", {})
        self.assertEqual(prefix, "global")

    def test_with_params(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        cache = Cache(scope_config=config)
        prefix = cache._build_scope_prefix("user", {"user_id": "123"})
        self.assertIn("user:123", prefix)

    def test_missing_params(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        cache = Cache(scope_config=config)
        with self.assertRaises(ValueError):
            cache._build_scope_prefix("user", {})

    def test_nested(self):
        user_level = ScopeLevel("user", "user_id", [ScopeLevel("tenant", "tenant_id")])
        config = ScopeConfig([user_level])
        cache = Cache(scope_config=config)
        prefix = cache._build_scope_prefix("tenant", {"user_id": "123", "tenant_id": "456"})
        self.assertIn("user:123", prefix)
        self.assertIn("tenant:456", prefix)


class TestCacheComposeCacheKey(unittest.TestCase):
    def setUp(self):
        self.cache = Cache()

    def test_compose(self):
        key = self.cache._compose_cache_key("global", "func", (b"args",))
        self.assertEqual(key.scope_prefix, "global")
        self.assertEqual(key.namespace, "func")

    def test_as_string(self):
        key = self.cache._compose_cache_key("global", "func", (b"args",))
        key_str = key.as_string()
        self.assertIn("global", key_str)
        self.assertIn("func", key_str)

    def test_different_scopes(self):
        key1 = self.cache._compose_cache_key("global", "func", (b"args",))
        key2 = self.cache._compose_cache_key("user:123", "func", (b"args",))
        self.assertNotEqual(key1.as_string(), key2.as_string())


class TestCacheDecoratorAdvanced(unittest.TestCase):
    def test_decorator_with_scope(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        cache = Cache(scope_config=config)

        @cache.cache(ttl_seconds=10, scope="user")
        def func(user_id, x):
            return x * 2

        result1 = func(user_id="123", x=5)
        result2 = func(user_id="123", x=5)
        self.assertEqual(result1, 10)
        self.assertEqual(result2, 10)

    def test_decorator_different_users(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        cache = Cache(scope_config=config)

        call_count = {"count": 0}

        @cache.cache(ttl_seconds=10, scope="user")
        def func(user_id, x):
            call_count["count"] += 1
            return x * 2

        func(user_id="123", x=5)
        func(user_id="456", x=5)
        self.assertEqual(call_count["count"], 2)

    def test_decorator_cache_hit(self):
        cache = Cache()
        call_count = {"count": 0}

        @cache.cache(ttl_seconds=10)
        def func(x):
            call_count["count"] += 1
            return x * 2

        func(5)
        func(5)
        self.assertEqual(call_count["count"], 1)


class TestCacheDecoratorAdvancedAsync(IsolatedAsyncioTestCase):
    async def test_decorator_with_scope(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        cache = Cache(scope_config=config)

        @cache.cache(ttl_seconds=10, scope="user")
        async def func(user_id, x):
            return x * 2

        result1 = await func(user_id="123", x=5)
        result2 = await func(user_id="123", x=5)
        self.assertEqual(result1, 10)
        self.assertEqual(result2, 10)

    async def test_decorator_cache_hit(self):
        cache = Cache()
        call_count = {"count": 0}

        @cache.cache(ttl_seconds=10)
        async def func(x):
            call_count["count"] += 1
            return x * 2

        await func(5)
        await func(5)
        self.assertEqual(call_count["count"], 1)


class TestCacheDecoratorErrors(unittest.TestCase):
    def setUp(self):
        self.cache = Cache()

    def test_with_unhashable_args(self):
        @self.cache.cache(ttl_seconds=10)
        def func(x):
            return x

        result = func({"key": "value"})
        self.assertEqual(result, {"key": "value"})

    def test_with_kwargs(self):
        @self.cache.cache(ttl_seconds=10)
        def func(x, y=10):
            return x + y

        result1 = func(5, y=10)
        result2 = func(5, y=10)
        self.assertEqual(result1, 15)
        self.assertEqual(result2, 15)


class TestCacheDecoratorErrorsAsync(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.cache = Cache()

    async def test_with_unhashable_args(self):
        @self.cache.cache(ttl_seconds=10)
        async def func(x):
            return x

        result = await func({"key": "value"})
        self.assertEqual(result, {"key": "value"})


class TestCacheEdgeCases(unittest.TestCase):
    def test_get_from_storage_miss(self):
        cache = Cache()
        result = cache._get_from_storage(cache._compose_cache_key("global", "test", (b"args",)))
        self.assertIsNone(result)

    def test_set_in_storage_zero_ttl(self):
        cache = Cache()
        key = cache._compose_cache_key("global", "test", (b"args",))
        cache._set_in_storage(key, "value", 0)
        result = cache._get_from_storage(key)
        self.assertIsNone(result)

    def test_evict_from_storage(self):
        cache = Cache()
        key = cache._compose_cache_key("global", "test", (b"args",))
        cache._set_in_storage(key, "value", 10)
        cache._evict_from_storage(key)
        result = cache._get_from_storage(key)
        self.assertIsNone(result)

    def test_evict_by_scope_invalid(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        cache = Cache(scope_config=config)
        count = cache.evict_by_scope("user", {})
        self.assertEqual(count, 0)

    def test_cache_key_str_repr(self):
        cache = Cache()
        key = cache._compose_cache_key("global", "func", (b"args",))
        self.assertIn("global", str(key))
        self.assertIn("CacheKey", repr(key))

    def test_cache_key_inequality(self):
        cache = Cache()
        key1 = cache._compose_cache_key("global", "func1", (b"args",))
        key2 = cache._compose_cache_key("global", "func2", (b"args",))
        self.assertNotEqual(key1, key2)

    def test_cache_key_not_equal_to_string(self):
        cache = Cache()
        key = cache._compose_cache_key("global", "func", (b"args",))
        self.assertNotEqual(key, "some_string")


class TestCacheHitsMisses(unittest.TestCase):
    def setUp(self):
        self.cache = Cache()

    def test_hit(self):
        self.cache.set("key1", "value1", 10)
        self.cache.get("key1")
        stats = self.cache.stats()
        self.assertEqual(stats["hits"], 1)

    def test_miss(self):
        self.cache.get("missing")
        stats = self.cache.stats()
        self.assertEqual(stats["misses"], 1)

    def test_eviction_count(self):
        self.cache.set("key1", "value1", 10)
        self.cache.evict("key1")
        stats = self.cache.stats()
        self.assertEqual(stats["evictions"], 1)

    def test_multiple_hits(self):
        self.cache.set("key1", "value1", 10)
        self.cache.get("key1")
        self.cache.get("key1")
        self.cache.get("key1")
        stats = self.cache.stats()
        self.assertEqual(stats["hits"], 3)

    def test_stats_after_clear(self):
        self.cache.set("key1", "value1", 10)
        self.cache.get("key1")
        self.cache.clear()
        stats = self.cache.stats()
        self.assertEqual(stats["hits"], 0)
        self.assertEqual(stats["misses"], 0)


class TestCacheIntegration(unittest.TestCase):
    def test_with_lru_rule(self):
        storage = InMemory()
        rule = LRUEvict(max_items=2)
        cache = Cache(storage_provider=storage, storage_rules=[rule])

        cache.set("key1", "value1", 10)
        cache.set("key2", "value2", 10)
        cache.set("key3", "value3", 10)

        self.assertIsNone(cache.get("key1"))
        self.assertEqual(cache.get("key2"), "value2")
        self.assertEqual(cache.get("key3"), "value3")

    def test_with_multiple_rules(self):
        storage = InMemory()
        lru_rule = LRUEvict(max_items=5)
        ttl_rule = LifeTimeEvict()
        cache = Cache(storage_provider=storage, storage_rules=[lru_rule, ttl_rule])

        cache.set("key1", "value1", 10)
        result = cache.get("key1")
        self.assertEqual(result, "value1")

    def test_decorator_with_rules(self):
        storage = InMemory()
        rule = LRUEvict(max_items=2)
        cache = Cache(storage_provider=storage, storage_rules=[rule])

        @cache.cache(ttl_seconds=10)
        def func(x):
            return x * 2

        result1 = func(1)
        result2 = func(2)
        result3 = func(3)

        self.assertEqual(result1, 2)
        self.assertEqual(result2, 4)
        self.assertEqual(result3, 6)


class TestCacheMakeArgsKey(unittest.TestCase):
    def setUp(self):
        self.cache = Cache()

    def test_simple(self):
        key = self.cache._make_args_key(1, 2, 3)
        self.assertIsInstance(key, tuple)

    def test_with_kwargs(self):
        key = self.cache._make_args_key(1, 2, x=3, y=4)
        self.assertIsInstance(key, tuple)

    def test_consistency(self):
        key1 = self.cache._make_args_key(1, 2, x=3)
        key2 = self.cache._make_args_key(1, 2, x=3)
        self.assertEqual(key1, key2)

    def test_different_order(self):
        key1 = self.cache._make_args_key(x=1, y=2)
        key2 = self.cache._make_args_key(y=2, x=1)
        self.assertEqual(key1, key2)

    def test_unhashable(self):
        key = self.cache._make_args_key({"key": "value"})
        self.assertIsInstance(key, tuple)


class TestCacheMakeCacheKey(unittest.TestCase):
    def test_make_cache_key(self):
        cache = Cache()
        args_key = cache._make_args_key(1, 2)
        key = cache._make_cache_key("func", args_key, "global", {})
        self.assertEqual(key.namespace, "func")

    def test_with_scope(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        cache = Cache(scope_config=config)
        args_key = cache._make_args_key(1, 2)
        key = cache._make_cache_key("func", args_key, "user", {"user_id": "123"})
        self.assertIn("user:123", key.scope_prefix)

    def test_make_programmatic_key(self):
        cache = Cache()
        key = cache._make_programmatic_key("my_key", "global", {})
        self.assertEqual(key.namespace, "__programmatic__")

    def test_make_programmatic_key_with_scope(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        cache = Cache(scope_config=config)
        key = cache._make_programmatic_key("my_key", "user", {"user_id": "123"})
        self.assertIn("user:123", key.scope_prefix)


class TestCacheScopeParams(unittest.TestCase):
    def test_with_scope_params(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        cache = Cache(scope_config=config)

        cache.set("key1", "value1", 10, scope="user", user_id="123")
        result = cache.get("key1", scope="user", user_id="123")
        self.assertEqual(result, "value1")

    def test_scope_isolation(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        cache = Cache(scope_config=config)

        cache.set("key1", "value1", 10, scope="user", user_id="123")
        result = cache.get("key1", scope="user", user_id="456")
        self.assertIsNone(result)

    def test_evict_by_scope_with_params(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        cache = Cache(scope_config=config)

        cache.set("key1", "value1", 10, scope="user", user_id="123")
        cache.set("key2", "value2", 10, scope="user", user_id="123")
        count = cache.evict_by_scope("user", user_id="123")
        self.assertEqual(count, 2)

    def test_scope_params_dict(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        cache = Cache(scope_config=config)

        cache.set("key1", "value1", 10, scope="user", scope_params={"user_id": "123"})
        result = cache.get("key1", scope="user", scope_params={"user_id": "123"})
        self.assertEqual(result, "value1")


class TestCacheTTL(unittest.TestCase):
    def test_expiration(self):
        storage = InMemory()
        rule = LifeTimeEvict()
        cache = Cache(storage_provider=storage, storage_rules=[rule])

        cache.set("key1", "value1", 0.01)
        time.sleep(0.05)
        cache.get("key1")
        result = cache.get("key1")
        self.assertIsNone(result)

    def test_not_expired(self):
        storage = InMemory()
        rule = LifeTimeEvict()
        cache = Cache(storage_provider=storage, storage_rules=[rule])

        cache.set("key1", "value1", 10)
        result = cache.get("key1")
        self.assertEqual(result, "value1")

    def test_zero_ttl(self):
        cache = Cache()
        cache.set("key1", "value1", 0)
        result = cache.get("key1")
        self.assertIsNone(result)

    def test_negative_ttl(self):
        cache = Cache()
        cache.set("key1", "value1", -1)
        result = cache.get("key1")
        self.assertIsNone(result)


class TestCacheWithMocks(unittest.TestCase):
    def test_storage_get_called(self):
        mock_storage = MagicMock(spec=InMemory)
        mock_storage.get.return_value = ("value1", 100.0)
        mock_storage.get_stats.return_value = {"storage_type": "mock"}

        cache = Cache(storage_provider=mock_storage)
        cache.get("key1")

        mock_storage.get.assert_called_once()

    def test_storage_set_called(self):
        mock_storage = MagicMock(spec=InMemory)
        mock_storage.get_stats.return_value = {"storage_type": "mock"}

        cache = Cache(storage_provider=mock_storage)
        cache.set("key1", "value1", 10)

        mock_storage.set.assert_called_once()

    def test_storage_evict_called(self):
        mock_storage = MagicMock(spec=InMemory)
        mock_storage.get_stats.return_value = {"storage_type": "mock"}

        cache = Cache(storage_provider=mock_storage)
        cache.evict("key1")

        mock_storage.evict.assert_called_once()

    def test_storage_clear_called(self):
        mock_storage = MagicMock(spec=InMemory)
        mock_storage.get_stats.return_value = {"storage_type": "mock"}

        cache = Cache(storage_provider=mock_storage)
        cache.clear()

        mock_storage.clear.assert_called_once()


class TestCacheWithAsyncMocks(IsolatedAsyncioTestCase):
    async def test_aget_with_async_mock(self):
        mock_storage = MagicMock(spec=InMemory)
        mock_storage.get.return_value = ("value1", 100.0)
        mock_storage.get_stats.return_value = {"storage_type": "mock"}

        cache = Cache(storage_provider=mock_storage)
        result = await cache.aget("key1")

        self.assertEqual(result, "value1")

    async def test_aset_with_async_mock(self):
        mock_storage = MagicMock(spec=InMemory)
        mock_storage.get_stats.return_value = {"storage_type": "mock"}

        cache = Cache(storage_provider=mock_storage)
        await cache.aset("key1", "value1", 10)

        mock_storage.set.assert_called_once()
