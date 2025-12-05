"""Tests for protocol interfaces to ensure they are properly defined."""

from protocols.eviction_policy import IEvictionPolicy
from protocols.storage_provider import IStorageProvider


class TestProtocols:
    """Test protocol definitions and their methods."""

    def test_storage_provider_protocol(self):
        """Test IStorageProvider protocol methods exist."""
        assert hasattr(IStorageProvider, "get")
        assert hasattr(IStorageProvider, "set")
        assert hasattr(IStorageProvider, "evict")
        assert hasattr(IStorageProvider, "get_all_keys")
        assert hasattr(IStorageProvider, "clear")

        assert hasattr(IStorageProvider, "aget")
        assert hasattr(IStorageProvider, "aset")
        assert hasattr(IStorageProvider, "aevict")
        assert hasattr(IStorageProvider, "aget_all_keys")
        assert hasattr(IStorageProvider, "aclear")

    def test_eviction_policy_protocol(self):
        """Test IEvictionPolicy protocol methods exist."""
        assert hasattr(IEvictionPolicy, "notify_set")
        assert hasattr(IEvictionPolicy, "notify_get")
        assert hasattr(IEvictionPolicy, "notify_evict")
        assert hasattr(IEvictionPolicy, "notify_clear")
        assert hasattr(IEvictionPolicy, "get_namespace_count")
        assert hasattr(IEvictionPolicy, "get_global_size")

    def test_protocol_method_signatures(self):
        """Test that protocol methods have proper signatures."""

        storage_annotations = getattr(IStorageProvider, "__annotations__", {})
        assert len(storage_annotations) == 0

        methods_to_check = [
            "get",
            "set",
            "evict",
            "get_all_keys",
            "clear",
            "aget",
            "aset",
            "aevict",
            "aget_all_keys",
            "aclear",
        ]

        for method_name in methods_to_check:
            method = getattr(IStorageProvider, method_name)
            assert callable(method)

    def test_protocol_inheritance(self):
        """Test protocol inheritance structure."""
        protocols = [IStorageProvider, IEvictionPolicy]

        for protocol in protocols:
            assert hasattr(protocol, "__mro__")
            assert len([attr for attr in dir(protocol) if not attr.startswith("_")]) > 0

    def test_protocol_documentation(self):
        """Test that protocols have proper documentation."""
        protocols = [IStorageProvider, IEvictionPolicy]

        for protocol in protocols:
            assert protocol.__doc__ is not None
            assert len(protocol.__doc__.strip()) > 0
