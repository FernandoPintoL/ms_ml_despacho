"""
Assignment History Repository
Manages assignment history records and data for ML training
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

from .base_repository import BaseRepository


class AssignmentHistoryRepository(BaseRepository):
    """
    Repository para manejar histórico de asignaciones

    Propósito:
    - Almacenar cada asignación de ambulancia y personal
    - Proporcionar datos para entrenar modelos ML
    - Registrar métricas de desempeño
    """

    def __init__(self, db_connection=None, redis_client=None):
        """
        Inicializar repositorio

        Args:
            db_connection: Conexión a la base de datos
            redis_client: Cliente de Redis para caché
        """
        super().__init__(db_connection, redis_client)
        self.table_name = 'ml.assignment_history'

    # ============================================
    # CREATE OPERATIONS
    # ============================================

    def create_assignment_history(self, assignment_data: Dict[str, Any]) -> Optional[int]:
        """
        Crear registro de histórico de asignación

        Args:
            assignment_data: Dictionary con:
                - dispatch_id: INT
                - emergency_latitude: DECIMAL
                - emergency_longitude: DECIMAL
                - emergency_type: VARCHAR
                - severity_level: INT
                - zone_code: VARCHAR (opcional)
                - available_ambulances_count: INT
                - nearest_ambulance_distance_km: DECIMAL (opcional)
                - available_ambulances_json: JSON (opcional)
                - paramedics_available_count: INT
                - assigned_ambulance_id: INT
                - assigned_paramedic_ids: JSON
                - assigned_paramedic_levels: JSON (opcional)
                - actual_response_time_minutes: DECIMAL (opcional, se llena después)
                - patient_outcome: VARCHAR (opcional, se llena después)

        Returns:
            ID del registro creado, o None si falló
        """
        try:
            # Agregar metadatos
            assignment_data['created_at'] = datetime.utcnow()
            assignment_data['updated_at'] = datetime.utcnow()
            assignment_data['request_timestamp'] = datetime.utcnow()

            # Agregar contexto temporal si no está presente
            if 'hour_of_day' not in assignment_data:
                assignment_data['hour_of_day'] = datetime.utcnow().hour

            if 'day_of_week' not in assignment_data:
                day_of_week = datetime.utcnow().weekday()
                assignment_data['day_of_week'] = day_of_week
                assignment_data['is_weekend'] = 1 if day_of_week >= 5 else 0

            if 'latitude' not in assignment_data:
                assignment_data['latitude'] = assignment_data.get('emergency_latitude')
                assignment_data['longitude'] = assignment_data.get('emergency_longitude')

            if 'created_by' not in assignment_data:
                assignment_data['created_by'] = 'SYSTEM'

            # Preparar columnas y valores
            columns = ', '.join(assignment_data.keys())
            placeholders = ', '.join(['%s'] * len(assignment_data))
            query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"

            # Ejecutar insert
            affected = self.execute_update(query, tuple(assignment_data.values()))

            if affected > 0:
                self.log_info(f"Assignment history created for dispatch {assignment_data.get('dispatch_id')}")
                return affected  # En SQL Server, retorna el número de filas afectadas

            return None

        except Exception as e:
            self.log_error(f"Error creating assignment history: {str(e)}")
            return None

    # ============================================
    # READ OPERATIONS
    # ============================================

    def get_assignment_by_dispatch(self, dispatch_id: int) -> Optional[Dict]:
        """
        Obtener histórico de asignación por dispatch_id

        Args:
            dispatch_id: ID del despacho

        Returns:
            Diccionario con datos de asignación, o None
        """
        try:
            cache_key = f"assignment_history:{dispatch_id}"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            query = f"""
                SELECT TOP 1 *
                FROM {self.table_name}
                WHERE dispatch_id = %s
                ORDER BY created_at DESC
            """

            results = self.execute_query(query, (dispatch_id,))

            if results:
                assignment = results[0]
                self.set_cache(cache_key, assignment, ttl=3600)
                return assignment

            return None

        except Exception as e:
            self.log_error(f"Error getting assignment by dispatch: {str(e)}")
            return None

    def get_recent_assignments(
        self,
        limit: int = 100,
        hours: int = 24
    ) -> List[Dict]:
        """
        Obtener asignaciones recientes

        Args:
            limit: Número máximo de registros
            hours: Últimas N horas

        Returns:
            Lista de asignaciones
        """
        try:
            cache_key = f"recent_assignments:{hours}h:{limit}"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            cutoff_time = (datetime.utcnow() - timedelta(hours=hours))

            query = f"""
                SELECT TOP {limit} *
                FROM {self.table_name}
                WHERE created_at >= %s
                ORDER BY created_at DESC
            """

            results = self.execute_query(query, (cutoff_time,))

            if results:
                self.set_cache(cache_key, results, ttl=300)

            return results or []

        except Exception as e:
            self.log_error(f"Error getting recent assignments: {str(e)}")
            return []

    def get_assignments_by_ambulance(
        self,
        ambulance_id: int,
        limit: int = 50
    ) -> List[Dict]:
        """
        Obtener histórico de asignaciones de una ambulancia

        Args:
            ambulance_id: ID de la ambulancia
            limit: Número máximo de registros

        Returns:
            Lista de asignaciones
        """
        try:
            cache_key = f"ambulance_history:{ambulance_id}"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            query = f"""
                SELECT TOP {limit} *
                FROM {self.table_name}
                WHERE assigned_ambulance_id = %s
                ORDER BY created_at DESC
            """

            results = self.execute_query(query, (ambulance_id,))

            if results:
                self.set_cache(cache_key, results, ttl=600)

            return results or []

        except Exception as e:
            self.log_error(f"Error getting ambulance assignments: {str(e)}")
            return []

    def get_assignments_by_severity(
        self,
        severity_level: int,
        limit: int = 50,
        hours: int = 168  # 1 semana
    ) -> List[Dict]:
        """
        Obtener asignaciones por severidad

        Args:
            severity_level: Nivel de severidad (1-5)
            limit: Número máximo de registros
            hours: Período de búsqueda en horas

        Returns:
            Lista de asignaciones
        """
        try:
            cutoff_time = (datetime.utcnow() - timedelta(hours=hours))

            query = f"""
                SELECT TOP {limit} *
                FROM {self.table_name}
                WHERE severity_level = %s
                AND created_at >= %s
                ORDER BY created_at DESC
            """

            results = self.execute_query(query, (severity_level, cutoff_time))

            return results or []

        except Exception as e:
            self.log_error(f"Error getting assignments by severity: {str(e)}")
            return []

    def get_assignments_for_training(
        self,
        min_samples: int = 100,
        include_optimal_only: bool = False
    ) -> List[Dict]:
        """
        Obtener asignaciones para entrenar modelos ML

        Args:
            min_samples: Mínimo de muestras requeridas
            include_optimal_only: Incluir solo asignaciones óptimas

        Returns:
            Lista de asignaciones con complete data para entrenar
        """
        try:
            query = f"""
                SELECT *
                FROM {self.table_name}
                WHERE created_at >= DATEADD(DAY, -30, GETUTCDATE())
            """

            if include_optimal_only:
                query += " AND was_optimal = 1"

            query += " ORDER BY created_at DESC"

            results = self.execute_query(query, ())

            if results and len(results) >= min_samples:
                return results

            return results or []

        except Exception as e:
            self.log_error(f"Error getting training assignments: {str(e)}")
            return []

    # ============================================
    # UPDATE OPERATIONS
    # ============================================

    def update_assignment_outcome(
        self,
        assignment_id: int,
        outcome_data: Dict[str, Any]
    ) -> bool:
        """
        Actualizar información post-asignación

        Args:
            assignment_id: ID del registro
            outcome_data: Dictionary con:
                - actual_response_time_minutes: DECIMAL
                - actual_travel_distance_km: DECIMAL
                - patient_outcome: VARCHAR
                - hospital_destination_id: INT (opcional)
                - was_optimal: BIT
                - optimization_score: DECIMAL

        Returns:
            True si fue exitoso
        """
        try:
            outcome_data['updated_at'] = datetime.utcnow()

            updates = ', '.join([f"{k} = %s" for k in outcome_data.keys()])
            query = f"UPDATE {self.table_name} SET {updates} WHERE id = %s"

            values = list(outcome_data.values()) + [assignment_id]
            affected = self.execute_update(query, tuple(values))

            if affected > 0:
                # Invalidar cache
                self.clear_cache_pattern(f"assignment_history:*")
                self.log_info(f"Assignment {assignment_id} outcome updated")
                return True

            return False

        except Exception as e:
            self.log_error(f"Error updating assignment outcome: {str(e)}")
            return False

    def add_satisfaction_rating(
        self,
        assignment_id: int,
        patient_rating: Optional[int] = None,
        paramedic_rating: Optional[int] = None
    ) -> bool:
        """
        Agregar ratings de satisfacción

        Args:
            assignment_id: ID del registro
            patient_rating: Rating del paciente (1-5)
            paramedic_rating: Rating del paramédico (1-5)

        Returns:
            True si fue exitoso
        """
        try:
            update_data = {'updated_at': datetime.utcnow()}

            if patient_rating is not None:
                update_data['patient_satisfaction_rating'] = patient_rating

            if paramedic_rating is not None:
                update_data['paramedic_satisfaction_rating'] = paramedic_rating

            return self.update_assignment_outcome(assignment_id, update_data)

        except Exception as e:
            self.log_error(f"Error adding satisfaction rating: {str(e)}")
            return False

    # ============================================
    # STATISTICS & ANALYTICS
    # ============================================

    def get_assignment_statistics(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Obtener estadísticas de asignaciones

        Args:
            hours: Período en horas

        Returns:
            Diccionario con estadísticas
        """
        try:
            cutoff_time = (datetime.utcnow() - timedelta(hours=hours))

            query = f"""
                SELECT
                    COUNT(*) as total_assignments,
                    COUNT(CASE WHEN was_optimal = 1 THEN 1 END) as optimal_count,
                    AVG(actual_response_time_minutes) as avg_response_time,
                    MIN(actual_response_time_minutes) as min_response_time,
                    MAX(actual_response_time_minutes) as max_response_time,
                    AVG(CAST(optimization_score as FLOAT)) as avg_optimization_score,
                    COUNT(DISTINCT assigned_ambulance_id) as unique_ambulances,
                    AVG(CAST(patient_satisfaction_rating as FLOAT)) as avg_patient_satisfaction
                FROM {self.table_name}
                WHERE created_at >= %s
            """

            results = self.execute_query(query, (cutoff_time,))

            if results:
                return results[0]

            return {}

        except Exception as e:
            self.log_error(f"Error getting assignment statistics: {str(e)}")
            return {}

    def get_ambulance_performance(
        self,
        ambulance_id: int,
        hours: int = 168
    ) -> Dict[str, Any]:
        """
        Obtener desempeño de una ambulancia

        Args:
            ambulance_id: ID de la ambulancia
            hours: Período en horas

        Returns:
            Diccionario con métricas de desempeño
        """
        try:
            cutoff_time = (datetime.utcnow() - timedelta(hours=hours))

            query = f"""
                SELECT
                    assigned_ambulance_id,
                    COUNT(*) as total_assignments,
                    COUNT(CASE WHEN was_optimal = 1 THEN 1 END) as optimal_assignments,
                    AVG(actual_response_time_minutes) as avg_response_time,
                    AVG(CAST(optimization_score as FLOAT)) as avg_optimization_score,
                    AVG(CAST(patient_satisfaction_rating as FLOAT)) as avg_patient_satisfaction
                FROM {self.table_name}
                WHERE assigned_ambulance_id = %s
                AND created_at >= %s
                GROUP BY assigned_ambulance_id
            """

            results = self.execute_query(query, (ambulance_id, cutoff_time))

            if results:
                return results[0]

            return {}

        except Exception as e:
            self.log_error(f"Error getting ambulance performance: {str(e)}")
            return {}

    def get_severity_distribution(
        self,
        hours: int = 168
    ) -> Dict[int, int]:
        """
        Obtener distribución de asignaciones por severidad

        Args:
            hours: Período en horas

        Returns:
            Diccionario {severidad: count}
        """
        try:
            cutoff_time = (datetime.utcnow() - timedelta(hours=hours))

            query = f"""
                SELECT severity_level, COUNT(*) as count
                FROM {self.table_name}
                WHERE created_at >= %s
                GROUP BY severity_level
                ORDER BY severity_level
            """

            results = self.execute_query(query, (cutoff_time,))

            distribution = {row['severity_level']: row['count'] for row in results}

            return distribution

        except Exception as e:
            self.log_error(f"Error getting severity distribution: {str(e)}")
            return {}

    def get_optimal_assignment_rate(
        self,
        hours: int = 168
    ) -> Optional[float]:
        """
        Obtener tasa de asignaciones óptimas (%)

        Args:
            hours: Período en horas

        Returns:
            Porcentaje de asignaciones óptimas, o None
        """
        try:
            cutoff_time = (datetime.utcnow() - timedelta(hours=hours))

            query = f"""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN was_optimal = 1 THEN 1 END) as optimal
                FROM {self.table_name}
                WHERE created_at >= %s
            """

            results = self.execute_query(query, (cutoff_time,))

            if results:
                row = results[0]
                total = row['total']
                optimal = row['optimal']

                if total > 0:
                    return (optimal / total) * 100

            return None

        except Exception as e:
            self.log_error(f"Error calculating optimal rate: {str(e)}")
            return None

    # ============================================
    # CLEANUP OPERATIONS
    # ============================================

    def archive_old_assignments(self, days: int = 90) -> int:
        """
        Archivar asignaciones antiguas (opcional)

        Args:
            days: Archivar registros más antiguos que N días

        Returns:
            Número de registros archivados
        """
        try:
            cutoff_time = (datetime.utcnow() - timedelta(days=days))

            # En producción, mover a tabla archive
            # Por ahora, solo loguear
            query = f"""
                SELECT COUNT(*) as count
                FROM {self.table_name}
                WHERE created_at < %s
            """

            results = self.execute_query(query, (cutoff_time,))

            if results:
                count = results[0]['count']
                self.log_info(f"Found {count} assignments older than {days} days")
                return count

            return 0

        except Exception as e:
            self.log_error(f"Error archiving assignments: {str(e)}")
            return 0
