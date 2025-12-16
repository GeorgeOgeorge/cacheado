import unittest

from utils.cache_scope_config import ScopeConfig, ScopeLevel


class TestScopeLevel(unittest.TestCase):
    def test_creation(self):
        level = ScopeLevel("user", "user_id")
        self.assertEqual(level.name, "user")
        self.assertEqual(level.param_name, "user_id")

    def test_empty_name(self):
        with self.assertRaises(ValueError):
            ScopeLevel("", "param")


class TestScopeConfig(unittest.TestCase):
    def test_default(self):
        config = ScopeConfig()
        self.assertIn("global", config.level_names)

    def test_build_scope_path_global(self):
        config = ScopeConfig()
        path = config.build_scope_path({})
        self.assertEqual(path, "global")

    def test_build_scope_path_with_params(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        path = config.build_scope_path({"user_id": "123"})
        self.assertEqual(path, "user:123")

    def test_validate_scope_params_global(self):
        config = ScopeConfig()
        config.validate_scope_params("global", {})

    def test_validate_scope_params_missing(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        with self.assertRaises(ValueError):
            config.validate_scope_params("user", {})

    def test_get_param_name(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        self.assertEqual(config.get_param_name("user"), "user_id")

    def test_get_param_name_unknown(self):
        config = ScopeConfig()
        with self.assertRaises(ValueError):
            config.get_param_name("unknown")

    def test_get_parent_scope_path(self):
        config = ScopeConfig()
        self.assertIsNone(config.get_parent_scope_path("global"))
        self.assertEqual(config.get_parent_scope_path("user:123"), "global")

    def test_is_descendant_of(self):
        config = ScopeConfig()
        self.assertTrue(config.is_descendant_of("user:123/tenant:456", "user:123"))
        self.assertTrue(config.is_descendant_of("user:123", "global"))
        self.assertFalse(config.is_descendant_of("global", "user:123"))

    def test_duplicate_level_names(self):
        user_level1 = ScopeLevel("user", "user_id")
        user_level2 = ScopeLevel("user", "other_id")
        with self.assertRaises(ValueError):
            ScopeConfig([user_level1, user_level2])

    def test_root_levels_property(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        roots = config.root_levels
        self.assertIsInstance(roots, list)

    def test_all_levels_property(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        levels = config.all_levels
        self.assertIsInstance(levels, list)

    def test_level_names_property(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        names = config.level_names
        self.assertIn("user", names)

    def test_find_path_to_level_not_found(self):
        config = ScopeConfig()
        path = config._find_path_to_level("nonexistent")
        self.assertIsNone(path)

    def test_get_scope_tree_for_level(self):
        user_level = ScopeLevel("user", "user_id")
        config = ScopeConfig([user_level])
        tree = config.get_scope_tree_for_level("user")
        self.assertIsNotNone(tree)

    def test_get_scope_tree_for_level_not_found(self):
        config = ScopeConfig()
        tree = config.get_scope_tree_for_level("nonexistent")
        self.assertIsNone(tree)

    def test_level_exists_in_tree(self):
        user_level = ScopeLevel("user", "user_id", [ScopeLevel("tenant", "tenant_id")])
        config = ScopeConfig([user_level])
        exists = config._level_exists_in_tree(user_level, "tenant")
        self.assertTrue(exists)

    def test_build_scope_path_nested(self):
        user_level = ScopeLevel("user", "user_id", [ScopeLevel("tenant", "tenant_id")])
        config = ScopeConfig([user_level])
        path = config.build_scope_path({"user_id": "123", "tenant_id": "456"})
        self.assertIn("user:123", path)
        self.assertIn("tenant:456", path)

    def test_validate_scope_params_unknown_level(self):
        config = ScopeConfig()
        with self.assertRaises(ValueError):
            config.validate_scope_params("unknown", {})

    def test_is_descendant_of_same_path(self):
        config = ScopeConfig()
        self.assertTrue(config.is_descendant_of("user:123", "user:123"))

    def test_get_parent_scope_path_single_level(self):
        config = ScopeConfig()
        parent = config.get_parent_scope_path("user:123")
        self.assertEqual(parent, "global")
