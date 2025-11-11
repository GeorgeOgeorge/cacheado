"""
Hierarchical Multi-Tenant Cache System

An advanced Python cache system with support for scope hierarchies,
configurable eviction policies, thread-safe operations, and cache stampede protection.
"""

from .cache import Cache, create_cache
from .cache_policies.cache_policy_manager import CachePolicyManager
from .cache_scopes.scope_config import ScopeConfig, ScopeLevel
from .cache_types import _CacheKey, _CacheScope, _CacheValue
from .eviction_policies.lre_eviction import LRUEvictionPolicy
from .storages.in_memory import InMemory

__version__ = "1.3.0"

__all__ = [
    "Cache",
    "create_cache",
    "InMemory",
    "LRUEvictionPolicy",
    "CachePolicyManager",
    "ScopeConfig",
    "ScopeLevel",
    "_CacheKey",
    "_CacheValue",
    "_CacheScope",
]
