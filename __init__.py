"""
Hierarchical Multi-Tenant Cache System

An advanced Python cache system with support for scope hierarchies,
thread-safe operations, and cache stampede protection.

Storages are fully responsible for their own eviction policies and TTL management.
"""

from .cache import Cache, create_cache
from .cache_scopes.scope_config import ScopeConfig, ScopeLevel
from .cache_types import _CacheKey, _CacheScope, _CacheValue
from .storages.in_memory import InMemory
from .storages.memcached_storage import MemcachedStorage
from .storages.mongodb_storage import MongoDBStorage
from .storages.redis_storage import RedisStorage

__version__ = "2.0.0"

__all__ = [
    "Cache",
    "create_cache",
    "InMemory",
    "RedisStorage",
    "MongoDBStorage",
    "MemcachedStorage",
    "ScopeConfig",
    "ScopeLevel",
    "_CacheKey",
    "_CacheValue",
    "_CacheScope",
]
