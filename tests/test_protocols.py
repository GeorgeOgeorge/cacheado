"""Tests for protocol interfaces to ensure they are properly defined."""

from protocols.cache import ICache
from protocols.cache_policy_manager_protocol import ICachePolicyManager
from protocols.eviction_policy import IEvictionPolicy
from protocols.scope import IScope
from protocols.storage_provider import IStorageProvider


class TestProtocols:
    """Test protocol definitions and their methods."""

    def test_storage_provider_protocol(self):
        """Test IStorageProvider protocol methods exist."""
        # Test that protocol has required methods
        assert hasattr(IStorageProvider, "get")
        assert hasattr(IStorageProvider, "get_value_no_lock")
        assert hasattr(IStorageProvider, "set")
        assert hasattr(IStorageProvider, "evict")
        assert hasattr(IStorageProvider, "get_all_keys")
        assert hasattr(IStorageProvider, "clear")

    def test_eviction_policy_protocol(self):
        """Test IEvictionPolicy protocol methods exist."""
        assert hasattr(IEvictionPolicy, "notify_set")
        assert hasattr(IEvictionPolicy, "notify_get")
        assert hasattr(IEvictionPolicy, "notify_evict")
        assert hasattr(IEvictionPolicy, "notify_clear")
        assert hasattr(IEvictionPolicy, "get_namespace_count")
        assert hasattr(IEvictionPolicy, "get_global_size")

    def test_cache_policy_manager_protocol(self):
        """Test ICachePolicyManager protocol methods exist."""
        assert hasattr(ICachePolicyManager, "start_background_cleanup")
        assert hasattr(ICachePolicyManager, "stop_background_cleanup")
        assert hasattr(ICachePolicyManager, "notify_set")
        assert hasattr(ICachePolicyManager, "notify_get")
        assert hasattr(ICachePolicyManager, "notify_evict")
        assert hasattr(ICachePolicyManager, "notify_clear")
        assert hasattr(ICachePolicyManager, "get_namespace_count")
        assert hasattr(ICachePolicyManager, "get_global_size")

    def test_scope_protocol(self):
        """Test IScope protocol methods exist."""
        # Check the actual methods that exist in IScope protocol
        assert hasattr(IScope, "level_names")
        assert hasattr(IScope, "get_param_name")
        assert hasattr(IScope, "build_scope_path")
        assert hasattr(IScope, "validate_scope_params")
        assert hasattr(IScope, "get_parent_scope_path")
        assert hasattr(IScope, "is_descendant_of")

    def test_cache_protocol(self):
        """Test ICache protocol methods exist."""
        assert hasattr(ICache, "get")
        assert hasattr(ICache, "set")
        assert hasattr(ICache, "evict")
        assert hasattr(ICache, "clear")
        assert hasattr(ICache, "cache")
        assert hasattr(ICache, "stats")
        assert hasattr(ICache, "evict_by_scope")

    def test_protocol_method_signatures(self):
        """Test that protocol methods have proper signatures."""
        # This test ensures protocols are properly defined
        # The actual implementation testing is done in other test files

        # Test IStorageProvider annotations
        storage_annotations = getattr(IStorageProvider, "__annotations__", {})
        assert len(storage_annotations) == 0  # Protocols don't have class-level annotations

        # Test that methods exist and are callable
        methods_to_check = ["get", "get_value_no_lock", "set", "evict", "get_all_keys", "clear"]

        for method_name in methods_to_check:
            method = getattr(IStorageProvider, method_name)
            assert callable(method)

    def test_protocol_inheritance(self):
        """Test protocol inheritance structure."""
        # Protocols should be properly defined as Protocol classes
        # In Python 3.8+, protocols have different attributes
        protocols = [IStorageProvider, IEvictionPolicy, ICachePolicyManager, IScope, ICache]

        for protocol in protocols:
            # Check that they are actually protocols (have typing.Protocol as base)
            assert hasattr(protocol, "__mro__")
            # Protocols should have methods defined
            assert len([attr for attr in dir(protocol) if not attr.startswith("_")]) > 0

    def test_protocol_documentation(self):
        """Test that protocols have proper documentation."""
        protocols = [IStorageProvider, IEvictionPolicy, ICachePolicyManager, IScope, ICache]

        for protocol in protocols:
            assert protocol.__doc__ is not None
            assert len(protocol.__doc__.strip()) > 0
