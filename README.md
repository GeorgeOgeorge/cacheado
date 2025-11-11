# Hierarchical Multi-Tenant Cache System

An advanced Python cache system with support for scope hierarchies, configurable eviction policies, thread-safe operations, and cache stampede protection.

## 🎯 Project Concept

This project implements an enterprise cache system that solves common problems in multi-tenant applications:

- **Data isolation** between different organizations/users
- **Intelligent memory management** with eviction policies
- **Cache stampede protection** in concurrent environments
- **Storage flexibility** through pluggable interfaces
- **Observability** with detailed metrics

### Key Features

✅ **Multi-Tenant**: Automatic isolation by organization, user, session, etc.  
✅ **Thread-Safe**: Atomic operations with granular locks  
✅ **Async/Sync**: Complete support for synchronous and asynchronous code  
✅ **Stampede Protection**: Prevents unnecessary recalculations in high concurrency  
✅ **Eviction Policies**: LRU implemented, extensible to LFU, FIFO, etc.  
✅ **Flexible TTL**: Automatic expiration with background cleanup  
✅ **Smart Decorator**: Transparent caching for functions  
✅ **Observability**: Metrics for hits, misses, evictions  

## 🏗️ Architecture

The system follows the **Dependency Injection** pattern with well-defined interfaces:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│     Cache       │────│  PolicyManager   │────│ EvictionPolicy  │
│  (Orchestrator) │    │   (Lifecycle)    │    │     (LRU)       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │
         ▼
┌─────────────────┐    ┌──────────────────┐
│ StorageProvider │    │   ScopeConfig    │
│   (InMemory)    │    │  (Hierarchies)   │
└─────────────────┘    └──────────────────┘
```

### Main Components

#### 1. **Cache (Central Orchestrator)**
- Coordinates all operations
- Manages stampede protection locks
- Maintains statistics (hits/misses/evictions)
- Delegates storage and policies

#### 2. **Storage Providers**
- **InMemory**: In-memory storage with per-key locks
- Extensible interface for Redis, Memcached, etc.

#### 3. **Eviction Policies**
- **LRU**: Least Recently Used implemented
- Interface for LFU, FIFO, TTL-based, etc.

#### 4. **Scope Configuration**
- Flexible hierarchies: `global → org → user → session`
- Multiple independent trees
- Automatic parameter validation

#### 5. **Policy Manager**
- Manages background cleanup
- Coordinates global and per-namespace limits
- Daemon thread for automatic expiration

## 📊 Data Structures

### Fundamental Types

```python
# Internal cache key: (scope_path, namespace, args_hash)
_CacheKey = Tuple[str, str, Tuple[Any, ...]]

# Stored value: (data, expiry_timestamp)
_CacheValue = Tuple[Any, float]

# Scope: string or tuple of levels
_CacheScope = Union[str, Tuple[str, ...]]
```

### Internal Key Examples

```python
# Global cache
("global", "expensive_function", (b"pickled_args...",))

# Organization cache
("organization:org_123", "user_data", (b"pickled_args...",))

# User cache
("organization:org_123/user:user_456", "preferences", (b"pickled_args...",))

# Programmatic cache
("organization:org_123", "__programmatic__", ("user_settings",))
```

### Scope Hierarchy

```python
# Example configuration
scope_config = ScopeConfig([
    ScopeLevel("organization", "org_id", [
        ScopeLevel("user", "user_id", [
            ScopeLevel("session", "session_id")
        ])
    ]),
    ScopeLevel("tenant", "tenant_id", [
        ScopeLevel("project", "project_id")
    ])
])

# Results in paths like:
# "global"
# "organization:123"
# "organization:123/user:456"
# "organization:123/user:456/session:789"
# "tenant:abc/project:xyz"
```

## 🚀 Basic Usage

### Initial Setup

```python
from cache import create_cache
from storages.in_memory import InMemory
from eviction_policies.lre_eviction import LRUEvictionPolicy
from cache_policies.cache_policy_manager import CachePolicyManager
from cache_scopes.scope_config import ScopeConfig, ScopeLevel

# Configure scope hierarchy
scope_config = ScopeConfig([
    ScopeLevel("organization", "org_id", [
        ScopeLevel("user", "user_id")
    ])
])

# Create components
storage = InMemory()
eviction_policy = LRUEvictionPolicy()
policy_manager = CachePolicyManager(
    cache_instance=None,  # Will be set automatically
    cleanup_interval=60,  # Cleanup every 60 seconds
    policy=eviction_policy,
    max_size=10000  # Maximum 10k items globally
)

# Create and configure cache
cache = create_cache(
    backend=storage,
    policy_manager=policy_manager,
    scope_config=scope_config
)
```

### Cache with Decorator

```python
# Simple global cache
@cache.cache(ttl_seconds=300, scope="global")
def expensive_calculation(x, y):
    time.sleep(2)  # Simulate expensive operation
    return x * y + random.random()

# User-scoped cache
@cache.cache(ttl_seconds=600, scope="user", max_items=100)
def get_user_preferences(user_data, organization_id=None, user_id=None):
    # organization_id and user_id are automatically extracted for scope
    return fetch_preferences_from_db(user_data)

# Async cache
@cache.cache(ttl_seconds=180, scope="organization")
async def fetch_org_data(org_slug, organization_id=None):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"/api/orgs/{org_slug}")
        return response.json()
```

### Programmatic Cache

```python
# Synchronous operations
cache.set("user_settings", {"theme": "dark"}, 3600, 
          scope="user", organization_id="org_123", user_id="user_456")

settings = cache.get("user_settings", 
                    scope="user", organization_id="org_123", user_id="user_456")

# Asynchronous operations
await cache.aset("session_data", {"cart": []}, 1800,
                scope="session", organization_id="org_123", 
                user_id="user_456", session_id="sess_789")

data = await cache.aget("session_data",
                       scope="session", organization_id="org_123",
                       user_id="user_456", session_id="sess_789")
```

### Scope-based Eviction

```python
# Remove all data from an organization
evicted_count = cache.evict_by_scope("organization", organization_id="org_123")

# Remove data from a specific user
cache.evict_by_scope("user", organization_id="org_123", user_id="user_456")

# Clear everything
cache.clear()
```

## 📈 Observability

### Available Metrics

```python
stats = cache.stats()
print(stats)
# {
#     "hits": 1250,
#     "misses": 180,
#     "evictions": 45,
#     "current_size": 8934,
#     "tracked_namespaces": 23,
#     "total_calc_locks": 12
# }

# Hit rate
hit_rate = stats["hits"] / (stats["hits"] + stats["misses"])
print(f"Hit Rate: {hit_rate:.2%}")
```

### Structured Logs

```python
import logging
logging.basicConfig(level=logging.INFO)

# The system generates logs for:
# - Cache hits/misses
# - Automatic evictions
# - Background cleanup
# - Serialization errors
# - Configuration operations
```

## 🔧 Advanced Configuration

### Custom Limits

```python
# Global limit
policy_manager = CachePolicyManager(
    cache_instance=cache,
    cleanup_interval=30,
    policy=LRUEvictionPolicy(),
    max_size=50000  # Maximum 50k items
)

# Per-function/namespace limit
@cache.cache(ttl_seconds=300, scope="global", max_items=1000)
def limited_function():
    pass
```

### Multiple Hierarchies

```python
# Support for multiple independent scope trees
scope_config = ScopeConfig([
    # User tree
    ScopeLevel("organization", "org_id", [
        ScopeLevel("user", "user_id", [
            ScopeLevel("session", "session_id")
        ])
    ]),
    # Resource tree
    ScopeLevel("tenant", "tenant_id", [
        ScopeLevel("project", "project_id", [
            ScopeLevel("environment", "env_id")
        ])
    ])
])
```

### Custom Serialization

```python
# The system uses pickle by default, but can be extended
class CustomCache(Cache):
    def _make_args_key(self, *args, **kwargs):
        # Custom implementation for specific types
        try:
            return super()._make_args_key(*args, **kwargs)
        except TypeError:
            # Fallback for non-pickleable types
            return (str(args), str(sorted(kwargs.items())))
```

## 🚀 CI/CD Pipeline

The project includes automated CI/CD pipeline with GitHub Actions for quality assurance and publishing:

### Pipeline Stages

#### 1. **Quality Assurance** (`.github/workflows/quality.yml`)
Runs on every push and pull request:
- **Linting**: Code style validation with flake8
- **Formatting**: Black and isort checks
- **Type Checking**: MyPy static analysis
- **Standards**: Ensures code quality before merge

#### 2. **Automated Publishing** (`.github/workflows/publish.yml`)
Triggered on push/merge to `master` branch:

**Pipeline Steps:**
1. **Test Execution**: Full test suite with coverage
2. **Quality Validation**: Lint, format, and type checks
3. **Version Validation**: Ensures version was bumped
4. **Package Building**: Creates distribution files
5. **Git Tagging**: Automatic version tagging
6. **GitHub Release**: Creates release with notes
7. **PyPI Publishing**: Uploads to Python Package Index

### Version Management

```bash
# Bump version before merge/push
make bump-patch    # 1.0.0 → 1.0.1 (bug fixes)
make bump-minor    # 1.0.0 → 1.1.0 (new features)
make bump-major    # 1.0.0 → 2.0.0 (breaking changes)
```

### Setup Requirements

1. **PyPI API Token**: Add `PYPI_API_TOKEN` to GitHub repository secrets
2. **Version Bump**: Always increment version before merge to master
3. **Quality Gates**: All tests and quality checks must pass

### Manual Publishing

```bash
# Local development workflow
make test-coverage     # Ensure tests pass
make quality-check     # Validate code quality
make bump-patch        # Increment version
make build            # Build package locally
make publish-test     # Test on TestPyPI
make publish          # Publish to PyPI
```

## 🧪 Tests

The project includes a complete test suite:

```bash
# Run all tests
make test

# Specific tests
make test-unit          # Unit tests only
make test-integration   # Integration tests
make test-performance   # Performance tests

# With coverage
make test-coverage
```

### Test Structure

- **Unit Tests**: Each component in isolation
- **Integration Tests**: Complete system working together
- **Performance Tests**: Benchmarks and stress tests
- **Concurrency Tests**: Thread safety and race conditions

## 🔒 Thread Safety

### Synchronization Strategies

1. **Per-Key Locks**: Each key has its own lock
2. **Instance Lock**: For global operations (clear, stats)
3. **Calculation Locks**: Stampede protection per function
4. **Atomic Operations**: Thread-safe storage providers

### Stampede Protection

```python
# Multiple threads calling the same function simultaneously
# Only one executes, others wait for the result

@cache.cache(ttl_seconds=300)
def expensive_api_call(endpoint):
    # Only one thread will execute this at a time for the same endpoint
    return requests.get(endpoint).json()

# 100 simultaneous threads = 1 API call
results = await asyncio.gather(*[
    expensive_api_call("/api/data") for _ in range(100)
])
```

## 🚀 Performance

### Typical Benchmarks

- **Basic operations**: >10,000 ops/sec
- **Concurrent operations**: >5,000 ops/sec  
- **Memory usage**: <500MB for 50k items
- **Latency**: <1ms for hits, <10ms for misses

### Optimizations

- `__slots__` for memory efficiency
- Granular locks for high concurrency
- Optimized serialization with pickle
- Non-blocking background cleanup

## 🔌 Extensibility

### New Storage Providers

```python
class RedisStorage(IStorageProvider):
    def __init__(self, redis_client):
        self.redis = redis_client
    
    def get(self, key: _CacheKey) -> Optional[_CacheValue]:
        # Redis implementation
        pass
```

### New Eviction Policies

```python
class LFUEvictionPolicy(IEvictionPolicy):
    def notify_set(self, key, namespace, max_items, global_max_size):
        # Least Frequently Used implementation
        pass
```

## 📝 License

This project is open source and available under the MIT license.

## 🤝 Contributing

### Development Workflow

1. **Fork and Clone**
   ```bash
   git clone https://github.com/yourusername/cacheado.git
   cd cacheado
   ```

2. **Create Feature Branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```

3. **Development Cycle**
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Run tests during development
   make test-coverage
   
   # Check code quality
   make quality-check
   
   # Format code
   make format
   ```

4. **Pre-commit Validation**
   ```bash
   make check-all  # Runs tests + quality checks
   ```

5. **Submit Changes**
   ```bash
   git commit -m "feat: add amazing feature"
   git push origin feature/amazing-feature
   ```

6. **Create Pull Request**
   - All CI checks must pass
   - Maintain test coverage >95%
   - Follow conventional commit messages

### Release Process (Maintainers)

1. **Prepare Release**
   ```bash
   make bump-minor  # or bump-patch/bump-major
   git add pyproject.toml
   git commit -m "chore: bump version to X.Y.Z"
   ```

2. **Merge to Master**
   - Pipeline automatically:
     - Validates version bump
     - Runs full test suite
     - Creates Git tag
     - Publishes to PyPI
     - Creates GitHub release

### Guidelines

- **Test Coverage**: Maintain >95% coverage
- **Code Style**: Follow Black + isort formatting
- **Type Hints**: Add type annotations for new code
- **Documentation**: Update README for new features
- **Commit Messages**: Use conventional commits format

## 📚 Additional Documentation

- [Configuration Guide](docs/configuration.md)
- [API Reference](docs/api.md)
- [Advanced Examples](docs/examples.md)
- [Troubleshooting](docs/troubleshooting.md)

---

**Developed with ❤️ for high-performance Python applications**