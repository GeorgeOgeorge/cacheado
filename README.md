# Cacheado

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Test Coverage](https://img.shields.io/badge/coverage-91%25-brightgreen.svg)](https://github.com/GeorgeOgeorge/cacheado)

**High-performance Python cache system with hierarchical scopes, pluggable storage backends, and intelligent eviction policies**

Solves critical cache problems in enterprise applications: hierarchical data isolation (organization/user/tenant), flexible storage backends (In-Memory, Redis, MongoDB), intelligent memory management with LRU/TTL policies, and thread-safe operations with high performance.

## ⚡ Why Cacheado?

**Flexible Architecture** with pluggable storage providers  
**Zero configuration** for common use cases  
**Production-ready** with comprehensive eviction policies  

### Key Benefits

🚀 **Performance**: Optimized for high-throughput operations with <1ms latency  
🏢 **Multi-Tenant**: Hierarchical scope isolation (global → organization → user → session)  
🔌 **Pluggable Storage**: In-Memory, Redis, MongoDB support out-of-the-box  
⚡ **Async/Sync**: Full support for synchronous and asynchronous code  
🧠 **Smart Eviction**: LRU, TTL, and max-items policies with rule composition  
📊 **Observability**: Detailed metrics for hits, misses, evictions, and storage stats  

## 🚀 Quick Start

### Installation

```bash
# Basic installation (in-memory only)
pip install cacheado

# With Redis support
pip install cacheado[redis]

# With MongoDB support
pip install cacheado[mongodb]

# With all backends
pip install cacheado[all]

# For development
pip install cacheado[dev]
```

### Basic Usage (30 seconds to first result)

```python
from cache import Cache

# Instant creation with default in-memory storage
cache = Cache()

# Simple cache with decorator
@cache.cache(ttl_seconds=300)
def expensive_calculation(x, y):
    import time
    time.sleep(2)  # Simulates expensive operation
    return x * y

# First call: 2 seconds
result = expensive_calculation(10, 20)  # 200

# Second call: <1ms (cache hit!)
result = expensive_calculation(10, 20)  # 200 (from cache)
```

### Multi-Tenant Cache with Hierarchical Scopes

```python
from cache import Cache
from utils.cache_scope_config import ScopeConfig, ScopeLevel

# Configure hierarchical scopes
scope_config = ScopeConfig([
    ScopeLevel("organization", "org_id", [
        ScopeLevel("user", "user_id")
    ])
])

cache = Cache(scope_config=scope_config)

# Cache isolated by organization and user
@cache.cache(ttl_seconds=600, scope="user")
def get_user_data(user_id, org_id=None):
    return fetch_from_database(user_id)

# Data automatically isolated by scope
user_data_org1 = get_user_data("123", org_id="org1")
user_data_org2 = get_user_data("123", org_id="org2")
# Different caches, same user_id!
```

## 🔌 Storage Backends

> **Note**: In-Memory storage is included by default. For Redis or MongoDB, install the respective extras.

### In-Memory Storage (Default)

```python
from cache import Cache
from storages.in_memory import InMemory

cache = Cache(storage_provider=InMemory())
```

### Redis Storage

```bash
# Install Redis support
pip install cacheado[redis]
```

```python
from cache import Cache
from storages.redis import RedisStorage

redis_storage = RedisStorage(
    connection_string="redis://localhost:6379",
    db=0
)
cache = Cache(storage_provider=redis_storage)
```

### MongoDB Storage

```bash
# Install MongoDB support
pip install cacheado[mongodb]
```

```python
from cache import Cache
from storages.mongodb import MongoDBStorage

mongo_storage = MongoDBStorage(
    connection_string="mongodb://localhost:27017",
    db_name="cache_db",
    collection_name="cache_collection"
)
cache = Cache(storage_provider=mongo_storage)
```

## 🧠 Intelligent Eviction Policies

### LRU (Least Recently Used)

```python
from cache import Cache
from storages.in_memory import InMemory
from storages.rules.lru_evict import LRUEvict

storage = InMemory()
lru_rule = LRUEvict(max_items=1000)
cache = Cache(storage_provider=storage, storage_rules=[lru_rule])
```

### TTL (Time-To-Live)

```python
from storages.rules.lifetime_evict import LifeTimeEvict

storage = InMemory()
ttl_rule = LifeTimeEvict()
cache = Cache(storage_provider=storage, storage_rules=[ttl_rule])

# Items expire automatically based on TTL
cache.set("key1", "value1", ttl_seconds=60)
```

### Max Items (Hard Limit)

```python
from storages.rules.max_items_evict import MaxItemsEvict

storage = InMemory()
max_items_rule = MaxItemsEvict(max_items=500)
cache = Cache(storage_provider=storage, storage_rules=[max_items_rule])
```

### Combining Multiple Rules

```python
# Combine LRU + TTL for optimal memory management
storage = InMemory()
lru_rule = LRUEvict(max_items=1000)
ttl_rule = LifeTimeEvict()

cache = Cache(
    storage_provider=storage,
    storage_rules=[lru_rule, ttl_rule]
)
```

## 📊 Observability

### Real-Time Metrics

```python
stats = cache.stats()
print(stats)
# {
#     "hits": 1250,
#     "misses": 180,
#     "evictions": 45,
#     "storage_type": "in_memory",
#     "total_keys": 8934
# }
```

### Cache Hit Rate Monitoring

```python
# Monitor cache effectiveness
stats = cache.stats()
hit_rate = stats["hits"] / (stats["hits"] + stats["misses"]) * 100
print(f"Cache hit rate: {hit_rate:.2f}%")
```

## 🛠️ Advanced Use Cases

### Asynchronous Cache

```python
import asyncio

# Native support for async/await
@cache.cache(ttl_seconds=180, scope="global")
async def fetch_api_data(endpoint):
    async with httpx.AsyncClient() as client:
        response = await client.get(endpoint)
        return response.json()

# Async programmatic operations
await cache.aset("key1", "value1", ttl_seconds=300)
value = await cache.aget("key1")
await cache.aevict("key1")
await cache.aclear()
```

### Programmatic Cache Operations

```python
# Direct cache operations
cache.set("user_settings", {"theme": "dark"}, ttl_seconds=3600, 
          scope="user", org_id="org_123", user_id="user_456")

settings = cache.get("user_settings", 
                    scope="user", org_id="org_123", user_id="user_456")

# Evict specific key
cache.evict("user_settings", scope="user", org_id="org_123", user_id="user_456")
```

### Scope-based Eviction

```python
# Remove all data from an organization
count = cache.evict_by_scope("organization", org_id="org_123")
print(f"Evicted {count} items")

# Remove data from a specific user
count = cache.evict_by_scope("user", org_id="org_123", user_id="user_456")
```

### Decorator with Scope Parameters

```python
@cache.cache(ttl_seconds=300, scope="user")
def get_user_preferences(user_id, org_id=None):
    # org_id is automatically extracted for scope resolution
    return load_preferences(user_id)

# Scope parameters extracted from kwargs
prefs = get_user_preferences("user_123", org_id="org_456")
```

## 🔧 Advanced Configuration

### Custom Scope Hierarchies

```python
from utils.cache_scope_config import ScopeConfig, ScopeLevel

# Configure complex hierarchies
scope_config = ScopeConfig([
    ScopeLevel("organization", "org_id", [
        ScopeLevel("department", "dept_id", [
            ScopeLevel("user", "user_id", [
                ScopeLevel("session", "session_id")
            ])
        ])
    ])
])

cache = Cache(scope_config=scope_config)

# Use nested scopes
@cache.cache(ttl_seconds=600, scope="session")
def get_session_data(session_id, org_id=None, dept_id=None, user_id=None):
    return fetch_session_data(session_id)
```

### Custom Storage Provider

```python
from protocols.storage_provider import IStorageProvider

class CustomStorage(IStorageProvider):
    def get(self, key: str):
        # Implement custom get logic
        pass
    
    def set(self, key: str, value: Any, ttl_seconds: float):
        # Implement custom set logic
        pass
    
    # Implement other required methods...

cache = Cache(storage_provider=CustomStorage())
```

### Custom Eviction Rules

```python
from protocols.storage_rule import IStorageRule
from utils.cache_types import RuleSideEffect, StorageRuleAction

class CustomRule(IStorageRule):
    def on_get(self, key: str):
        # Custom logic on get
        return None
    
    def on_set(self, key: str, value: Any, ttl_seconds: float):
        # Custom logic on set
        return None
    
    # Implement other required methods...

cache = Cache(storage_rules=[CustomRule()])
```

## 🧪 Testing

```bash
# Run all tests
make test

# Tests with coverage
make test-coverage

# Run specific test file
python -m pytest tests/test_cache.py -v

# Run with coverage report
python -m pytest --cov=. --cov-report=html --cov-report=term-missing
```

## 📁 Project Structure

```
cache/
├── cache.py                    # Main Cache class
├── protocols/                  # Protocol definitions
│   ├── storage_provider.py    # Storage backend interface
│   └── storage_rule.py        # Eviction rule interface
├── storages/                   # Storage implementations
│   ├── in_memory.py           # In-memory storage
│   ├── redis.py               # Redis storage
│   ├── mongodb.py             # MongoDB storage
│   ├── rule_aware_storage.py  # Rule decorator
│   └── rules/                 # Eviction policies
│       ├── lifetime_evict.py  # TTL-based eviction
│       ├── lru_evict.py       # LRU eviction
│       └── max_items_evict.py # Max items eviction
├── utils/                      # Utilities
│   ├── cache_types.py         # Type definitions
│   └── cache_scope_config.py  # Scope configuration
└── tests/                      # Test suite
    ├── test_cache.py
    ├── test_in_memory.py
    ├── test_redis.py
    ├── test_mongodb.py
    └── ...
```

## 🎯 Design Principles

### 1. Protocol-Based Architecture
Uses Python protocols for loose coupling and easy extensibility.

### 2. Dependency Injection
Storage providers and rules are injected, enabling flexible composition.

### 3. Separation of Concerns
- **Cache**: High-level API and decorator logic
- **Storage**: Data persistence and retrieval
- **Rules**: Eviction policies and side effects
- **Scopes**: Hierarchical key resolution

### 4. Thread-Safe Operations
All storage operations are atomic and thread-safe.

### 5. Async-First Design
Full support for async/await with non-blocking operations.

## 📝 License

This project is open source and available under the MIT license.

## 🤝 Contributing

1. **Fork and Clone**
   ```bash
   git clone https://github.com/GeorgeOgeorge/cacheado.git
   cd cacheado
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-build.txt
   ```

3. **Run Tests**
   ```bash
   make test-coverage
   ```

4. **Code Quality**
   ```bash
   make lint
   make format
   ```

5. **Submit Pull Request**
   - Maintain test coverage >90%
   - Follow code standards (Black + isort + flake8)
   - Add tests for new features
   - Update documentation

## 🐛 Known Limitations

- Redis and MongoDB require external services
- Async operations use `asyncio.to_thread` for sync storage backends
- Scope validation happens at runtime, not compile-time

## 📚 Useful Links

- [Issues and Bug Reports](https://github.com/GeorgeOgeorge/cacheado/issues)
- [Changelog](https://github.com/GeorgeOgeorge/cacheado/releases)

---

**Built with ❤️ for high-performance Python applications**
