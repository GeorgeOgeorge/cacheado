import logging
import pickle
import threading
from typing import List, Optional

import pymemcache.client.base

from cache_types import _CacheKey, _CacheValue
from protocols.storage_provider import IStorageProvider


class MemcachedStorage(IStorageProvider):
    """
    Thread-safe Memcached implementation of the IStorageProvider.

    Uses Memcached as the backend storage with server configuration.
    Serializes cache keys and values using pickle for Memcached compatibility.
    """

    __slots__ = ("_client", "_instance_lock")

    def __init__(self, server: str = "localhost:11211"):
        """Initializes the Memcached storage provider.

        Args:
            server (str): Memcached server address (default: "localhost:11211").
        """
        if not server:
            raise ValueError("Server address is required")

        try:
            self._client = pymemcache.client.base.Client(server)
            self._instance_lock = threading.Lock()

            self._client.version()
            logging.info(f"MemcachedStorage initialized with server: {server}")
        except Exception as e:
            logging.error(f"Failed to connect to Memcached: {e}")
            raise

    def _serialize_key(self, key: _CacheKey) -> str:
        """Serializes cache key for Memcached storage."""
        return pickle.dumps(key).hex()

    def _deserialize_key(self, serialized_key: str) -> _CacheKey:
        """Deserializes cache key from Memcached storage."""
        result = pickle.loads(bytes.fromhex(serialized_key))
        if not isinstance(result, tuple) or len(result) != 3:
            raise ValueError(f"Invalid cache key format: {result}")
        return result

    def get(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        Atomically gets a value tuple (value, expiry) from Memcached.

        Args:
            key (_CacheKey): The internal key to get.

        Returns:
            Optional[_CacheValue]: The stored tuple, or None.
        """
        try:
            serialized_key = self._serialize_key(key)
            serialized_value = self._client.get(serialized_key)

            if serialized_value is None:
                return None

            result = pickle.loads(serialized_value)
            if not isinstance(result, tuple) or len(result) != 2:
                raise ValueError(f"Invalid cache value format: {result}")
            return result
        except Exception as e:
            logging.error(f"Error getting key {key}: {e}")
            return None

    def get_value_no_lock(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        Performs a non-locking read for the cleanup loop.
        Memcached operations are atomic by default.

        Args:
            key (_CacheKey): The internal key to look up.

        Returns:
            Optional[_CacheValue]: The stored tuple (value, expiry) or None.
        """
        return self.get(key)

    def set(self, key: _CacheKey, value: _CacheValue) -> None:
        """
        Atomically sets a value tuple (value, expiry) in Memcached.

        Args:
            key (_CacheKey): The internal key to set.
            value (_CacheValue): The (value, expiry) tuple to store.
        """
        try:
            serialized_key = self._serialize_key(key)
            serialized_value = pickle.dumps(value)
            self._client.set(serialized_key, serialized_value)
        except Exception as e:
            logging.error(f"Error setting key {key}: {e}")
            raise

    def evict(self, key: _CacheKey) -> None:
        """
        Atomically evicts a key from Memcached.

        Args:
            key (_CacheKey): The internal key to evict.
        """
        try:
            serialized_key = self._serialize_key(key)
            self._client.delete(serialized_key)
        except Exception as e:
            logging.error(f"Error evicting key {key}: {e}")

    def get_all_keys(self) -> List[_CacheKey]:
        """
        Gets all keys from Memcached.
        Note: Memcached doesn't natively support key enumeration,
        so this returns an empty list as a limitation.

        Returns:
            List[_CacheKey]: Empty list (Memcached limitation).
        """
        logging.warning("Memcached does not support key enumeration. Returning empty list.")
        return []

    def clear(self) -> None:
        """Atomically clears the entire Memcached storage."""
        try:
            with self._instance_lock:
                self._client.flush_all()
        except Exception as e:
            logging.error(f"Error clearing storage: {e}")
