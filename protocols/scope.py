from typing import Any, Dict, List, Optional, Protocol


class IScope(Protocol):
    """
    Interface (Protocol) for scope configuration implementations.

    Defines the contract for managing hierarchical cache scoping,
    allowing different implementations while maintaining type safety.
    """

    @property
    def level_names(self) -> List[str]:
        """
        Returns the names of all scope levels.

        Returns:
            List of scope level names.
        """
        ...

    def get_param_name(self, level_name: str) -> str:
        """
        Returns the parameter name for a specific scope level.

        Args:
            level_name: Name of the scope level.

        Returns:
            Corresponding parameter name.

        Raises:
            ValueError: If the level doesn't exist.
        """
        ...

    def build_scope_path(self, scope_params: Dict[str, Any]) -> str:
        """
        Builds the scope path based on provided parameters.

        Args:
            scope_params: Dictionary with scope parameters.

        Returns:
            String representing the hierarchical scope path.
        """
        ...

    def validate_scope_params(self, target_level: str, scope_params: Dict[str, Any]) -> None:
        """
        Validates that required parameters are present for the target level.

        Args:
            target_level: Desired scope level.
            scope_params: Provided parameters.

        Raises:
            ValueError: If mandatory parameters are missing.
        """
        ...

    def get_parent_scope_path(self, scope_path: str) -> Optional[str]:
        """
        Returns the parent scope path.

        Args:
            scope_path: Current scope path.

        Returns:
            Parent scope path or None if global.
        """
        ...

    def is_descendant_of(self, child_path: str, parent_path: str) -> bool:
        """
        Checks if one scope is a descendant of another.

        Args:
            child_path: Child scope path.
            parent_path: Parent scope path.

        Returns:
            True if child_path is descendant of parent_path.
        """
        ...
