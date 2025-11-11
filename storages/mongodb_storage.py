import logging
import pickle
import threading
from typing import List, Optional

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from cache_types import _CacheKey, _CacheValue
from protocols.storage_provider import IStorageProvider


class MongoDBStorage(IStorageProvider):
    """
    Thread-safe MongoDB implementation of the IStorageProvider.

    Uses MongoDB as the backend storage with connection string configuration.
    Serializes cache keys and values using pickle for MongoDB compatibility.
    """

    __slots__ = ("_client", "_db", "_collection", "_instance_lock")

    def __init__(self, connection_string: str, database: str = "cache", collection: str = "items"):
        """Initializes the MongoDB storage provider.

        Args:
            connection_string (str): MongoDB connection string.
            database (str): Database name (default: "cache").
            collection (str): Collection name (default: "items").
        """
        if not connection_string:
            raise ValueError("Connection string is required")

        try:
            self._client: MongoClient = MongoClient(connection_string)
            self._db: Database = self._client[database]
            self._collection: Collection = self._db[collection]
            self._instance_lock: threading.Lock = threading.Lock()

            self._client.admin.command("ping")
            logging.info(f"MongoDBStorage initialized with connection: {connection_string}")
        except Exception as e:
            logging.error(f"Failed to connect to MongoDB: {e}")
            raise

    def _serialize_key(self, key: _CacheKey) -> str:
        """Serializes cache key for MongoDB storage."""
        return pickle.dumps(key).hex()

    def _deserialize_key(self, serialized_key: str) -> _CacheKey:
        """Deserializes cache key from MongoDB storage."""
        result = pickle.loads(bytes.fromhex(serialized_key))
        if not isinstance(result, tuple) or len(result) != 3:
            raise ValueError(f"Invalid cache key format: {result}")
        return result

    def get(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        Atomically gets a value tuple (value, expiry) from MongoDB.

        Args:
            key (_CacheKey): The internal key to get.

        Returns:
            Optional[_CacheValue]: The stored tuple, or None.
        """
        try:
            serialized_key = self._serialize_key(key)
            doc = self._collection.find_one({"_id": serialized_key})

            if doc is None:
                return None

            result = pickle.loads(doc["value"])
            if not isinstance(result, tuple) or len(result) != 2:
                raise ValueError(f"Invalid cache value format: {result}")
            return result
        except Exception as e:
            logging.error(f"Error getting key {key}: {e}")
            return None

    def get_value_no_lock(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        Performs a non-locking read for the cleanup loop.
        MongoDB operations are atomic by default.

        Args:
            key (_CacheKey): The internal key to look up.

        Returns:
            Optional[_CacheValue]: The stored tuple (value, expiry) or None.
        """
        return self.get(key)

    def set(self, key: _CacheKey, value: _CacheValue) -> None:
        """
        Atomically sets a value tuple (value, expiry) in MongoDB.

        Args:
            key (_CacheKey): The internal key to set.
            value (_CacheValue): The (value, expiry) tuple to store.
        """
        try:
            serialized_key = self._serialize_key(key)
            serialized_value = pickle.dumps(value)

            self._collection.replace_one(
                {"_id": serialized_key}, {"_id": serialized_key, "value": serialized_value}, upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting key {key}: {e}")
            raise

    def evict(self, key: _CacheKey) -> None:
        """
        Atomically evicts a key from MongoDB.

        Args:
            key (_CacheKey): The internal key to evict.
        """
        try:
            serialized_key = self._serialize_key(key)
            self._collection.delete_one({"_id": serialized_key})
        except Exception as e:
            logging.error(f"Error evicting key {key}: {e}")

    def get_all_keys(self) -> List[_CacheKey]:
        """
        Atomically gets a copy of all keys in MongoDB.

        Returns:
            List[_CacheKey]: A list of all cache keys.
        """
        try:
            with self._instance_lock:
                docs = self._collection.find({}, {"_id": 1})
                return [self._deserialize_key(doc["_id"]) for doc in docs]
        except Exception as e:
            logging.error(f"Error getting all keys: {e}")
            return []

    def clear(self) -> None:
        """Atomically clears the entire MongoDB collection."""
        try:
            with self._instance_lock:
                self._collection.delete_many({})
        except Exception as e:
            logging.error(f"Error clearing storage: {e}")
