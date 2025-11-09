import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cache_scopes.scope_config import ScopeConfig, ScopeLevel


class TestScopeLevel:
    """Test cases for ScopeLevel dataclass."""

    def test_basic_creation(self):
        """Test basic ScopeLevel creation."""
        level = ScopeLevel("organization", "org_id")
        
        assert level.name == "organization"
        assert level.param_name == "org_id"
        assert level.children == []

    def test_creation_with_children(self):
        """Test ScopeLevel creation with children."""
        child = ScopeLevel("user", "user_id")
        parent = ScopeLevel("organization", "org_id", [child])
        
        assert parent.name == "organization"
        assert parent.param_name == "org_id"
        assert len(parent.children) == 1
        assert parent.children[0] is child

    def test_empty_name_validation(self):
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            ScopeLevel("", "param")

    def test_none_children_default(self):
        """Test that None children defaults to empty list."""
        level = ScopeLevel("test", "param", None)
        assert level.children == []


class TestScopeConfig:
    """Test cases for ScopeConfig class."""

    def test_initialization_empty(self):
        """Test ScopeConfig initialization with no levels."""
        config = ScopeConfig()
        
        assert len(config.root_levels) == 1  # Global level
        assert config.root_levels[0].name == "global"

    def test_initialization_with_levels(self):
        """Test ScopeConfig initialization with levels."""
        org_level = ScopeLevel("organization", "org_id")
        config = ScopeConfig([org_level])
        
        root_levels = config.root_levels
        assert len(root_levels) == 1
        assert root_levels[0].name == "global"
        assert len(root_levels[0].children) == 1
        assert root_levels[0].children[0] is org_level

    def test_duplicate_level_names(self):
        """Test that duplicate level names raise ValueError."""
        level1 = ScopeLevel("duplicate", "param1")
        level2 = ScopeLevel("duplicate", "param2")
        
        with pytest.raises(ValueError, match="Scope level names must be unique"):
            ScopeConfig([level1, level2])

    def test_flatten_levels(self):
        """Test level flattening."""
        user_level = ScopeLevel("user", "user_id")
        org_level = ScopeLevel("organization", "org_id", [user_level])
        config = ScopeConfig([org_level])
        
        all_levels = config.all_levels
        level_names = [level.name for level in all_levels]
        
        assert "global" in level_names
        assert "organization" in level_names
        assert "user" in level_names

    def test_get_param_name(self):
        """Test getting parameter name for level."""
        org_level = ScopeLevel("organization", "org_id")
        config = ScopeConfig([org_level])
        
        assert config.get_param_name("organization") == "org_id"
        assert config.get_param_name("global") == ""

    def test_get_param_name_unknown_level(self):
        """Test getting parameter name for unknown level."""
        config = ScopeConfig()
        
        with pytest.raises(ValueError, match="Unknown scope level: unknown"):
            config.get_param_name("unknown")

    def test_build_scope_path_global(self):
        """Test building global scope path."""
        config = ScopeConfig()
        
        path = config.build_scope_path({})
        assert path == "global"

    def test_build_scope_path_single_level(self):
        """Test building single level scope path."""
        org_level = ScopeLevel("organization", "org_id")
        config = ScopeConfig([org_level])
        
        path = config.build_scope_path({"org_id": "org_123"})
        assert path == "organization:org_123"

    def test_build_scope_path_nested_levels(self):
        """Test building nested scope path."""
        user_level = ScopeLevel("user", "user_id")
        org_level = ScopeLevel("organization", "org_id", [user_level])
        config = ScopeConfig([org_level])
        
        path = config.build_scope_path({
            "org_id": "org_123",
            "user_id": "user_456"
        })
        assert path == "organization:org_123/user:user_456"

    def test_build_scope_path_partial_params(self):
        """Test building scope path with partial parameters."""
        user_level = ScopeLevel("user", "user_id")
        org_level = ScopeLevel("organization", "org_id", [user_level])
        config = ScopeConfig([org_level])
        
        # Only org_id provided
        path = config.build_scope_path({"org_id": "org_123"})
        assert path == "organization:org_123"

    def test_validate_scope_params_global(self):
        """Test validating global scope parameters."""
        config = ScopeConfig()
        
        # Should not raise exception
        config.validate_scope_params("global", {})

    def test_validate_scope_params_valid(self):
        """Test validating valid scope parameters."""
        org_level = ScopeLevel("organization", "org_id")
        config = ScopeConfig([org_level])
        
        # Should not raise exception
        config.validate_scope_params("organization", {"org_id": "org_123"})

    def test_validate_scope_params_missing_required(self):
        """Test validating scope parameters with missing required param."""
        org_level = ScopeLevel("organization", "org_id")
        config = ScopeConfig([org_level])
        
        with pytest.raises(ValueError, match="Missing required parameter 'org_id'"):
            config.validate_scope_params("organization", {})

    def test_validate_scope_params_unknown_level(self):
        """Test validating parameters for unknown scope level."""
        config = ScopeConfig()
        
        with pytest.raises(ValueError, match="Unknown scope level: unknown"):
            config.validate_scope_params("unknown", {})

    def test_validate_scope_params_nested(self):
        """Test validating nested scope parameters."""
        user_level = ScopeLevel("user", "user_id")
        org_level = ScopeLevel("organization", "org_id", [user_level])
        config = ScopeConfig([org_level])
        
        # Valid nested params
        config.validate_scope_params("user", {
            "org_id": "org_123",
            "user_id": "user_456"
        })
        
        # Missing parent param
        with pytest.raises(ValueError, match="Missing required parameter 'org_id'"):
            config.validate_scope_params("user", {"user_id": "user_456"})

    def test_get_parent_scope_path(self):
        """Test getting parent scope path."""
        config = ScopeConfig()
        
        assert config.get_parent_scope_path("global") is None
        assert config.get_parent_scope_path("organization:org_123") == "global"
        assert config.get_parent_scope_path("organization:org_123/user:user_456") == "organization:org_123"

    def test_is_descendant_of(self):
        """Test checking if scope is descendant of another."""
        config = ScopeConfig()
        
        # Global is parent of everything
        assert config.is_descendant_of("organization:org_123", "global")
        assert config.is_descendant_of("organization:org_123/user:user_456", "global")
        
        # Direct parent-child relationship
        assert config.is_descendant_of("organization:org_123/user:user_456", "organization:org_123")
        
        # Same scope
        assert config.is_descendant_of("organization:org_123", "organization:org_123")
        
        # Not descendant
        assert not config.is_descendant_of("global", "organization:org_123")
        assert not config.is_descendant_of("organization:org_456", "organization:org_123")

    def test_multiple_root_trees(self):
        """Test configuration with multiple root trees."""
        org_tree = ScopeLevel("organization", "org_id", [
            ScopeLevel("user", "user_id")
        ])
        tenant_tree = ScopeLevel("tenant", "tenant_id", [
            ScopeLevel("project", "project_id")
        ])
        
        config = ScopeConfig([org_tree, tenant_tree])
        
        # Test org tree
        org_path = config.build_scope_path({
            "org_id": "org_123",
            "user_id": "user_456"
        })
        assert org_path == "organization:org_123/user:user_456"
        
        # Test tenant tree
        tenant_path = config.build_scope_path({
            "tenant_id": "tenant_123",
            "project_id": "proj_456"
        })
        assert tenant_path == "tenant:tenant_123/project:proj_456"

    def test_get_scope_tree_for_level(self):
        """Test getting scope tree for specific level."""
        user_level = ScopeLevel("user", "user_id")
        org_level = ScopeLevel("organization", "org_id", [user_level])
        tenant_level = ScopeLevel("tenant", "tenant_id")
        
        config = ScopeConfig([org_level, tenant_level])
        
        # Find tree containing user level
        tree = config.get_scope_tree_for_level("user")
        assert tree is not None
        assert tree.name == "global"
        
        # Find tree containing tenant level
        tree = config.get_scope_tree_for_level("tenant")
        assert tree is not None
        assert tree.name == "global"
        
        # Non-existent level
        tree = config.get_scope_tree_for_level("nonexistent")
        assert tree is None

    def test_level_exists_in_tree(self):
        """Test checking if level exists in tree."""
        user_level = ScopeLevel("user", "user_id")
        org_level = ScopeLevel("organization", "org_id", [user_level])
        config = ScopeConfig([org_level])
        
        # Test with global root
        global_root = config.root_levels[0]
        assert config._level_exists_in_tree(global_root, "global")
        assert config._level_exists_in_tree(global_root, "organization")
        assert config._level_exists_in_tree(global_root, "user")
        assert not config._level_exists_in_tree(global_root, "nonexistent")

    def test_complex_hierarchy(self):
        """Test complex multi-level hierarchy."""
        session_level = ScopeLevel("session", "session_id")
        user_level = ScopeLevel("user", "user_id", [session_level])
        org_level = ScopeLevel("organization", "org_id", [user_level])
        
        config = ScopeConfig([org_level])
        
        # Test full path
        path = config.build_scope_path({
            "org_id": "org_123",
            "user_id": "user_456",
            "session_id": "sess_789"
        })
        assert path == "organization:org_123/user:user_456/session:sess_789"
        
        # Test validation
        config.validate_scope_params("session", {
            "org_id": "org_123",
            "user_id": "user_456",
            "session_id": "sess_789"
        })
        
        # Test missing intermediate param
        with pytest.raises(ValueError, match="Missing required parameter 'user_id'"):
            config.validate_scope_params("session", {
                "org_id": "org_123",
                "session_id": "sess_789"
            })

    def test_empty_param_name(self):
        """Test level with empty parameter name."""
        level = ScopeLevel("global", "")
        config = ScopeConfig([level])
        
        # Should work with empty param name
        path = config.build_scope_path({})
        assert path == "global"

    def test_property_accessors(self):
        """Test property accessor methods."""
        org_level = ScopeLevel("organization", "org_id")
        config = ScopeConfig([org_level])
        
        # Test that properties return copies
        root_levels = config.root_levels
        all_levels = config.all_levels
        level_names = config.level_names
        
        # Modify returned lists
        root_levels.clear()
        all_levels.clear()
        level_names.clear()
        
        # Original should be unchanged
        assert len(config.root_levels) > 0
        assert len(config.all_levels) > 0
        assert len(config.level_names) > 0