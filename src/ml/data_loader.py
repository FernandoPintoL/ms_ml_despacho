"""
Data Loader Module - Cargar datos desde SQL Server
Fase 2: Machine Learning
"""

import pandas as pd
import numpy as np
import pyodbc
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class DataLoader:
    """Carga datos desde ml.assignment_history en SQL Server"""

    def __init__(self, server, database, username, password):
        """
        Inicializar conexión a BD

        Args:
            server: Servidor SQL Server
            database: Nombre de BD
            username: Usuario
            password: Contraseña
        """
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.connection = None

    def connect(self):
        """Establecer conexión a BD"""
        try:
            connection_string = (
                f'DRIVER={{ODBC Driver 17 for SQL Server}};'
                f'SERVER={self.server};'
                f'DATABASE={self.database};'
                f'UID={self.username};'
                f'PWD={self.password}'
            )
            self.connection = pyodbc.connect(connection_string, timeout=10)
            logger.info(f"Conectado a {self.database} en {self.server}")
            return True
        except Exception as e:
            logger.error(f"Error conectando a BD: {e}")
            return False

    def disconnect(self):
        """Cerrar conexión a BD"""
        if self.connection:
            self.connection.close()
            logger.info("Conexión cerrada")

    def load_assignment_history(self):
        """
        Cargar datos desde ml.assignment_history

        Returns:
            DataFrame con los datos
        """
        if not self.connection:
            if not self.connect():
                return None

        try:
            query = """
            SELECT
                id,
                dispatch_id,
                request_timestamp,
                emergency_latitude,
                emergency_longitude,
                emergency_type,
                severity_level,
                hour_of_day,
                day_of_week,
                is_weekend,
                zone_code,
                available_ambulances_count,
                nearest_ambulance_distance_km,
                paramedics_available_count,
                paramedics_senior_count,
                paramedics_junior_count,
                nurses_available_count,
                active_dispatches_count,
                ambulances_busy_percentage,
                average_response_time_minutes,
                assigned_ambulance_id,
                assigned_paramedic_ids,
                actual_response_time_minutes,
                actual_travel_distance_km,
                patient_outcome,
                was_optimal,
                optimization_score,
                paramedic_satisfaction_rating,
                patient_satisfaction_rating,
                created_at
            FROM ml.assignment_history
            WHERE created_at IS NOT NULL
            ORDER BY created_at DESC
            """

            df = pd.read_sql(query, self.connection)
            logger.info(f"Cargados {len(df)} registros desde assignment_history")
            return df

        except Exception as e:
            logger.error(f"Error cargando datos: {e}")
            return None

    def load_with_filters(self, start_date=None, end_date=None, severity_level=None):
        """
        Cargar datos con filtros

        Args:
            start_date: Fecha inicial (datetime)
            end_date: Fecha final (datetime)
            severity_level: Nivel de severidad (int)

        Returns:
            DataFrame filtrado
        """
        if not self.connection:
            if not self.connect():
                return None

        try:
            where_clauses = ["created_at IS NOT NULL"]

            if start_date:
                where_clauses.append(f"created_at >= '{start_date.isoformat()}'")
            if end_date:
                where_clauses.append(f"created_at <= '{end_date.isoformat()}'")
            if severity_level:
                where_clauses.append(f"severity_level = {severity_level}")

            where_clause = " AND ".join(where_clauses)

            query = f"""
            SELECT
                id, dispatch_id, request_timestamp, emergency_latitude,
                emergency_longitude, emergency_type, severity_level, hour_of_day,
                day_of_week, is_weekend, zone_code, available_ambulances_count,
                nearest_ambulance_distance_km, paramedics_available_count,
                paramedics_senior_count, paramedics_junior_count,
                nurses_available_count, active_dispatches_count,
                ambulances_busy_percentage, average_response_time_minutes,
                assigned_ambulance_id, assigned_paramedic_ids,
                actual_response_time_minutes, actual_travel_distance_km,
                patient_outcome, was_optimal, optimization_score,
                paramedic_satisfaction_rating, patient_satisfaction_rating,
                created_at
            FROM ml.assignment_history
            WHERE {where_clause}
            ORDER BY created_at DESC
            """

            df = pd.read_sql(query, self.connection)
            logger.info(f"Cargados {len(df)} registros con filtros")
            return df

        except Exception as e:
            logger.error(f"Error con filtros: {e}")
            return None

    @staticmethod
    def get_data_stats(df):
        """
        Obtener estadísticas de los datos

        Args:
            df: DataFrame

        Returns:
            Diccionario con estadísticas
        """
        stats = {
            'total_records': len(df),
            'missing_values': df.isnull().sum().to_dict(),
            'optimal_count': (df['was_optimal'] == 1).sum() if 'was_optimal' in df.columns else 0,
            'optimal_rate': (df['was_optimal'] == 1).sum() / len(df) * 100 if 'was_optimal' in df.columns else 0,
            'date_range': {
                'start': df['created_at'].min() if 'created_at' in df.columns else None,
                'end': df['created_at'].max() if 'created_at' in df.columns else None
            },
            'columns': df.columns.tolist()
        }
        return stats


if __name__ == "__main__":
    # Ejemplo de uso
    loader = DataLoader(
        server='192.168.1.38',
        database='ms_ml_despacho',
        username='sa',
        password='1234'
    )

    if loader.connect():
        df = loader.load_assignment_history()
        if df is not None:
            stats = loader.get_data_stats(df)
            print(f"Total records: {stats['total_records']}")
            print(f"Optimal rate: {stats['optimal_rate']:.2f}%")
        loader.disconnect()
