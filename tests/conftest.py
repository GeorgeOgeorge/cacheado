import pytest

from cache import create_cache
from cache_policies.cache_policy_manager import CachePolicyManager
from cache_scopes.scope_config import ScopeConfig, ScopeLevel
from eviction_policies.lre_eviction import LRUEvictionPolicy
from storages.in_memory import InMemory


@pytest.fixture
def scope_config():
    """Basic scope configuration for tests."""
    return ScopeConfig(
        [
            ScopeLevel("organization", "org_id", [ScopeLevel("user", "user_id", [ScopeLevel("session", "session_id")])]),
            ScopeLevel("tenant", "tenant_id", [ScopeLevel("project", "project_id")]),
        ]
    )


@pytest.fixture
def storage():
    """In-memory storage provider."""
    return InMemory()


@pytest.fixture
def eviction_policy():
    """LRU eviction policy."""
    return LRUEvictionPolicy()


@pytest.fixture
def policy_manager(eviction_policy):
    """Cache policy manager."""
    return CachePolicyManager(cleanup_interval=1, policy=eviction_policy, max_size=100)


@pytest.fixture
def cache(storage, policy_manager, scope_config):
    """Configured cache instance."""
    return create_cache(backend=storage, policy_manager=policy_manager, scope_config=scope_config)
