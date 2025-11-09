import pytest
from typing import get_args, get_origin
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cache_types import _CacheKey, _CacheValue, _FuncT, _CacheScope


class TestCacheTypes:
    """Test cases for cache type definitions."""

    def test_cache_key_type(self):
        """Test _CacheKey type structure."""
        # Valid cache key
        key: _CacheKey = ("global", "namespace", ("arg1", "arg2"))
        
        assert isinstance(key, tuple)
        assert len(key) == 3
        assert isinstance(key[0], str)  # scope path
        assert isinstance(key[1], str)  # namespace
        assert isinstance(key[2], tuple)  # args tuple

    def test_cache_value_type(self):
        """Test _CacheValue type structure."""
        import time
        
        # Valid cache value
        value: _CacheValue = ("cached_data", time.monotonic() + 60)
        
        assert isinstance(value, tuple)
        assert len(value) == 2
        # First element can be any type
        assert isinstance(value[1], float)  # expiry timestamp

    def test_cache_scope_type_string(self):
        """Test _CacheScope type with string."""
        scope: _CacheScope = "global"
        
        assert isinstance(scope, str)

    def test_cache_scope_type_tuple(self):
        """Test _CacheScope type with tuple."""
        scope: _CacheScope = ("organization", "user")
        
        assert isinstance(scope, tuple)
        assert all(isinstance(item, str) for item in scope)

    def test_cache_key_examples(self):
        """Test various _CacheKey examples."""
        # Global cache key
        global_key: _CacheKey = ("global", "function_name", (b"serialized_args",))
        assert global_key[0] == "global"
        
        # Organization cache key
        org_key: _CacheKey = ("organization:org_123", "user_data", ("user_456",))
        assert "organization:org_123" in org_key[0]
        
        # Nested scope key
        nested_key: _CacheKey = ("organization:org_123/user:user_456", "preferences", ())
        assert "user:user_456" in nested_key[0]
        
        # Programmatic key
        prog_key: _CacheKey = ("global", "__programmatic__", ("user_settings",))
        assert prog_key[1] == "__programmatic__"

    def test_cache_value_examples(self):
        """Test various _CacheValue examples."""
        import time
        
        current_time = time.monotonic()
        
        # String value
        string_value: _CacheValue = ("hello world", current_time + 60)
        assert isinstance(string_value[0], str)
        
        # Dictionary value
        dict_value: _CacheValue = ({"key": "value"}, current_time + 60)
        assert isinstance(dict_value[0], dict)
        
        # List value
        list_value: _CacheValue = ([1, 2, 3], current_time + 60)
        assert isinstance(list_value[0], list)
        
        # Complex object value
        class CustomObject:
            def __init__(self, data):
                self.data = data
        
        obj_value: _CacheValue = (CustomObject("test"), current_time + 60)
        assert isinstance(obj_value[0], CustomObject)

    def test_cache_scope_examples(self):
        """Test various _CacheScope examples."""
        # String scopes
        global_scope: _CacheScope = "global"
        org_scope: _CacheScope = "organization"
        user_scope: _CacheScope = "user"
        
        assert isinstance(global_scope, str)
        assert isinstance(org_scope, str)
        assert isinstance(user_scope, str)
        
        # Tuple scopes (scope paths)
        path_scope: _CacheScope = ("organization", "user", "session")
        partial_path: _CacheScope = ("organization", "user")
        
        assert isinstance(path_scope, tuple)
        assert isinstance(partial_path, tuple)

    def test_type_annotations_compatibility(self):
        """Test that type annotations work correctly."""
        def process_cache_key(key: _CacheKey) -> str:
            return f"{key[0]}:{key[1]}"
        
        def process_cache_value(value: _CacheValue) -> tuple:
            return (value[0], value[1])
        
        def process_scope(scope: _CacheScope) -> str:
            if isinstance(scope, str):
                return scope
            return "/".join(scope)
        
        # Test with actual values
        test_key: _CacheKey = ("global", "test", ("arg",))
        test_value: _CacheValue = ("data", 123.45)
        test_scope_str: _CacheScope = "global"
        test_scope_tuple: _CacheScope = ("org", "user")
        
        assert process_cache_key(test_key) == "global:test"
        assert process_cache_value(test_value) == ("data", 123.45)
        assert process_scope(test_scope_str) == "global"
        assert process_scope(test_scope_tuple) == "org/user"

    def test_cache_key_immutability(self):
        """Test that cache keys are immutable (tuples)."""
        key: _CacheKey = ("global", "test", ("arg1", "arg2"))
        
        # Should not be able to modify
        with pytest.raises(TypeError):
            key[0] = "modified"  # type: ignore
        
        with pytest.raises(TypeError):
            key.append("new_item")  # type: ignore

    def test_cache_value_immutability(self):
        """Test that cache value tuples are immutable."""
        value: _CacheValue = ("data", 123.45)
        
        # Should not be able to modify tuple structure
        with pytest.raises(TypeError):
            value[0] = "modified"  # type: ignore
        
        with pytest.raises(TypeError):
            value.append("new_item")  # type: ignore

    def test_nested_tuple_structures(self):
        """Test nested tuple structures in cache keys."""
        # Complex args tuple
        complex_args = (
            ("nested", "tuple"),
            {"key": "value"},
            [1, 2, 3],
            42
        )
        
        key: _CacheKey = ("global", "complex_func", complex_args)
        
        assert len(key[2]) == 4
        assert key[2][0] == ("nested", "tuple")
        assert key[2][1] == {"key": "value"}
        assert key[2][2] == [1, 2, 3]
        assert key[2][3] == 42

    def test_empty_args_tuple(self):
        """Test cache key with empty args tuple."""
        key: _CacheKey = ("global", "no_args_func", ())
        
        assert len(key[2]) == 0
        assert key[2] == ()

    def test_large_cache_key(self):
        """Test cache key with large args tuple."""
        large_args = tuple(f"arg_{i}" for i in range(1000))
        key: _CacheKey = ("global", "large_func", large_args)
        
        assert len(key[2]) == 1000
        assert key[2][0] == "arg_0"
        assert key[2][999] == "arg_999"

    def test_special_characters_in_scope(self):
        """Test scope paths with special characters."""
        # Scope with special characters (should be handled by scope config)
        scope_path = "organization:org-123_test/user:user@domain.com"
        key: _CacheKey = (scope_path, "test_func", ("arg",))
        
        assert key[0] == scope_path
        assert ":" in key[0]
        assert "/" in key[0]
        assert "@" in key[0]

    def test_unicode_in_cache_values(self):
        """Test cache values with unicode content."""
        import time
        
        unicode_value: _CacheValue = ("Hello 世界! 🌍", time.monotonic() + 60)
        
        assert "世界" in unicode_value[0]
        assert "🌍" in unicode_value[0]

    def test_none_values(self):
        """Test handling of None values."""
        import time
        
        # None as cached value
        none_value: _CacheValue = (None, time.monotonic() + 60)
        assert none_value[0] is None
        
        # None in args tuple
        key_with_none: _CacheKey = ("global", "func", (None, "arg2"))
        assert key_with_none[2][0] is None

    def test_boolean_values(self):
        """Test handling of boolean values."""
        import time
        
        # Boolean as cached value
        bool_value: _CacheValue = (True, time.monotonic() + 60)
        assert bool_value[0] is True
        
        false_value: _CacheValue = (False, time.monotonic() + 60)
        assert false_value[0] is False

    def test_numeric_values(self):
        """Test handling of various numeric values."""
        import time
        
        current_time = time.monotonic()
        
        # Integer
        int_value: _CacheValue = (42, current_time + 60)
        assert isinstance(int_value[0], int)
        
        # Float
        float_value: _CacheValue = (3.14159, current_time + 60)
        assert isinstance(float_value[0], float)
        
        # Complex
        complex_value: _CacheValue = (3+4j, current_time + 60)
        assert isinstance(complex_value[0], complex)