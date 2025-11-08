from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from protocols.scope_config import IScopeConfig


@dataclass
class ScopeLevel:
    """Representa um nível na hierarquia de escopo."""
    name: str
    param_name: str
    children: Optional[List['ScopeLevel']] = None
    
    def __post_init__(self):
        if not self.name:
            raise ValueError("name cannot be empty")
        if self.children is None:
            self.children = []


class ScopeConfig(IScopeConfig):
    """
    Configuração de escopo hierárquico para cache com suporte a múltiplas árvores.
    
    Exemplo:
        # Múltiplas árvores independentes
        org_tree = ScopeLevel("organization", "org_id", [
            ScopeLevel("user", "user_id")
        ])
        car_tree = ScopeLevel("car", "car_id", [
            ScopeLevel("door", "door_id", [
                ScopeLevel("tire", "tire_id")
            ])
        ])
        config = ScopeConfig([org_tree, car_tree])
    """
    
    def __init__(self, root_levels: Optional[List[ScopeLevel]] = None):
        """
        Inicializa a configuração de escopo com global como root implícito.
        
        Args:
            root_levels: Lista de níveis filhos do global (opcional).
        """
        # Global sempre existe como root implícito
        global_level = ScopeLevel("global", "", root_levels or [])
        
        self._root_levels = [global_level]
        self._all_levels = self._flatten_levels(self._root_levels)
        self._level_names = [level.name for level in self._all_levels]
        self._param_mapping = {level.name: level.param_name for level in self._all_levels}
        
        # Validar nomes únicos (exceto global que sempre existe)
        if len(set(self._level_names)) != len(self._level_names):
            raise ValueError("Scope level names must be unique")
    
    def _flatten_levels(self, levels: List[ScopeLevel]) -> List[ScopeLevel]:
        """Achata a árvore de níveis em uma lista."""
        result = []
        for level in levels:
            result.append(level)
            if level.children:
                result.extend(self._flatten_levels(level.children))
        return result
    
    @property
    def root_levels(self) -> List[ScopeLevel]:
        """Retorna os níveis raiz de escopo configurados."""
        return self._root_levels.copy()
    
    @property
    def all_levels(self) -> List[ScopeLevel]:
        """Retorna todos os níveis de escopo (achatados)."""
        return self._all_levels.copy()
    
    @property
    def level_names(self) -> List[str]:
        """Retorna os nomes dos níveis de escopo."""
        return self._level_names.copy()
    
    def get_param_name(self, level_name: str) -> str:
        """
        Retorna o nome do parâmetro para um nível específico.
        
        Args:
            level_name: Nome do nível de escopo.
            
        Returns:
            Nome do parâmetro correspondente.
            
        Raises:
            ValueError: Se o nível não existir.
        """
        if level_name not in self._param_mapping:
            raise ValueError(f"Unknown scope level: {level_name}")
        return self._param_mapping[level_name]
    
    def build_scope_path(self, scope_params: Dict[str, Any]) -> str:
        """
        Constrói o caminho do escopo baseado nos parâmetros fornecidos.
        
        Args:
            scope_params: Dicionário com os parâmetros de escopo.
            
        Returns:
            String representando o caminho hierárquico do escopo.
        """
        def build_path_recursive(levels: List[ScopeLevel], path_parts: List[str]) -> List[str]:
            for level in levels:
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
        Valida se os parâmetros necessários estão presentes para o nível alvo.
        
        Args:
            target_level: Nível de escopo desejado.
            scope_params: Parâmetros fornecidos.
            
        Raises:
            ValueError: Se parâmetros obrigatórios estiverem ausentes.
        """
        if target_level == "global":
            return
        
        if target_level not in self._level_names:
            raise ValueError(f"Unknown scope level: {target_level}")
        
        # Encontrar o caminho até o nível alvo
        path_to_target = self._find_path_to_level(target_level)
        if not path_to_target:
            raise ValueError(f"Cannot find path to scope level: {target_level}")
        
        # Validar que todos os níveis no caminho têm parâmetros
        for level in path_to_target:
            if level.param_name and (level.param_name not in scope_params or scope_params[level.param_name] is None):
                raise ValueError(f"Missing required parameter '{level.param_name}' for scope level '{level.name}'")
    
    def _find_path_to_level(self, target_level: str) -> Optional[List[ScopeLevel]]:
        """Encontra o caminho hierárquico até um nível específico."""
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
        Retorna o caminho do escopo pai.
        
        Args:
            scope_path: Caminho do escopo atual.
            
        Returns:
            Caminho do escopo pai ou None se for global.
        """
        if scope_path == "global":
            return None
        
        parts = scope_path.split("/")
        if len(parts) <= 1:
            return "global"
        
        return "/".join(parts[:-1])
    
    def is_descendant_of(self, child_path: str, parent_path: str) -> bool:
        """
        Verifica se um escopo é descendente de outro.
        
        Args:
            child_path: Caminho do escopo filho.
            parent_path: Caminho do escopo pai.
            
        Returns:
            True se child_path é descendente de parent_path.
        """
        if parent_path == "global":
            return True
        
        if child_path == "global":
            return False
        
        return child_path.startswith(parent_path + "/") or child_path == parent_path
    
    def get_scope_tree_for_level(self, level_name: str) -> Optional[ScopeLevel]:
        """Retorna a árvore raiz que contém o nível especificado."""
        def find_root(levels: List[ScopeLevel], target: str) -> Optional[ScopeLevel]:
            for root in levels:
                if self._level_exists_in_tree(root, target):
                    return root
            return None
        
        return find_root(self._root_levels, level_name)
    
    def _level_exists_in_tree(self, root: ScopeLevel, target: str) -> bool:
        """Verifica se um nível existe na árvore."""
        if root.name == target:
            return True
        if root.children:
            return any(self._level_exists_in_tree(child, target) for child in root.children)
        return False


