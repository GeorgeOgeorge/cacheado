"""
Hierarchical Multi-Tenant Cache System

An advanced Python cache system with support for scope hierarchies,
thread-safe operations, and cache stampede protection.

Storages are fully responsible for their own eviction policies and TTL management.
"""

from .cache import Cache
from .storages.in_memory import InMemory
from .utils.cache_scope_config import ScopeConfig, ScopeLevel
from .utils.cache_types import CacheKey, _CacheScope, _CacheValue

__version__ = "2.0.0"

__all__ = [
    "Cache",
    "create_cache",
    "InMemory",
    "ScopeConfig",
    "ScopeLevel",
    "CacheKey",
    "_CacheValue",
    "_CacheScope",
]
