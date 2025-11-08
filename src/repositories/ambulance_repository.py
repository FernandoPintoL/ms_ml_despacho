"""
Ambulance Repository
Manages ambulance records, availability, and location tracking
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

from .base_repository import BaseRepository


class AmbulanceRepository(BaseRepository):
    """
    Repository for managing ambulance records and operations

    Provides:
    - Ambulance CRUD operations
    - Availability management
    - Location tracking
    - Performance metrics
    """

    def __init__(self, db_connection=None, redis_client=None):
        """
        Initialize Ambulance Repository

        Args:
            db_connection: Database connection object
            redis_client: Redis client instance
        """
        super().__init__(db_connection, redis_client)
        self.table_name = 'ambulances'

    # ============================================
    # AMBULANCE OPERATIONS
    # ============================================

    def create_ambulance(self, ambulance_data: Dict[str, Any]) -> Optional[int]:
        """
        Create new ambulance record

        Args:
            ambulance_data: Dictionary with ambulance information:
                - code: str (unique identifier)
                - type: str (basic, advanced, mobile_icu)
                - base_station_id: int
                - driver_name: str
                - driver_phone: str
                - equipment_level: int (1-5)
                - status: str (available, in_transit, at_hospital, maintenance)
                - current_lat: float
                - current_lon: float

        Returns:
            Ambulance ID if successful, None otherwise
        """
        try:
            ambulance_data['created_at'] = datetime.utcnow().isoformat()
            ambulance_data['updated_at'] = datetime.utcnow().isoformat()

            if not ambulance_data.get('status'):
                ambulance_data['status'] = 'available'

            columns = ', '.join(ambulance_data.keys())
            placeholders = ', '.join(['%s'] * len(ambulance_data))
            query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"

            affected = self.execute_update(query, tuple(ambulance_data.values()))

            if affected > 0:
                self.log_info(f"Ambulance {ambulance_data.get('code')} created")
                self.clear_cache_pattern("available:*")
                return ambulance_data.get('id')

            return None

        except Exception as e:
            self.log_error(f"Error creating ambulance: {str(e)}")
            return None

    def get_ambulance(self, ambulance_id: int) -> Optional[Dict]:
        """
        Get ambulance by ID

        Args:
            ambulance_id: Ambulance ID

        Returns:
            Ambulance dictionary or None
        """
        try:
            cache_key = f"ambulance:{ambulance_id}"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            query = f"SELECT * FROM {self.table_name} WHERE id = %s"
            results = self.execute_query(query, (ambulance_id,))

            if results:
                ambulance = results[0]
                self.set_cache(cache_key, ambulance)
                return ambulance

            return None

        except Exception as e:
            self.log_error(f"Error getting ambulance: {str(e)}")
            return None

    def get_ambulance_by_code(self, code: str) -> Optional[Dict]:
        """
        Get ambulance by code

        Args:
            code: Ambulance code (unique identifier)

        Returns:
            Ambulance dictionary or None
        """
        try:
            cache_key = f"ambulance_code:{code}"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            query = f"SELECT * FROM {self.table_name} WHERE code = %s"
            results = self.execute_query(query, (code,))

            if results:
                ambulance = results[0]
                self.set_cache(cache_key, ambulance)
                return ambulance

            return None

        except Exception as e:
            self.log_error(f"Error getting ambulance by code: {str(e)}")
            return None

    # ============================================
    # AVAILABILITY OPERATIONS
    # ============================================

    def get_available_ambulances(self, ambulance_type: Optional[str] = None) -> List[Dict]:
        """
        Get all available ambulances

        Args:
            ambulance_type: Filter by type (optional)

        Returns:
            List of available ambulances
        """
        try:
            cache_key = f"available:ambulances:{ambulance_type or 'all'}"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            query = f"SELECT * FROM {self.table_name} WHERE status = 'available'"
            params = []

            if ambulance_type:
                query += " AND type = %s"
                params.append(ambulance_type)

            query += " ORDER BY created_at ASC"

            results = self.execute_query(query, tuple(params) if params else None)

            if results:
                self.set_cache(cache_key, results, ttl=120)  # 2 min cache for availability

            return results or []

        except Exception as e:
            self.log_error(f"Error getting available ambulances: {str(e)}")
            return []

    def get_available_ambulances_near(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10,
        limit: int = 5
    ) -> List[Dict]:
        """
        Get available ambulances near a location

        Args:
            latitude: Target latitude
            longitude: Target longitude
            radius_km: Search radius in kilometers
            limit: Maximum results

        Returns:
            List of nearby ambulances with distance
        """
        try:
            cache_key = f"nearby:ambulances:{latitude:.2f}:{longitude:.2f}:{radius_km}"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            # Using Haversine formula for distance calculation
            query = f"""
                SELECT *,
                    (6371 * acos(cos(radians(%s)) * cos(radians(current_lat)) *
                    cos(radians(current_lon) - radians(%s)) +
                    sin(radians(%s)) * sin(radians(current_lat)))) as distance_km
                FROM {self.table_name}
                WHERE status = 'available'
                    AND (6371 * acos(cos(radians(%s)) * cos(radians(current_lat)) *
                    cos(radians(current_lon) - radians(%s)) +
                    sin(radians(%s)) * sin(radians(current_lat)))) <= %s
                ORDER BY distance_km ASC
                LIMIT %s
            """

            params = [latitude, longitude, latitude, latitude, longitude, latitude, radius_km, limit]
            results = self.execute_query(query, tuple(params))

            if results:
                self.set_cache(cache_key, results, ttl=60)  # 1 min cache for location queries

            return results or []

        except Exception as e:
            self.log_error(f"Error getting nearby ambulances: {str(e)}")
            return []

    def set_ambulance_status(self, ambulance_id: int, status: str, metadata: Optional[Dict] = None) -> bool:
        """
        Update ambulance status

        Args:
            ambulance_id: Ambulance ID
            status: New status (available, in_transit, at_hospital, maintenance)
            metadata: Additional metadata

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

            values = list(update_data.values()) + [ambulance_id]
            affected = self.execute_update(query, tuple(values))

            if affected > 0:
                self.delete_cache(f"ambulance:{ambulance_id}")
                self.clear_cache_pattern("available:*")
                self.clear_cache_pattern("nearby:*")
                self.log_info(f"Ambulance {ambulance_id} status changed to {status}")
                return True

            return False

        except Exception as e:
            self.log_error(f"Error setting ambulance status: {str(e)}")
            return False

    # ============================================
    # LOCATION TRACKING
    # ============================================

    def update_ambulance_location(
        self,
        ambulance_id: int,
        latitude: float,
        longitude: float,
        accuracy: float = 0.0
    ) -> bool:
        """
        Update ambulance GPS location

        Args:
            ambulance_id: Ambulance ID
            latitude: Current latitude
            longitude: Current longitude
            accuracy: GPS accuracy in meters

        Returns:
            True if successful
        """
        try:
            update_data = {
                'current_lat': latitude,
                'current_lon': longitude,
                'last_location_update': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }

            if accuracy:
                update_data['gps_accuracy'] = accuracy

            updates = ', '.join([f"{k} = %s" for k in update_data.keys()])
            query = f"UPDATE {self.table_name} SET {updates} WHERE id = %s"

            values = list(update_data.values()) + [ambulance_id]
            affected = self.execute_update(query, tuple(values))

            if affected > 0:
                # Store location history
                self._store_location_history(ambulance_id, latitude, longitude)

                # Clear location-based caches
                self.clear_cache_pattern("nearby:*")
                self.delete_cache(f"ambulance:{ambulance_id}")

                return True

            return False

        except Exception as e:
            self.log_error(f"Error updating ambulance location: {str(e)}")
            return False

    def get_ambulance_location_history(self, ambulance_id: int, limit: int = 100) -> List[Dict]:
        """
        Get ambulance location history

        Args:
            ambulance_id: Ambulance ID
            limit: Maximum records

        Returns:
            List of location history records
        """
        try:
            cache_key = f"location_history:{ambulance_id}"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            query = """
                SELECT id, ambulance_id, latitude, longitude, timestamp
                FROM ambulance_locations
                WHERE ambulance_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """

            results = self.execute_query(query, (ambulance_id, limit))

            if results:
                self.set_cache(cache_key, results, ttl=1800)  # 30 min cache

            return results or []

        except Exception as e:
            self.log_error(f"Error getting location history: {str(e)}")
            return []

    def _store_location_history(self, ambulance_id: int, latitude: float, longitude: float) -> bool:
        """
        Store ambulance location history

        Args:
            ambulance_id: Ambulance ID
            latitude: Latitude
            longitude: Longitude

        Returns:
            True if successful
        """
        try:
            query = """
                INSERT INTO ambulance_locations (ambulance_id, latitude, longitude, timestamp)
                VALUES (%s, %s, %s, %s)
            """

            timestamp = datetime.utcnow().isoformat()
            affected = self.execute_update(query, (ambulance_id, latitude, longitude, timestamp))

            return affected > 0

        except Exception as e:
            self.log_error(f"Error storing location history: {str(e)}")
            return False

    # ============================================
    # PERFORMANCE METRICS
    # ============================================

    def get_ambulance_stats(self, ambulance_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Get ambulance performance statistics

        Args:
            ambulance_id: Ambulance ID
            days: Look back how many days

        Returns:
            Dictionary with performance metrics
        """
        try:
            cache_key = f"ambulance_stats:{ambulance_id}:{days}d"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            cutoff_time = (datetime.utcnow() - timedelta(days=days)).isoformat()

            query = f"""
                SELECT
                    COUNT(DISTINCT d.id) as total_dispatches,
                    COUNT(CASE WHEN d.status = 'completed' THEN 1 END) as completed_dispatches,
                    AVG(df.rating) as avg_rating,
                    AVG(TIMESTAMPDIFF(MINUTE, d.created_at, d.updated_at)) as avg_response_time,
                    COUNT(CASE WHEN df.rating >= 4 THEN 1 END) as high_ratings,
                    COUNT(CASE WHEN df.rating < 3 THEN 1 END) as low_ratings
                FROM {self.table_name} a
                LEFT JOIN dispatches d ON a.id = d.assigned_ambulance_id
                LEFT JOIN dispatch_feedback df ON d.id = df.dispatch_id
                WHERE a.id = %s AND d.created_at >= %s
            """

            results = self.execute_query(query, (ambulance_id, cutoff_time))

            if results:
                stats = results[0]
                self.set_cache(cache_key, stats, ttl=3600)
                return stats

            return {}

        except Exception as e:
            self.log_error(f"Error getting ambulance stats: {str(e)}")
            return {}

    def get_ambulance_type_distribution(self) -> Dict[str, int]:
        """
        Get distribution of ambulance types

        Returns:
            Dictionary with type counts
        """
        try:
            cache_key = "ambulance_type_distribution"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            query = f"""
                SELECT type, COUNT(*) as count
                FROM {self.table_name}
                GROUP BY type
                ORDER BY count DESC
            """

            results = self.execute_query(query)

            distribution = {row['type']: row['count'] for row in results}

            if distribution:
                self.set_cache(cache_key, distribution, ttl=3600)

            return distribution

        except Exception as e:
            self.log_error(f"Error getting ambulance type distribution: {str(e)}")
            return {}

    def get_fleet_status(self) -> Dict[str, Any]:
        """
        Get overall fleet status

        Returns:
            Dictionary with fleet statistics
        """
        try:
            cache_key = "fleet_status"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            query = f"""
                SELECT
                    COUNT(*) as total_ambulances,
                    COUNT(CASE WHEN status = 'available' THEN 1 END) as available,
                    COUNT(CASE WHEN status = 'in_transit' THEN 1 END) as in_transit,
                    COUNT(CASE WHEN status = 'at_hospital' THEN 1 END) as at_hospital,
                    COUNT(CASE WHEN status = 'maintenance' THEN 1 END) as maintenance
                FROM {self.table_name}
            """

            results = self.execute_query(query)

            if results:
                status = results[0]
                # Calculate availability percentage
                total = status['total_ambulances'] or 1
                status['availability_percent'] = (status['available'] / total * 100) if total > 0 else 0
                self.set_cache(cache_key, status, ttl=120)
                return status

            return {}

        except Exception as e:
            self.log_error(f"Error getting fleet status: {str(e)}")
            return {}

    # ============================================
    # MAINTENANCE OPERATIONS
    # ============================================

    def schedule_maintenance(
        self,
        ambulance_id: int,
        start_time: datetime,
        end_time: datetime,
        reason: str
    ) -> bool:
        """
        Schedule maintenance for ambulance

        Args:
            ambulance_id: Ambulance ID
            start_time: Maintenance start time
            end_time: Maintenance end time
            reason: Maintenance reason

        Returns:
            True if successful
        """
        try:
            # Update ambulance status
            maintenance_data = {
                'status': 'maintenance',
                'updated_at': datetime.utcnow().isoformat(),
                'maintenance_until': end_time.isoformat()
            }

            updates = ', '.join([f"{k} = %s" for k in maintenance_data.keys()])
            query = f"UPDATE {self.table_name} SET {updates} WHERE id = %s"

            values = list(maintenance_data.values()) + [ambulance_id]
            affected = self.execute_update(query, tuple(values))

            if affected > 0:
                # Store maintenance record
                maint_query = """
                    INSERT INTO ambulance_maintenance (ambulance_id, start_time, end_time, reason, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                """

                self.execute_update(maint_query, (
                    ambulance_id,
                    start_time.isoformat(),
                    end_time.isoformat(),
                    reason,
                    datetime.utcnow().isoformat()
                ))

                self.delete_cache(f"ambulance:{ambulance_id}")
                self.clear_cache_pattern("available:*")
                self.clear_cache_pattern("fleet_status")

                self.log_info(f"Maintenance scheduled for ambulance {ambulance_id}")
                return True

            return False

        except Exception as e:
            self.log_error(f"Error scheduling maintenance: {str(e)}")
            return False

    def complete_maintenance(self, ambulance_id: int) -> bool:
        """
        Mark ambulance maintenance as complete

        Args:
            ambulance_id: Ambulance ID

        Returns:
            True if successful
        """
        try:
            update_data = {
                'status': 'available',
                'updated_at': datetime.utcnow().isoformat(),
                'maintenance_until': None
            }

            updates = ', '.join([f"{k} = %s" for k in update_data.keys()])
            query = f"UPDATE {self.table_name} SET {updates} WHERE id = %s"

            values = list(update_data.values()) + [ambulance_id]
            affected = self.execute_update(query, tuple(values))

            if affected > 0:
                self.delete_cache(f"ambulance:{ambulance_id}")
                self.clear_cache_pattern("available:*")
                self.clear_cache_pattern("fleet_status")
                self.log_info(f"Maintenance completed for ambulance {ambulance_id}")
                return True

            return False

        except Exception as e:
            self.log_error(f"Error completing maintenance: {str(e)}")
            return False
