"""
Base Repository Class
Provides common database and cache operations for all repositories
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json

from ..config.logger import LoggerMixin


class BaseRepository(ABC, LoggerMixin):
    """
    Abstract base class for all repositories

    Provides:
    - Common database operations
    - Redis caching
    - Transaction handling
    - Query building
    """

    def __init__(self, db_connection=None, redis_client=None):
        """
        Initialize base repository

        Args:
            db_connection: Database connection object
            redis_client: Redis client instance
        """
        self.db = db_connection
        self.redis = redis_client
        self.cache_prefix = self.__class__.__name__.lower()
        self.cache_ttl = 3600  # 1 hour default
        self.log_info(f"Initialized {self.__class__.__name__} repository")

    # ============================================
    # CACHE OPERATIONS
    # ============================================

    def get_cache(self, key: str) -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        if not self.redis:
            return None

        try:
            full_key = f"{self.cache_prefix}:{key}"
            cached = self.redis.get(full_key)

            if cached:
                self.log_debug(f"Cache hit: {full_key}")
                return json.loads(cached) if isinstance(cached, str) else cached

            return None

        except Exception as e:
            self.log_warning(f"Cache get error: {str(e)}")
            return None

    def set_cache(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds

        Returns:
            True if successful
        """
        if not self.redis:
            return False

        try:
            full_key = f"{self.cache_prefix}:{key}"
            ttl = ttl or self.cache_ttl

            # Serialize value
            if isinstance(value, (dict, list)):
                value = json.dumps(value)

            self.redis.setEx(full_key, ttl, str(value))
            self.log_debug(f"Cache set: {full_key} (TTL: {ttl}s)")
            return True

        except Exception as e:
            self.log_warning(f"Cache set error: {str(e)}")
            return False

    def delete_cache(self, key: str) -> bool:
        """
        Delete from cache

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        if not self.redis:
            return False

        try:
            full_key = f"{self.cache_prefix}:{key}"
            result = self.redis.delete(full_key)
            self.log_debug(f"Cache delete: {full_key}")
            return result > 0

        except Exception as e:
            self.log_warning(f"Cache delete error: {str(e)}")
            return False

    def clear_cache_pattern(self, pattern: str) -> int:
        """
        Clear cache by pattern

        Args:
            pattern: Pattern to match (e.g., "dispatch:*")

        Returns:
            Number of keys deleted
        """
        if not self.redis:
            return 0

        try:
            full_pattern = f"{self.cache_prefix}:{pattern}"
            deleted = 0

            # Get all keys matching pattern
            cursor = 0
            while True:
                cursor, keys = self.redis.scan(cursor, match=full_pattern, count=100)
                if keys:
                    deleted += self.redis.delete(*keys)
                if cursor == 0:
                    break

            self.log_debug(f"Cache cleared: {deleted} keys matching {full_pattern}")
            return deleted

        except Exception as e:
            self.log_warning(f"Cache clear error: {str(e)}")
            return 0

    # ============================================
    # DATABASE OPERATIONS
    # ============================================

    @abstractmethod
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        """
        Execute a database query

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            List of result rows
        """
        pass

    @abstractmethod
    def execute_update(self, query: str, params: Optional[tuple] = None) -> int:
        """
        Execute database update/insert/delete

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Number of affected rows
        """
        pass

    # ============================================
    # COMMON OPERATIONS
    # ============================================

    def find_by_id(self, table: str, id: Any) -> Optional[Dict]:
        """
        Find record by ID

        Args:
            table: Table name
            id: Record ID

        Returns:
            Record dictionary or None
        """
        try:
            # Check cache first
            cache_key = f"{table}:{id}"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            # Query database
            query = f"SELECT * FROM {table} WHERE id = %s"
            results = self.execute_query(query, (id,))

            if results:
                record = results[0]
                self.set_cache(cache_key, record)
                return record

            return None

        except Exception as e:
            self.log_error(f"Error finding record: {str(e)}")
            return None

    def find_all(self, table: str, limit: Optional[int] = None, offset: int = 0) -> List[Dict]:
        """
        Get all records

        Args:
            table: Table name
            limit: Limit results
            offset: Offset for pagination

        Returns:
            List of records
        """
        try:
            query = f"SELECT * FROM {table}"
            params = []

            if limit:
                query += f" LIMIT %s OFFSET %s"
                params = [limit, offset]

            return self.execute_query(query, tuple(params) if params else None)

        except Exception as e:
            self.log_error(f"Error finding all records: {str(e)}")
            return []

    def count(self, table: str, where: Optional[str] = None) -> int:
        """
        Count records

        Args:
            table: Table name
            where: WHERE clause (without WHERE keyword)

        Returns:
            Record count
        """
        try:
            query = f"SELECT COUNT(*) as count FROM {table}"
            if where:
                query += f" WHERE {where}"

            results = self.execute_query(query)
            return results[0]['count'] if results else 0

        except Exception as e:
            self.log_error(f"Error counting records: {str(e)}")
            return 0

    def save(self, table: str, data: Dict) -> bool:
        """
        Save/update record

        Args:
            table: Table name
            data: Record data

        Returns:
            True if successful
        """
        try:
            # Determine if insert or update
            if 'id' in data and data['id']:
                return self._update(table, data)
            else:
                return self._insert(table, data)

        except Exception as e:
            self.log_error(f"Error saving record: {str(e)}")
            return False

    def delete(self, table: str, id: Any) -> bool:
        """
        Delete record

        Args:
            table: Table name
            id: Record ID

        Returns:
            True if successful
        """
        try:
            query = f"DELETE FROM {table} WHERE id = %s"
            affected = self.execute_update(query, (id,))

            # Clear cache
            self.delete_cache(f"{table}:{id}")

            return affected > 0

        except Exception as e:
            self.log_error(f"Error deleting record: {str(e)}")
            return False

    def _insert(self, table: str, data: Dict) -> bool:
        """Internal insert operation"""
        try:
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['%s'] * len(data))
            query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

            affected = self.execute_update(query, tuple(data.values()))
            return affected > 0

        except Exception as e:
            self.log_error(f"Error inserting record: {str(e)}")
            return False

    def _update(self, table: str, data: Dict) -> bool:
        """Internal update operation"""
        try:
            record_id = data.pop('id')
            updates = ', '.join([f"{k} = %s" for k in data.keys()])
            query = f"UPDATE {table} SET {updates} WHERE id = %s"

            values = list(data.values()) + [record_id]
            affected = self.execute_update(query, tuple(values))

            # Clear cache
            self.delete_cache(f"{table}:{record_id}")

            return affected > 0

        except Exception as e:
            self.log_error(f"Error updating record: {str(e)}")
            return False

    # ============================================
    # BATCH OPERATIONS
    # ============================================

    def batch_insert(self, table: str, data_list: List[Dict]) -> int:
        """
        Insert multiple records

        Args:
            table: Table name
            data_list: List of record dictionaries

        Returns:
            Number of inserted records
        """
        if not data_list:
            return 0

        try:
            inserted = 0
            for data in data_list:
                if self._insert(table, data):
                    inserted += 1

            self.log_info(f"Batch inserted {inserted} records to {table}")
            return inserted

        except Exception as e:
            self.log_error(f"Error in batch insert: {str(e)}")
            return 0

    def batch_delete(self, table: str, ids: List[Any]) -> int:
        """
        Delete multiple records

        Args:
            table: Table name
            ids: List of IDs to delete

        Returns:
            Number of deleted records
        """
        deleted = 0
        try:
            for id in ids:
                if self.delete(table, id):
                    deleted += 1

            self.log_info(f"Batch deleted {deleted} records from {table}")
            return deleted

        except Exception as e:
            self.log_error(f"Error in batch delete: {str(e)}")
            return deleted

    # ============================================
    # HELPER METHODS
    # ============================================

    def get_cache_key(self, *parts: str) -> str:
        """
        Build cache key from parts

        Args:
            *parts: Key parts

        Returns:
            Full cache key
        """
        return f"{self.cache_prefix}:{':'.join(str(p) for p in parts)}"

    def serialize(self, obj: Any) -> str:
        """Serialize object to JSON"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)

    def deserialize(self, data: str, data_type: type) -> Any:
        """Deserialize JSON to object"""
        try:
            obj = json.loads(data)
            if data_type == datetime:
                return datetime.fromisoformat(obj)
            return obj
        except:
            return data

    def paginate(
        self,
        items: List[Dict],
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Dict], int, int]:
        """
        Paginate items

        Args:
            items: Items to paginate
            page: Page number (1-indexed)
            per_page: Items per page

        Returns:
            Tuple of (items, total_pages, current_page)
        """
        total = len(items)
        total_pages = (total + per_page - 1) // per_page

        start = (page - 1) * per_page
        end = start + per_page

        return items[start:end], total_pages, page

    def apply_filters(
        self,
        items: List[Dict],
        filters: Dict[str, Any]
    ) -> List[Dict]:
        """
        Filter items by multiple criteria

        Args:
            items: Items to filter
            filters: Filter criteria

        Returns:
            Filtered items
        """
        filtered = items

        for key, value in filters.items():
            if isinstance(value, list):
                filtered = [item for item in filtered if item.get(key) in value]
            elif isinstance(value, dict):
                # Range filter
                if 'min' in value:
                    filtered = [item for item in filtered if item.get(key, 0) >= value['min']]
                if 'max' in value:
                    filtered = [item for item in filtered if item.get(key, 0) <= value['max']]
            else:
                filtered = [item for item in filtered if item.get(key) == value]

        return filtered

    def apply_sort(
        self,
        items: List[Dict],
        sort_by: str,
        descending: bool = False
    ) -> List[Dict]:
        """
        Sort items

        Args:
            items: Items to sort
            sort_by: Field to sort by
            descending: Sort descending

        Returns:
            Sorted items
        """
        return sorted(
            items,
            key=lambda x: x.get(sort_by, 0),
            reverse=descending
        )
