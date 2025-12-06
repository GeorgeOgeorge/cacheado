import pytest

from cache import create_cache
from cache_scope_config import ScopeConfig, ScopeLevel
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
def cache(storage, scope_config):
    """Configured cache instance."""
    return create_cache(backend=storage, scope_config=scope_config)
