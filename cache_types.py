from typing import Any, Callable, Tuple, TypeVar, Union


class CacheKey:
    """Encapsulates cache key components and generates composite string key."""

    __slots__ = ("scope_prefix", "namespace", "args_hash")

    def __init__(self, scope_prefix: str, namespace: str, args_key: Tuple[Any, ...]):
        self.scope_prefix = scope_prefix
        self.namespace = namespace
        self.args_hash = hash(args_key)

    def to_string(self) -> str:
        """Generates composite string key."""
        return f"{self.scope_prefix}::{self.namespace}::{self.args_hash}"

    @staticmethod
    def from_string(key_str: str) -> "CacheKey":
        """Parses composite string key back to CacheKey."""
        parts = key_str.split("::")
        if len(parts) != 3:
            raise ValueError(f"Invalid cache key format: {key_str}")

        cache_key = object.__new__(CacheKey)
        cache_key.scope_prefix = parts[0]
        cache_key.namespace = parts[1]
        cache_key.args_hash = int(parts[2])
        return cache_key

    @staticmethod
    def extract_namespace(key_str: str) -> str:
        """Extracts namespace from cache key string."""
        parts = key_str.split("::")
        return parts[1] if len(parts) >= 2 else ""

    @staticmethod
    def extract_scope_prefix(key_str: str) -> str:
        """Extracts scope prefix from cache key string."""
        parts = key_str.split("::")
        return parts[0] if len(parts) >= 1 else ""

    @staticmethod
    def extract_args_hash(key_str: str) -> int:
        """Extracts args hash from cache key string."""
        parts = key_str.split("::")
        return int(parts[2]) if len(parts) >= 3 else 0

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return f"CacheKey(scope={self.scope_prefix}, ns={self.namespace}, hash={self.args_hash})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, CacheKey):
            return self.to_string() == other.to_string()
        return False

    def __hash__(self) -> int:
        return hash(self.to_string())


_CacheKey = CacheKey
_CacheValue = Tuple[Any, float]
_CacheScope = Union[str, Tuple[str, ...]]
