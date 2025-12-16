"""
Hierarchical Multi-Tenant Cache System

An advanced Python cache system with support for scope hierarchies,
thread-safe operations, and cache stampede protection.

Storages are fully responsible for their own eviction policies and TTL management.
"""

from .cache import Cache
from .protocols.storage_provider import IStorageProvider
from .protocols.storage_rule import IStorageRule
from .storages.in_memory import InMemory
from .storages.mongodb import MongoDBStorage
from .storages.redis import RedisStorage
from .storages.rule_aware_storage import RuleAwareStorage
from .storages.rules.lifetime_evict import LifeTimeEvict
from .storages.rules.lru_evict import LRUEvict
from .storages.rules.max_items_evict import MaxItemsEvict
from .utils.cache_scope_config import ScopeConfig, ScopeLevel
from .utils.cache_types import CacheKey, RuleSideEffect, StorageRuleAction, _CacheScope, _CacheValue

__version__ = "2.0.0"

__all__ = [
    "Cache",
    "IStorageProvider",
    "IStorageRule",
    "InMemory",
    "MongoDBStorage",
    "RedisStorage",
    "RuleAwareStorage",
    "LifeTimeEvict",
    "LRUEvict",
    "MaxItemsEvict",
    "ScopeConfig",
    "ScopeLevel",
    "CacheKey",
    "RuleSideEffect",
    "StorageRuleAction",
    "_CacheScope",
    "_CacheValue",
]
