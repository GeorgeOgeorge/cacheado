import logging
import threading
from collections import defaultdict
from typing import DefaultDict, Dict, Optional

from cache_types import _CacheKey, _CacheValue
from protocols.storage_provider import IStorageProvider


class InMemory(IStorageProvider):
    """
    Thread-safe, in-memory implementation of the IStorageProvider.
    
    Uses key-based locks for high-concurrency atomic operations.
    """
    def __init__(self):
        """Initializes the in-memory storage."""
        self._cache: Dict[_CacheKey, _CacheValue] = {}
        self._key_locks: DefaultDict[_CacheKey, threading.Lock] = defaultdict(threading.Lock)
        self._instance_lock = threading.Lock()
        logging.info("InMemoryStorageProvider initialized.")

    def get(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        Atomically gets a value tuple (value, expiry) from memory.

        Args:
            key (_CacheKey): The internal key to get.

        Returns:
            Optional[_CacheValue]: The stored tuple, or None.
        """
        with self._key_locks[key]:
            return self._cache.get(key)
            
    def get_value_no_lock(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        Performs a non-locking ("dirty") read for the cleanup loop.
        
        Args:
            key (_CacheKey): The internal key to look up.

        Returns:
            Optional[_CacheValue]: The stored tuple (value, expiry) or None.
        """
        return self._cache.get(key)

    def set(self, key: _CacheKey, value: _CacheValue) -> None:
        """
        Atomically sets a value tuple (value, expiry) in memory.

        Args:
            key (_CacheKey): The internal key to set.
            value (_CacheValue): The (value, expiry) tuple to store.
        """
        with self._key_locks[key]:
            self._cache[key] = value
        
    def evict(self, key: _CacheKey) -> None:
        """
        Atomically evicts a key from memory and cleans up its lock.

        Args:
            key (_CacheKey): The internal key to evict.
        """
        with self._key_locks[key]:
            if key in self._cache:
                del self._cache[key]
            
            if key in self._key_locks:
                del self._key_locks[key]

    def get_all_keys(self) -> list[_CacheKey]:
        """
        Atomically gets a copy of all keys in memory.

        Returns:
            list[_CacheKey]: A list of all cache keys.
        """
        with self._instance_lock:
            return list(self._cache.keys())
        
    def clear(self) -> None:
        """Atomically clears the entire in-memory storage."""
        with self._instance_lock:
            self._cache.clear()
            self._key_locks.clear()
