from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from protocols.scope import IScope


@dataclass
class ScopeLevel:
    """Represents a level in the scope hierarchy."""

    name: str
    param_name: str
    children: Optional[List["ScopeLevel"]] = None

    def __post_init__(self):
        if not self.name:
            raise ValueError("name cannot be empty")
        if self.children is None:
            self.children = []


class ScopeConfig(IScope):
    """
    Hierarchical scope configuration for cache with multiple tree support.

    Example:
        ``` python
            # Multiple independent trees
            org_tree = ScopeLevel("organization", "org_id", [
                ScopeLevel("user", "user_id")
            ])
            car_tree = ScopeLevel("car", "car_id", [
                ScopeLevel("door", "door_id", [
                    ScopeLevel("tire", "tire_id")
                ])
            ])
            config = ScopeConfig([org_tree, car_tree])
        ```
    """

    __slots__ = ("_root_levels", "_all_levels", "_level_names", "_param_mapping")

    def __init__(self, root_levels: Optional[List[ScopeLevel]] = None):
        """
        Initializes scope configuration with global as implicit root.

        Args:
            root_levels: List of global child levels (optional).
        """
        global_level = ScopeLevel("global", "", root_levels or [])

        self._root_levels = [global_level]
        self._all_levels = self._flatten_levels(self._root_levels)
        self._level_names = [level.name for level in self._all_levels]
        self._param_mapping = {level.name: level.param_name for level in self._all_levels}

        if len(set(self._level_names)) != len(self._level_names):
            raise ValueError("Scope level names must be unique")

    def _flatten_levels(self, levels: List[ScopeLevel]) -> List[ScopeLevel]:
        """Flattens the level tree into a list."""
        result = []
        for level in levels:
            result.append(level)
            if level.children:
                result.extend(self._flatten_levels(level.children))
        return result

    @property
    def root_levels(self) -> List[ScopeLevel]:
        """Returns the configured root scope levels."""
        return self._root_levels.copy()

    @property
    def all_levels(self) -> List[ScopeLevel]:
        """Returns all scope levels (flattened)."""
        return self._all_levels.copy()

    @property
    def level_names(self) -> List[str]:
        """Returns the scope level names."""
        return self._level_names.copy()

    def get_param_name(self, level_name: str) -> str:
        """
        Returns the parameter name for a specific level.

        Args:
            level_name: Name of the scope level.

        Returns:
            Corresponding parameter name.

        Raises:
            ValueError: If the level doesn't exist.
        """
        if level_name not in self._param_mapping:
            raise ValueError(f"Unknown scope level: {level_name}")
        return self._param_mapping[level_name]

    def build_scope_path(self, scope_params: Dict[str, Any]) -> str:
        """
        Builds the scope path based on provided parameters.

        Args:
            scope_params: Dictionary with scope parameters.

        Returns:
            String representing the hierarchical scope path.
        """

        def build_path_recursive(levels: List[ScopeLevel], path_parts: List[str]) -> List[str]:
            for level in levels:
                if level.name == "global":
                    if level.children:
                        return build_path_recursive(level.children, path_parts)
                    return path_parts

                param_value = scope_params.get(level.param_name)
                if param_value is not None:
                    new_path = path_parts + [f"{level.name}:{param_value}"]
                    if level.children:
                        child_path = build_path_recursive(level.children, new_path)
                        if len(child_path) > len(new_path):
                            return child_path
                    return new_path
            return path_parts

        path_parts = build_path_recursive(self._root_levels, [])
        return "/".join(path_parts) if path_parts else "global"

    def validate_scope_params(self, target_level: str, scope_params: Dict[str, Any]) -> None:
        """
        Validates that required parameters are present for the target level.

        Args:
            target_level: Desired scope level.
            scope_params: Provided parameters.

        Raises:
            ValueError: If mandatory parameters are missing.
        """
        if target_level == "global":
            return

        if target_level not in self._level_names:
            raise ValueError(f"Unknown scope level: {target_level}")

        path_to_target = self._find_path_to_level(target_level)
        if not path_to_target:
            raise ValueError(f"Cannot find path to scope level: {target_level}")

        for level in path_to_target:
            if level.param_name and (level.param_name not in scope_params or scope_params[level.param_name] is None):
                raise ValueError(f"Missing required parameter '{level.param_name}' for scope level '{level.name}'")

    def _find_path_to_level(self, target_level: str) -> Optional[List[ScopeLevel]]:
        """Finds the hierarchical path to a specific level."""

        def search_recursive(levels: List[ScopeLevel], path: List[ScopeLevel]) -> Optional[List[ScopeLevel]]:
            for level in levels:
                current_path = path + [level]
                if level.name == target_level:
                    return current_path
                if level.children:
                    result = search_recursive(level.children, current_path)
                    if result:
                        return result
            return None

        return search_recursive(self._root_levels, [])

    def get_parent_scope_path(self, scope_path: str) -> Optional[str]:
        """
        Returns the parent scope path.

        Args:
            scope_path: Current scope path.

        Returns:
            Parent scope path or None if global.
        """
        if scope_path == "global":
            return None

        parts = scope_path.split("/")
        if len(parts) <= 1:
            return "global"

        return "/".join(parts[:-1])

    def is_descendant_of(self, child_path: str, parent_path: str) -> bool:
        """
        Checks if one scope is a descendant of another.

        Args:
            child_path: Child scope path.
            parent_path: Parent scope path.

        Returns:
            True if child_path is descendant of parent_path.
        """
        if parent_path == "global":
            return True

        if child_path == "global":
            return False

        return child_path.startswith(parent_path + "/") or child_path == parent_path

    def get_scope_tree_for_level(self, level_name: str) -> Optional[ScopeLevel]:
        """Returns the root tree that contains the specified level."""

        def find_root(levels: List[ScopeLevel], target: str) -> Optional[ScopeLevel]:
            for root in levels:
                if self._level_exists_in_tree(root, target):
                    return root
            return None

        return find_root(self._root_levels, level_name)

    def _level_exists_in_tree(self, root: ScopeLevel, target: str) -> bool:
        """Checks if a level exists in the tree."""
        if root.name == target:
            return True
        if root.children:
            return any(self._level_exists_in_tree(child, target) for child in root.children)
        return False
