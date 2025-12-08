from typing import Any, Tuple, Union


class CacheKey:
    """Encapsulates cache key components and generates a composite string key.

    This class is responsible for standardizing how cache keys are built, ensuring
    consistency across the application. It combines scope, namespace, and argument
    hashes into a single string format (scope::namespace::hash).

    Attributes:
        scope_prefix (str): The resolved scope path.
        namespace (str): The logical namespace, typically the function name.
        args_hash (int): The hash integer derived from the function arguments.
    """

    __slots__ = ("scope_prefix", "namespace", "args_hash")

    def __init__(self, scope_prefix: str, namespace: str, args_key: Tuple[Any, ...]) -> None:
        """Initializes a new CacheKey instance.

        Args:
            scope_prefix (str): The calculated scope string (e.g., 'tenant:1').
            namespace (str): The identifier for the cached item (usually function name).
            args_key (Tuple[Any, ...]): A tuple containing the raw arguments to be hashed.
                This tuple must contain hashable items.
        """
        self.scope_prefix = scope_prefix
        self.namespace = namespace
        self.args_hash = hash(args_key)

    def as_string(self) -> str:
        """Serializes the key components into a string format.

        The format used is 'scope_prefix::namespace::args_hash'.

        Returns:
            str: The composite string key ready for storage backends (e.g., Redis).
        """
        return f"{self.scope_prefix}::{self.namespace}::{self.args_hash}"

    @staticmethod
    def from_string(key_str: str) -> "CacheKey":
        """Deserializes a string key back into a CacheKey object.

        This method bypasses the standard __init__ because we are reconstructing
        the object from an existing hash, rather than calculating a new hash
        from raw arguments.

        Args:
            key_str (str): The composite string key (format: 'scope::ns::hash').

        Raises:
            ValueError: If the key string does not match the expected '::' delimited format.

        Returns:
            CacheKey: A new instance of CacheKey populated with the parsed data.
        """
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
        """Extracts the namespace component from a raw key string.

        Args:
            key_str (str): The composite string key.

        Returns:
            str: The namespace part, or an empty string if parsing fails.
        """
        parts = key_str.split("::")
        return parts[1] if len(parts) >= 2 else ""

    @staticmethod
    def extract_scope_prefix(key_str: str) -> str:
        """Extracts the scope prefix component from a raw key string.

        Args:
            key_str (str): The composite string key.

        Returns:
            str: The scope prefix part, or an empty string if parsing fails.
        """
        parts = key_str.split("::")
        return parts[0] if len(parts) >= 1 else ""

    @staticmethod
    def extract_args_hash(key_str: str) -> int:
        """Extracts the argument hash component from a raw key string.

        Args:
            key_str (str): The composite string key.

        Returns:
            int: The hash integer, or 0 if parsing fails.
        """
        parts = key_str.split("::")
        return int(parts[2]) if len(parts) >= 3 else 0

    def __str__(self) -> str:
        """Returns the string representation of the cache key.

        Returns:
            str: The composite key string (same as as_string).
        """
        return self.as_string()

    def __repr__(self) -> str:
        """Returns a developer-friendly string representation.

        Returns:
            str: A string showing the internal state of the CacheKey.
        """
        return f"CacheKey(scope={self.scope_prefix}, ns={self.namespace}, hash={self.args_hash})"

    def __eq__(self, other_object: Any) -> bool:
        """Checks equality based on the composite string representation.

        Args:
            other (Any): The object to compare against.

        Returns:
            bool: True if both objects produce the same cache key string.
        """
        if isinstance(other_object, CacheKey):
            return self.as_string() == other_object.as_string()
        return False

    def __hash__(self) -> int:
        """Calculates the hash of the CacheKey object itself.

        This allows CacheKey instances to be used as keys in dictionaries or sets.

        Returns:
            int: The hash of the composite key string.
        """
        return hash(self.as_string())


_CacheValue = Tuple[Any, float]
_CacheScope = Union[str, Tuple[str, ...]]
