import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, List, Optional, Union

from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.mongo_client import AsyncMongoClient
from pymongo.collection import Collection
from pymongo.errors import OperationFailure
from pymongo.synchronous.mongo_client import MongoClient

from protocols.storage_provider import IStorageProvider
from utils.cache_types import _CacheValue


class MongoDBStorage(IStorageProvider):
    """Persistent storage implementation using MongoDB. Supports synchronous and asynchronous operations
    for flexibility in hybrid contexts.

    This class manages dual connections (Sync/Async) to allow usage
    in different parts of the application without duplicating configuration logic.
    """

    def __init__(
        self,
        connection_string: str,
        db_name: Optional[str] = None,
        collection_name: Optional[str] = None,
        event_listeners: Optional[list] = None,
        **extra_options: Any,
    ) -> None:
        """
        Initializes the MongoDB storage provider.

        Warning: This constructor performs I/O operations (ping and index verification),
        which may cause blocking during initialization.

        Args:
            connection_string (str): The MongoDB connection URI (e.g., mongodb://localhost:27017).
            db_name (Optional[str]): Database name. Default: "cacheado_cache_db".
            collection_name (Optional[str]): Collection name. Default: "cacheado_cache_collection".
            event_listeners (Optional[list]): List of PyMongo event listeners.
            **extra_options: Additional options passed directly to the MongoDB client.

        Raises:
            ConnectionError: If unable to establish a connection to the MongoDB server (ping fails).
        """
        self._db_name = db_name or "cacheado_cache_db"
        self._collection_name = collection_name or "cacheado_cache_collection"

        self._sync_client: MongoClient = MongoClient(
            host=connection_string,
            event_listeners=event_listeners,
            **extra_options,
        )

        try:
            self._sync_client.admin.command("ping")
        except Exception as e:
            raise ConnectionError(f"Could not connect to MongoDB server: {e}")

        self.check_collection(self._sync_client, self._db_name, self._collection_name)

        self._async_client: AsyncMongoClient = AsyncMongoClient(
            host=connection_string, event_listeners=event_listeners, **extra_options
        )

    @staticmethod
    def check_collection(sync_client: MongoClient, db_name: str, collection_name: str) -> None:
        """
        Verifies the existence of the collection and ensures the creation of necessary indexes.

        This operation is idempotent and safe to be called during initialization,
        although it involves synchronous I/O.

        Args:
            sync_client (MongoClient): The connected synchronous MongoDB client.
            db_name (str): The target database name.
            collection_name (str): The target collection name.
        """
        cache_collection: Collection = sync_client[db_name][collection_name]
        try:
            cache_collection.create_index("key", unique=True)
        except OperationFailure:
            pass

    @asynccontextmanager
    async def get_async_collection(self) -> AsyncGenerator[AsyncCollection, None]:
        """
        Context manager to get the asynchronous MongoDB collection.

        Uses a context manager to facilitate resource management,
        although in MongoDB the connection is usually managed by the driver pool.

        Yields:
            AsyncCollection: The collection instance ready for awaitable operations.
        """
        collection_connection = self._async_client[self._db_name][self._collection_name]
        try:
            yield collection_connection
        finally:
            pass

    def get_sync_collection(self) -> Collection:
        """
        Gets the direct instance of the synchronous collection.

        Returns:
            Collection: The PyMongo MongoDB collection.
        """
        return self._sync_client[self._db_name][self._collection_name]

    def set(self, key: str, value: Any, ttl_seconds: Union[int, float]) -> None:
        """
        Stores a value in the cache with a defined time-to-live (TTL).
        Synchronous operation (blocking).

        Args:
            key (str): The unique key for item identification.
            value (Any): The value to be stored (must be BSON serializable).
            ttl_seconds (Union[int, float]): Time in seconds until expiration.
        """
        collection = self.get_sync_collection()
        collection.update_one(
            {"key": key}, {"$set": {"value": value, "ttl_seconds": time.monotonic() + ttl_seconds}}, upsert=True
        )

    def get(self, key: str) -> Optional[_CacheValue]:
        """
        Retrieves a value from the cache atomically.
        Synchronous operation (blocking).

        Args:
            key (str): The key of the item to be retrieved.

        Returns:
            Optional[_CacheValue]: A tuple (value, expiration_timestamp) if found,
            or None if the key does not exist.
        """
        collection = self.get_sync_collection()

        result = collection.find_one({"key": key})
        if result:
            return (result["value"], result["ttl_seconds"])

        return None

    def evict(self, key: str) -> None:
        """
        Explicitly removes a key from storage.
        Synchronous operation (blocking).

        Args:
            key (str): The key to be removed.
        """
        collection = self.get_sync_collection()
        collection.delete_one({"key": key})

    def get_all_keys(self) -> List[str]:
        """
        Returns all keys present in storage.
        Warning: Can be costly in very large collections.

        Returns:
            List[str]: List containing all stored keys.
        """
        collection = self.get_sync_collection()
        keys = collection.distinct("key")
        return keys

    def clear(self) -> None:
        """
        Clears the entire storage, removing all documents from the collection.
        Synchronous operation (blocking).
        """
        collection = self.get_sync_collection()
        collection.delete_many({})

    async def aget(self, key: str) -> Optional[_CacheValue]:
        """
        Retrieves a value from the cache asynchronously.
        Does not block the Event Loop.

        Args:
            key (str): The key of the item to be retrieved.

        Returns:
            Optional[_CacheValue]: Tuple (value, expiry) or None.
        """
        async with self.get_async_collection() as cache_collection:
            result = await cache_collection.find_one({"key": key})
            if result:
                return (result["value"], result["ttl_seconds"])

            return None

    async def aset(self, key: str, value: Any, ttl_seconds: Union[int, float]) -> None:
        """
        Stores a value asynchronously with TTL.
        Does not block the Event Loop.

        Args:
            key (str): Cache key.
            value (Any): Value to store.
            ttl_seconds (Union[int, float]): Time-to-live in seconds.
        """
        async with self.get_async_collection() as cache_collection:
            await cache_collection.update_one(
                {"key": key}, {"$set": {"value": value, "ttl_seconds": time.monotonic() + ttl_seconds}}, upsert=True
            )

    async def aevict(self, key: str) -> None:
        """
        Removes a key asynchronously.

        Args:
            key (str): The key to remove.
        """
        async with self.get_async_collection() as cache_collection:
            await cache_collection.delete_one({"key": key})

    async def aget_all_keys(self) -> List[str]:
        """
        Returns all keys asynchronously.

        Returns:
            List[str]: List of keys.
        """
        async with self.get_async_collection() as cache_collection:
            keys = await cache_collection.distinct("key")
            return keys

    async def aclear(self) -> None:
        """
        Clears the entire storage asynchronously.
        """
        async with self.get_async_collection() as cache_collection:
            await cache_collection.delete_many({})
