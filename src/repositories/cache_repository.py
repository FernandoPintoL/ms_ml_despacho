"""
Cache Repository
Specialized Redis caching operations for frequently accessed data
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

from ..config.logger import LoggerMixin


class CacheRepository(LoggerMixin):
    """
    Repository for Redis-specific caching operations

    Provides:
    - Pattern-based caching
    - Distributed locking
    - Cache warming
    - Cache statistics
    """

    def __init__(self, redis_client):
        """
        Initialize Cache Repository

        Args:
            redis_client: Redis client instance
        """
        self.redis = redis_client

    # ============================================
    # BASIC CACHE OPERATIONS
    # ============================================

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        try:
            value = self.redis.get(key)

            if value:
                # Try to deserialize JSON
                try:
                    return json.loads(value) if isinstance(value, str) else value
                except:
                    return value

            return None

        except Exception as e:
            self.log_warning(f"Cache get error for {key}: {str(e)}")
            return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """
        Set cache value

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds

        Returns:
            True if successful
        """
        try:
            # Serialize if needed
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            else:
                value = str(value)

            self.redis.setEx(key, ttl, value)
            self.log_debug(f"Cache set: {key} (TTL: {ttl}s)")
            return True

        except Exception as e:
            self.log_warning(f"Cache set error for {key}: {str(e)}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete cache key

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        try:
            result = self.redis.delete(key)
            self.log_debug(f"Cache delete: {key}")
            return result > 0

        except Exception as e:
            self.log_warning(f"Cache delete error for {key}: {str(e)}")
            return False

    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache

        Args:
            key: Cache key

        Returns:
            True if exists
        """
        try:
            return self.redis.exists(key) > 0

        except Exception as e:
            self.log_warning(f"Cache exists error for {key}: {str(e)}")
            return False

    # ============================================
    # PATTERN-BASED OPERATIONS
    # ============================================

    def get_by_pattern(self, pattern: str) -> Dict[str, Any]:
        """
        Get all keys matching pattern

        Args:
            pattern: Pattern to match (e.g., "dispatch:*")

        Returns:
            Dictionary of keys and values
        """
        try:
            result = {}
            cursor = 0

            while True:
                cursor, keys = self.redis.scan(cursor, match=pattern, count=100)

                for key in keys:
                    value = self.get(key.decode() if isinstance(key, bytes) else key)
                    if value:
                        result[key] = value

                if cursor == 0:
                    break

            self.log_debug(f"Retrieved {len(result)} keys matching {pattern}")
            return result

        except Exception as e:
            self.log_warning(f"Cache get_by_pattern error for {pattern}: {str(e)}")
            return {}

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern

        Args:
            pattern: Pattern to match

        Returns:
            Number of deleted keys
        """
        try:
            deleted = 0
            cursor = 0

            while True:
                cursor, keys = self.redis.scan(cursor, match=pattern, count=100)

                if keys:
                    deleted += self.redis.delete(*keys)

                if cursor == 0:
                    break

            self.log_info(f"Cache deleted: {deleted} keys matching {pattern}")
            return deleted

        except Exception as e:
            self.log_warning(f"Cache delete_pattern error for {pattern}: {str(e)}")
            return 0

    # ============================================
    # DISTRIBUTED LOCKING
    # ============================================

    def acquire_lock(self, key: str, ttl: int = 10) -> bool:
        """
        Acquire distributed lock

        Args:
            key: Lock key
            ttl: Lock time to live in seconds

        Returns:
            True if lock acquired
        """
        try:
            # Use SET with NX (only if not exists)
            lock_key = f"lock:{key}"
            timestamp = datetime.utcnow().isoformat()

            # Redis SET with NX and EX
            result = self.redis.set(lock_key, timestamp, ex=ttl, nx=True)

            if result:
                self.log_debug(f"Lock acquired: {lock_key}")
                return True

            return False

        except Exception as e:
            self.log_warning(f"Lock acquire error for {key}: {str(e)}")
            return False

    def release_lock(self, key: str) -> bool:
        """
        Release distributed lock

        Args:
            key: Lock key

        Returns:
            True if released
        """
        try:
            lock_key = f"lock:{key}"
            result = self.redis.delete(lock_key)
            self.log_debug(f"Lock released: {lock_key}")
            return result > 0

        except Exception as e:
            self.log_warning(f"Lock release error for {key}: {str(e)}")
            return False

    # ============================================
    # COUNTER OPERATIONS
    # ============================================

    def increment(self, key: str, amount: int = 1) -> int:
        """
        Increment counter

        Args:
            key: Counter key
            amount: Amount to increment

        Returns:
            New counter value
        """
        try:
            return self.redis.incrby(key, amount)

        except Exception as e:
            self.log_warning(f"Counter increment error for {key}: {str(e)}")
            return 0

    def decrement(self, key: str, amount: int = 1) -> int:
        """
        Decrement counter

        Args:
            key: Counter key
            amount: Amount to decrement

        Returns:
            New counter value
        """
        try:
            return self.redis.decrby(key, amount)

        except Exception as e:
            self.log_warning(f"Counter decrement error for {key}: {str(e)}")
            return 0

    def get_counter(self, key: str) -> int:
        """
        Get counter value

        Args:
            key: Counter key

        Returns:
            Counter value
        """
        try:
            value = self.redis.get(key)
            return int(value) if value else 0

        except Exception as e:
            self.log_warning(f"Counter get error for {key}: {str(e)}")
            return 0

    # ============================================
    # LIST OPERATIONS
    # ============================================

    def push_list(self, key: str, value: Any, max_items: int = None) -> bool:
        """
        Push item to list (LPUSH)

        Args:
            key: List key
            value: Value to push
            max_items: Max items to keep (LTRIM if exceeded)

        Returns:
            True if successful
        """
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            else:
                value = str(value)

            self.redis.lpush(key, value)

            # Trim if needed
            if max_items:
                self.redis.ltrim(key, 0, max_items - 1)

            self.log_debug(f"List push: {key}")
            return True

        except Exception as e:
            self.log_warning(f"List push error for {key}: {str(e)}")
            return False

    def get_list(self, key: str, start: int = 0, end: int = -1) -> List[Any]:
        """
        Get list items

        Args:
            key: List key
            start: Start index
            end: End index

        Returns:
            List of items
        """
        try:
            items = self.redis.lrange(key, start, end)
            result = []

            for item in items:
                try:
                    item_str = item.decode() if isinstance(item, bytes) else item
                    result.append(json.loads(item_str))
                except:
                    result.append(item)

            return result

        except Exception as e:
            self.log_warning(f"List get error for {key}: {str(e)}")
            return []

    def list_length(self, key: str) -> int:
        """
        Get list length

        Args:
            key: List key

        Returns:
            List length
        """
        try:
            return self.redis.llen(key)

        except Exception as e:
            self.log_warning(f"List length error for {key}: {str(e)}")
            return 0

    # ============================================
    # SET OPERATIONS
    # ============================================

    def add_to_set(self, key: str, *members: Any) -> int:
        """
        Add members to set

        Args:
            key: Set key
            *members: Members to add

        Returns:
            Number of added members
        """
        try:
            members_str = [str(m) for m in members]
            return self.redis.sadd(key, *members_str)

        except Exception as e:
            self.log_warning(f"Set add error for {key}: {str(e)}")
            return 0

    def remove_from_set(self, key: str, *members: Any) -> int:
        """
        Remove members from set

        Args:
            key: Set key
            *members: Members to remove

        Returns:
            Number of removed members
        """
        try:
            members_str = [str(m) for m in members]
            return self.redis.srem(key, *members_str)

        except Exception as e:
            self.log_warning(f"Set remove error for {key}: {str(e)}")
            return 0

    def get_set(self, key: str) -> set:
        """
        Get all set members

        Args:
            key: Set key

        Returns:
            Set of members
        """
        try:
            members = self.redis.smembers(key)
            return {m.decode() if isinstance(m, bytes) else m for m in members}

        except Exception as e:
            self.log_warning(f"Set get error for {key}: {str(e)}")
            return set()

    # ============================================
    # CACHE STATISTICS & MONITORING
    # ============================================

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dictionary with cache stats
        """
        try:
            info = self.redis.info('memory')

            return {
                'used_memory': info.get('used_memory_human', 'N/A'),
                'used_memory_bytes': info.get('used_memory', 0),
                'peak_memory': info.get('used_memory_peak_human', 'N/A'),
                'memory_fragmentation': info.get('mem_fragmentation_ratio', 0),
                'evicted_keys': info.get('evicted_keys', 0),
                'expired_keys': info.get('expired_keys', 0),
                'total_keys': self.redis.dbsize()
            }

        except Exception as e:
            self.log_warning(f"Error getting cache stats: {str(e)}")
            return {}

    def warm_cache(self, cache_data: Dict[str, Dict]) -> int:
        """
        Warm cache with data

        Args:
            cache_data: Dictionary with key -> {value, ttl} mappings

        Returns:
            Number of items cached
        """
        try:
            count = 0

            for key, config in cache_data.items():
                value = config.get('value')
                ttl = config.get('ttl', 3600)

                if self.set(key, value, ttl):
                    count += 1

            self.log_info(f"Cache warmed with {count} items")
            return count

        except Exception as e:
            self.log_error(f"Error warming cache: {str(e)}")
            return 0

    def clear_all(self) -> bool:
        """
        Clear entire cache (FLUSHDB)

        WARNING: This clears all Redis data!

        Returns:
            True if successful
        """
        try:
            self.redis.flushdb()
            self.log_warning("Cache cleared completely")
            return True

        except Exception as e:
            self.log_error(f"Error clearing cache: {str(e)}")
            return False
