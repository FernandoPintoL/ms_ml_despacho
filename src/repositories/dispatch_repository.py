"""
Dispatch Repository
Manages dispatch records, history, and related data operations
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

from .base_repository import BaseRepository


class DispatchRepository(BaseRepository):
    """
    Repository for managing dispatch records and operations

    Provides:
    - Dispatch CRUD operations
    - Historical dispatch queries
    - Dispatch statistics and analytics
    - Real-time dispatch tracking
    """

    def __init__(self, db_connection=None, redis_client=None):
        """
        Initialize Dispatch Repository

        Args:
            db_connection: Database connection object
            redis_client: Redis client instance
        """
        super().__init__(db_connection, redis_client)
        self.table_name = 'dispatches'

    # ============================================
    # DISPATCH OPERATIONS
    # ============================================

    def create_dispatch(self, dispatch_data: Dict[str, Any]) -> Optional[int]:
        """
        Create new dispatch record

        Args:
            dispatch_data: Dictionary with dispatch information:
                - patient_name: str
                - patient_age: int
                - patient_lat: float
                - patient_lon: float
                - description: str
                - severity_level: int (1-5)
                - timestamp: datetime
                - assigned_ambulance_id: int (optional)
                - hospital_id: int (optional)
                - status: str (enum: pending, assigned, in_transit, arrived, completed, cancelled)

        Returns:
            Dispatch ID if successful, None otherwise
        """
        try:
            # Add metadata
            dispatch_data['created_at'] = datetime.utcnow().isoformat()
            dispatch_data['updated_at'] = datetime.utcnow().isoformat()

            if not dispatch_data.get('status'):
                dispatch_data['status'] = 'pending'

            # Insert record
            columns = ', '.join(dispatch_data.keys())
            placeholders = ', '.join(['%s'] * len(dispatch_data))
            query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"

            affected = self.execute_update(query, tuple(dispatch_data.values()))

            if affected > 0:
                self.log_info(f"Dispatch created for patient {dispatch_data.get('patient_name')}")
                # Clear cache of all dispatches
                self.clear_cache_pattern("recent:*")
                return dispatch_data.get('id')

            return None

        except Exception as e:
            self.log_error(f"Error creating dispatch: {str(e)}")
            return None

    def get_dispatch(self, dispatch_id: int) -> Optional[Dict]:
        """
        Get dispatch by ID

        Args:
            dispatch_id: Dispatch ID

        Returns:
            Dispatch dictionary or None
        """
        try:
            cache_key = f"dispatch:{dispatch_id}"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            query = f"SELECT * FROM {self.table_name} WHERE id = %s"
            results = self.execute_query(query, (dispatch_id,))

            if results:
                dispatch = results[0]
                self.set_cache(cache_key, dispatch)
                return dispatch

            return None

        except Exception as e:
            self.log_error(f"Error getting dispatch: {str(e)}")
            return None

    def get_recent_dispatches(self, limit: int = 50, hours: int = 24) -> List[Dict]:
        """
        Get recent dispatches within specified hours

        Args:
            limit: Maximum number of records
            hours: Look back how many hours

        Returns:
            List of dispatch records
        """
        try:
            cache_key = f"recent:dispatches:{hours}h"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

            query = f"""
                SELECT * FROM {self.table_name}
                WHERE created_at >= %s
                ORDER BY created_at DESC
                LIMIT %s
            """

            results = self.execute_query(query, (cutoff_time, limit))

            if results:
                self.set_cache(cache_key, results, ttl=300)  # 5 min cache for recent

            return results or []

        except Exception as e:
            self.log_error(f"Error getting recent dispatches: {str(e)}")
            return []

    def get_dispatches_by_ambulance(self, ambulance_id: int, limit: int = 20) -> List[Dict]:
        """
        Get all dispatches assigned to ambulance

        Args:
            ambulance_id: Ambulance ID
            limit: Maximum number of records

        Returns:
            List of dispatch records
        """
        try:
            cache_key = f"ambulance:{ambulance_id}:dispatches"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            query = f"""
                SELECT * FROM {self.table_name}
                WHERE assigned_ambulance_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """

            results = self.execute_query(query, (ambulance_id, limit))

            if results:
                self.set_cache(cache_key, results, ttl=600)

            return results or []

        except Exception as e:
            self.log_error(f"Error getting ambulance dispatches: {str(e)}")
            return []

    def get_dispatches_by_status(self, status: str, limit: int = 50) -> List[Dict]:
        """
        Get dispatches by status

        Args:
            status: Dispatch status (pending, assigned, in_transit, arrived, completed, cancelled)
            limit: Maximum number of records

        Returns:
            List of dispatch records
        """
        try:
            cache_key = f"status:{status}:dispatches"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            query = f"""
                SELECT * FROM {self.table_name}
                WHERE status = %s
                ORDER BY created_at DESC
                LIMIT %s
            """

            results = self.execute_query(query, (status, limit))

            if results:
                self.set_cache(cache_key, results, ttl=300)

            return results or []

        except Exception as e:
            self.log_error(f"Error getting dispatches by status: {str(e)}")
            return []

    def update_dispatch_status(self, dispatch_id: int, status: str, metadata: Optional[Dict] = None) -> bool:
        """
        Update dispatch status

        Args:
            dispatch_id: Dispatch ID
            status: New status
            metadata: Additional metadata to store

        Returns:
            True if successful
        """
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.utcnow().isoformat()
            }

            if metadata:
                update_data['metadata'] = json.dumps(metadata)

            updates = ', '.join([f"{k} = %s" for k in update_data.keys()])
            query = f"UPDATE {self.table_name} SET {updates} WHERE id = %s"

            values = list(update_data.values()) + [dispatch_id]
            affected = self.execute_update(query, tuple(values))

            if affected > 0:
                # Clear cache for this dispatch
                self.delete_cache(f"dispatch:{dispatch_id}")
                self.clear_cache_pattern("recent:*")
                self.clear_cache_pattern(f"status:*")
                self.log_info(f"Dispatch {dispatch_id} status updated to {status}")
                return True

            return False

        except Exception as e:
            self.log_error(f"Error updating dispatch status: {str(e)}")
            return False

    def assign_ambulance(self, dispatch_id: int, ambulance_id: int, route_info: Dict) -> bool:
        """
        Assign ambulance to dispatch

        Args:
            dispatch_id: Dispatch ID
            ambulance_id: Ambulance ID
            route_info: Route information from optimizer

        Returns:
            True if successful
        """
        try:
            update_data = {
                'assigned_ambulance_id': ambulance_id,
                'status': 'assigned',
                'updated_at': datetime.utcnow().isoformat(),
                'route_info': json.dumps(route_info)
            }

            updates = ', '.join([f"{k} = %s" for k in update_data.keys()])
            query = f"UPDATE {self.table_name} SET {updates} WHERE id = %s"

            values = list(update_data.values()) + [dispatch_id]
            affected = self.execute_update(query, tuple(values))

            if affected > 0:
                self.delete_cache(f"dispatch:{dispatch_id}")
                self.clear_cache_pattern("recent:*")
                self.log_info(f"Ambulance {ambulance_id} assigned to dispatch {dispatch_id}")
                return True

            return False

        except Exception as e:
            self.log_error(f"Error assigning ambulance: {str(e)}")
            return False

    # ============================================
    # DISPATCH STATISTICS
    # ============================================

    def get_dispatch_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get dispatch statistics for time period

        Args:
            hours: Look back how many hours

        Returns:
            Dictionary with statistics
        """
        try:
            cache_key = f"stats:dispatches:{hours}h"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

            query = f"""
                SELECT
                    COUNT(*) as total,
                    AVG(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completion_rate,
                    COUNT(CASE WHEN severity_level = 1 THEN 1 END) as critical_count,
                    COUNT(CASE WHEN severity_level = 2 THEN 1 END) as high_count,
                    COUNT(CASE WHEN severity_level = 3 THEN 1 END) as medium_count,
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,
                    COUNT(CASE WHEN status = 'in_transit' THEN 1 END) as in_transit_count
                FROM {self.table_name}
                WHERE created_at >= %s
            """

            results = self.execute_query(query, (cutoff_time,))

            if results:
                stats = results[0]
                self.set_cache(cache_key, stats, ttl=600)
                return stats

            return {}

        except Exception as e:
            self.log_error(f"Error getting dispatch statistics: {str(e)}")
            return {}

    def get_severity_distribution(self, hours: int = 24) -> Dict[int, int]:
        """
        Get distribution of severity levels

        Args:
            hours: Look back how many hours

        Returns:
            Dictionary with severity counts
        """
        try:
            cache_key = f"severity:distribution:{hours}h"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

            query = f"""
                SELECT severity_level, COUNT(*) as count
                FROM {self.table_name}
                WHERE created_at >= %s
                GROUP BY severity_level
                ORDER BY severity_level
            """

            results = self.execute_query(query, (cutoff_time,))

            distribution = {row['severity_level']: row['count'] for row in results}

            if distribution:
                self.set_cache(cache_key, distribution, ttl=600)

            return distribution

        except Exception as e:
            self.log_error(f"Error getting severity distribution: {str(e)}")
            return {}

    def get_response_times_stats(self, hours: int = 24) -> Dict[str, float]:
        """
        Get response time statistics

        Args:
            hours: Look back how many hours

        Returns:
            Dictionary with response time metrics
        """
        try:
            cache_key = f"response_times:{hours}h"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

            # This assumes a response_time field in dispatches
            query = f"""
                SELECT
                    AVG(response_time) as avg_response,
                    MIN(response_time) as min_response,
                    MAX(response_time) as max_response,
                    STDDEV(response_time) as stddev_response
                FROM {self.table_name}
                WHERE created_at >= %s AND status = 'completed'
            """

            results = self.execute_query(query, (cutoff_time,))

            if results:
                stats = results[0]
                self.set_cache(cache_key, stats, ttl=900)  # 15 min cache
                return stats

            return {}

        except Exception as e:
            self.log_error(f"Error getting response time statistics: {str(e)}")
            return {}

    # ============================================
    # DISPATCH FEEDBACK & RATINGS
    # ============================================

    def add_dispatch_feedback(self, dispatch_id: int, feedback: Dict[str, Any]) -> bool:
        """
        Add feedback/rating for dispatch

        Args:
            dispatch_id: Dispatch ID
            feedback: Dictionary with:
                - rating: int (1-5)
                - comment: str (optional)
                - response_time_minutes: int
                - patient_outcome: str

        Returns:
            True if successful
        """
        try:
            feedback['dispatch_id'] = dispatch_id
            feedback['created_at'] = datetime.utcnow().isoformat()

            columns = ', '.join(feedback.keys())
            placeholders = ', '.join(['%s'] * len(feedback))
            query = f"INSERT INTO dispatch_feedback ({columns}) VALUES ({placeholders})"

            affected = self.execute_update(query, tuple(feedback.values()))

            if affected > 0:
                self.delete_cache(f"dispatch:{dispatch_id}")
                self.log_info(f"Feedback added for dispatch {dispatch_id}")
                return True

            return False

        except Exception as e:
            self.log_error(f"Error adding feedback: {str(e)}")
            return False

    def get_dispatch_feedback(self, dispatch_id: int) -> Optional[Dict]:
        """
        Get feedback for dispatch

        Args:
            dispatch_id: Dispatch ID

        Returns:
            Feedback dictionary or None
        """
        try:
            cache_key = f"feedback:dispatch:{dispatch_id}"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            query = "SELECT * FROM dispatch_feedback WHERE dispatch_id = %s"
            results = self.execute_query(query, (dispatch_id,))

            if results:
                feedback = results[0]
                self.set_cache(cache_key, feedback)
                return feedback

            return None

        except Exception as e:
            self.log_error(f"Error getting feedback: {str(e)}")
            return None

    def get_average_rating(self, ambulance_id: int = None, hours: int = None) -> Optional[float]:
        """
        Get average rating for ambulance or overall

        Args:
            ambulance_id: Ambulance ID (optional for overall rating)
            hours: Look back how many hours (optional)

        Returns:
            Average rating or None
        """
        try:
            query = """
                SELECT AVG(df.rating) as avg_rating
                FROM dispatch_feedback df
                JOIN dispatches d ON df.dispatch_id = d.id
                WHERE 1=1
            """

            params = []

            if ambulance_id:
                query += " AND d.assigned_ambulance_id = %s"
                params.append(ambulance_id)

            if hours:
                cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
                query += " AND d.created_at >= %s"
                params.append(cutoff)

            results = self.execute_query(query, tuple(params) if params else None)

            if results and results[0]['avg_rating']:
                return float(results[0]['avg_rating'])

            return None

        except Exception as e:
            self.log_error(f"Error getting average rating: {str(e)}")
            return None

    # ============================================
    # CLEANUP OPERATIONS
    # ============================================

    def archive_old_dispatches(self, days: int = 30) -> int:
        """
        Archive completed dispatches older than specified days

        Args:
            days: Archive records older than this many days

        Returns:
            Number of archived records
        """
        try:
            cutoff_time = (datetime.utcnow() - timedelta(days=days)).isoformat()

            # Move to archive table
            query = f"""
                INSERT INTO dispatches_archive
                SELECT * FROM {self.table_name}
                WHERE created_at < %s AND status = 'completed'
            """

            self.execute_update(query, (cutoff_time,))

            # Delete from main table
            delete_query = f"""
                DELETE FROM {self.table_name}
                WHERE created_at < %s AND status = 'completed'
            """

            affected = self.execute_update(delete_query, (cutoff_time,))

            # Clear cache
            self.clear_cache_pattern("recent:*")
            self.clear_cache_pattern("stats:*")

            self.log_info(f"Archived {affected} old dispatches")
            return affected

        except Exception as e:
            self.log_error(f"Error archiving old dispatches: {str(e)}")
            return 0
