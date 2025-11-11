import logging
import threading
import time
from typing import TYPE_CHECKING, Optional

from cache_types import _CacheKey

if TYPE_CHECKING:
    from cache import Cache

from protocols.cache_policy_manager_protocol import ICachePolicyManager
from protocols.eviction_policy import IEvictionPolicy


class CachePolicyManager(ICachePolicyManager):
    """
    Manages cache maintenance policies (e.g., eviction, cleanup).

    This class handles background cleanup and delegates eviction logic
    to an injected IEvictionPolicy. Optimized with __slots__ for memory efficiency.
    """

    __slots__ = ("_cache", "_cleanup_interval", "_policy", "_global_max_size", "_stop_event", "_cleanup_thread")

    def __init__(
        self, cache_instance: "Cache", cleanup_interval: int, policy: IEvictionPolicy, max_size: Optional[int] = None
    ):
        """
        Initializes the policy manager.

        Args:
            cache_instance (Cache): The main Cache instance.
            cleanup_interval (int): The interval (in seconds) for the cleanup loop.
            policy (IEvictionPolicy): The injected eviction policy (e.g., LRUPolicy).
            max_size (Optional[int]): The maximum number of items allowed globally.
        """
        self._cache = cache_instance
        self._cleanup_interval = cleanup_interval
        self._policy = policy
        self._global_max_size = max_size
        self._stop_event = threading.Event()
        self._cleanup_thread: Optional[threading.Thread] = None
        logging.info(
            f"CachePolicyManager initialized with policy={policy.__class__.__name__}, "
            f"max_size={max_size}, cleanup_interval={cleanup_interval}s"
        )

    def start_background_cleanup(self) -> None:
        """
        Starts the background daemon thread for cache cleanup.
        """
        try:
            if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
                self._stop_event.clear()
                self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True, name="CacheCleanupThread")
                self._cleanup_thread.start()
                logging.info("Cache cleanup thread started.")
        except Exception as e:
            logging.error(f"Failed to start cache cleanup thread: {e}")
            raise

    def stop_background_cleanup(self) -> None:
        """Stops the background cleanup thread gracefully."""
        try:
            if self._cleanup_thread and self._cleanup_thread.is_alive():
                self._stop_event.set()
                self._cleanup_thread.join()
                logging.info("Cache cleanup thread stopped.")
        except Exception as e:
            logging.error(f"Error stopping cache cleanup thread: {e}")

    def _cleanup_loop(self) -> None:
        """
        The main loop for the garbage collector thread.

        Periodically scans keys and triggers passive eviction for expired items.
        """
        while not self._stop_event.wait(self._cleanup_interval):
            try:
                if self._cache is None:
                    continue

                all_keys = self._cache._get_all_keys_from_storage()
                if not all_keys:
                    continue

                logging.info(f"Background cleanup: checking {len(all_keys)} keys.")

                current_time = time.monotonic()
                expired_count = 0

                for key in all_keys:
                    value_tuple = self._cache._get_value_no_lock_from_storage(key)
                    if value_tuple and current_time > value_tuple[1]:
                        namespace = key[1]
                        self._cache._internal_get(key, namespace)
                        expired_count += 1

                if expired_count > 0:
                    logging.info(f"Background cleanup: {expired_count} expired keys removed.")

            except Exception as e:
                logging.error(f"Error in cache cleanup thread: {e}", exc_info=True)

    def notify_set(self, key: _CacheKey, namespace: str, max_items: Optional[int]) -> Optional[_CacheKey]:
        """
        Delegates 'set' notification to the eviction policy.

        Args:
            key (_CacheKey): The key that was set.
            namespace (str): The namespace of the key.
            max_items (Optional[int]): The max_items limit for this namespace.

        Returns:
            Optional[_CacheKey]: A key to evict, or None.
        """
        try:
            return self._policy.notify_set(key, namespace, max_items, self._global_max_size)
        except Exception as e:
            logging.error(f"Error in policy notify_set: {e}")
            return None

    def notify_get(self, key: _CacheKey, namespace: str) -> None:
        """
        Delegates 'get' notification to the eviction policy.

        Args:
            key (_CacheKey): The key that was accessed.
            namespace (str): The namespace of the key.
        """
        try:
            self._policy.notify_get(key, namespace)
        except Exception as e:
            logging.error(f"Error in policy notify_get: {e}")

    def notify_evict(self, key: _CacheKey, namespace: str) -> None:
        """
        Delegates 'evict' notification to the eviction policy.

        Args:
            key (_CacheKey): The key that was evicted.
            namespace (str): The namespace of the key.
        """
        try:
            self._policy.notify_evict(key, namespace)
        except Exception as e:
            logging.error(f"Error in policy notify_evict: {e}")

    def notify_clear(self) -> None:
        """Delegates 'clear' notification to the eviction policy."""
        try:
            self._policy.notify_clear()
        except Exception as e:
            logging.error(f"Error in policy notify_clear: {e}")

    def get_namespace_count(self) -> int:
        """
        Gets the total number of tracked namespaces from the policy.

        Returns:
            int: The count of namespaces.
        """
        return self._policy.get_namespace_count()

    def get_global_size(self) -> int:
        """
        Gets the global item count from the policy.

        Returns:
            int: The global item count.
        """
        return self._policy.get_global_size()

    @property
    def policy(self) -> IEvictionPolicy:
        """Returns the eviction policy instance."""
        return self._policy

    @property
    def global_max_size(self) -> Optional[int]:
        """Returns the global maximum cache size."""
        return self._global_max_size

    @property
    def cleanup_interval(self) -> int:
        """Returns the cleanup interval in seconds."""
        return self._cleanup_interval
