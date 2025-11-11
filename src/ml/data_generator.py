"""
Data Generator Module - Generar datos de simulacion para Fase 2
Genera 500 registros realistas para entrenar el modelo XGBoost
"""

import pandas as pd
import numpy as np
import pyodbc
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


class DataGenerator:
    """Genera datos de simulacion realistas para entrenamiento ML"""

    def __init__(self, server: str, database: str, username: str, password: str):
        """
        Inicializar generador de datos

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

    def connect(self) -> bool:
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

    @staticmethod
    def generate_synthetic_data(num_records: int = 500) -> pd.DataFrame:
        """
        Generar datos sintéticos realistas

        Args:
            num_records: Número de registros a generar

        Returns:
            DataFrame con datos sintéticos
        """
        np.random.seed(42)  # Para reproducibilidad

        # Generar coordenadas
        emergency_lats = np.random.uniform(4.5, 5.0, num_records)
        emergency_lons = np.random.uniform(-74.3, -74.0, num_records)
        ambulance_lats = np.random.uniform(4.5, 5.0, num_records)
        ambulance_lons = np.random.uniform(-74.3, -74.0, num_records)

        data = {
            'dispatch_id': np.arange(1, num_records + 1),
            'request_timestamp': [
                datetime.now() - timedelta(days=np.random.randint(0, 180),
                                          hours=np.random.randint(0, 24),
                                          minutes=np.random.randint(0, 60))
                for _ in range(num_records)
            ],
            'emergency_latitude': emergency_lats,
            'emergency_longitude': emergency_lons,
            'emergency_type': np.random.choice(
                ['trauma', 'cardiac', 'respiratory', 'stroke', 'burn', 'fracture', 'other'],
                num_records,
                p=[0.25, 0.20, 0.15, 0.15, 0.10, 0.10, 0.05]
            ),
            'severity_level': np.random.choice([1, 2, 3, 4, 5], num_records, p=[0.1, 0.15, 0.3, 0.3, 0.15]),
            'hour_of_day': np.random.randint(0, 24, num_records),
            'day_of_week': np.random.randint(0, 7, num_records),
            'is_weekend': np.random.choice([0, 1], num_records, p=[0.7, 0.3]),
            'latitude': ambulance_lats,  # Ambulance latitude (required)
            'longitude': ambulance_lons,  # Ambulance longitude (required)
            'zone_code': np.random.choice(
                ['ZONA_1', 'ZONA_2', 'ZONA_3', 'ZONA_4', 'ZONA_5'],
                num_records,
                p=[0.25, 0.25, 0.2, 0.2, 0.1]
            ),
            'available_ambulances_count': np.random.randint(1, 12, num_records),
            'nearest_ambulance_distance_km': np.random.uniform(0.1, 15.0, num_records),
            'paramedics_available_count': np.random.randint(1, 15, num_records),
            'paramedics_senior_count': np.random.randint(0, 8, num_records),
            'paramedics_junior_count': np.random.randint(0, 8, num_records),
            'nurses_available_count': np.random.randint(0, 6, num_records),
            'active_dispatches_count': np.random.randint(0, 20, num_records),
            'ambulances_busy_percentage': np.random.uniform(0.0, 1.0, num_records),
            'average_response_time_minutes': np.random.uniform(1.5, 20.0, num_records),
            'assigned_ambulance_id': np.random.randint(1, 11, num_records),
            'assigned_paramedic_ids': [
                str(list(np.random.choice(range(1, 20), np.random.randint(1, 4), replace=False)))
                for _ in range(num_records)
            ],
            'assigned_paramedic_levels': [
                ','.join(np.random.choice(['senior', 'junior'], np.random.randint(1, 3)))
                for _ in range(num_records)
            ],
            'actual_response_time_minutes': np.random.uniform(1.0, 25.0, num_records),
            'actual_travel_distance_km': np.random.uniform(0.1, 20.0, num_records),
            'patient_outcome': np.random.choice(['recovered', 'stable', 'transferred', 'expired'], num_records, p=[0.6, 0.25, 0.12, 0.03]),
            'optimization_score': np.random.uniform(0.5, 1.0, num_records),
            'paramedic_satisfaction_rating': np.random.randint(1, 6, num_records),
            'patient_satisfaction_rating': np.random.randint(1, 6, num_records),
        }

        df = pd.DataFrame(data)

        # Generar target variable (was_optimal) basado en características con correlación fuerte
        # Optimización depende de: distancia, tiempo y satisfacción - con pesos
        distance_score = 1 - (df['nearest_ambulance_distance_km'] / 15.0).clip(0, 1)
        time_score = 1 - (df['actual_response_time_minutes'] / 20.0).clip(0, 1)
        satisfaction_score = (df['patient_satisfaction_rating'] / 5.0)
        optimization_direct = df['optimization_score']

        # Combinar scores con pesos
        combined_score = (distance_score * 0.25 + time_score * 0.25 +
                         satisfaction_score * 0.25 + optimization_direct * 0.25)

        # Usar umbral para clasificación - más flexible
        threshold = combined_score.quantile(0.30)  # Top 30% son óptimos
        df['was_optimal'] = (combined_score > threshold).astype(int)

        # Agregar mínimo ruido (solo 5%)
        noise_indices = np.random.choice(len(df), size=int(0.05 * len(df)), replace=False)
        df.loc[noise_indices, 'was_optimal'] = 1 - df.loc[noise_indices, 'was_optimal']

        # Agregar created_at como timestamp actual
        df['created_at'] = datetime.now()

        logger.info(f"Generados {num_records} registros sintéticos")
        logger.info(f"Distribución was_optimal: {df['was_optimal'].value_counts().to_dict()}")

        return df

    def insert_data(self, df: pd.DataFrame) -> bool:
        """
        Insertar datos en SQL Server

        Args:
            df: DataFrame con datos a insertar

        Returns:
            True si fue exitoso, False si hubo error
        """
        if not self.connection:
            if not self.connect():
                return False

        try:
            cursor = self.connection.cursor()

            # Construir query INSERT
            columns = ', '.join(df.columns)
            placeholders = ', '.join(['?' for _ in df.columns])
            insert_query = f"INSERT INTO ml.assignment_history ({columns}) VALUES ({placeholders})"

            # Insertar fila por fila
            for idx, row in df.iterrows():
                values = tuple(
                    None if pd.isna(val) else (
                        str(val) if isinstance(val, (list, np.ndarray)) else val
                    )
                    for val in row
                )
                cursor.execute(insert_query, values)

            self.connection.commit()
            logger.info(f"Insertados {len(df)} registros en assignment_history")
            cursor.close()
            return True

        except Exception as e:
            logger.error(f"Error insertando datos: {e}")
            self.connection.rollback()
            return False

    def insert_data_batch(self, df: pd.DataFrame, batch_size: int = 100) -> bool:
        """
        Insertar datos en lotes (más eficiente)

        Args:
            df: DataFrame con datos a insertar
            batch_size: Tamaño de cada lote

        Returns:
            True si fue exitoso, False si hubo error
        """
        if not self.connection:
            if not self.connect():
                return False

        try:
            cursor = self.connection.cursor()

            columns = ', '.join(df.columns)
            placeholders = ', '.join(['?' for _ in df.columns])
            insert_query = f"INSERT INTO ml.assignment_history ({columns}) VALUES ({placeholders})"

            total_inserted = 0

            # Procesar en lotes
            for batch_start in range(0, len(df), batch_size):
                batch_end = min(batch_start + batch_size, len(df))
                batch = df.iloc[batch_start:batch_end]

                for idx, row in batch.iterrows():
                    values = tuple(
                        None if pd.isna(val) else (
                            str(val) if isinstance(val, (list, np.ndarray)) else val
                        )
                        for val in row
                    )
                    cursor.execute(insert_query, values)

                self.connection.commit()
                total_inserted += len(batch)
                logger.info(f"Insertados {total_inserted}/{len(df)} registros")

            cursor.close()
            logger.info(f"Todos los {total_inserted} registros insertados exitosamente")
            return True

        except Exception as e:
            logger.error(f"Error insertando datos en lotes: {e}")
            self.connection.rollback()
            return False

    def verify_data(self) -> Dict:
        """
        Verificar datos insertados

        Returns:
            Diccionario con estadísticas de verificación
        """
        if not self.connection:
            if not self.connect():
                return {}

        try:
            cursor = self.connection.cursor()

            # Contar registros
            cursor.execute("SELECT COUNT(*) FROM ml.assignment_history")
            total_records = cursor.fetchone()[0]

            # Contar registros optimales
            cursor.execute("SELECT COUNT(*) FROM ml.assignment_history WHERE was_optimal = 1")
            optimal_records = cursor.fetchone()[0]

            # Obtener rango de fechas
            cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM ml.assignment_history")
            date_range = cursor.fetchone()

            # Contar por severidad
            cursor.execute("""
                SELECT severity_level, COUNT(*)
                FROM ml.assignment_history
                GROUP BY severity_level
                ORDER BY severity_level
            """)
            severity_dist = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.close()

            optimal_rate = (optimal_records / total_records * 100) if total_records > 0 else 0

            stats = {
                'total_records': total_records,
                'optimal_records': optimal_records,
                'optimal_rate': round(optimal_rate, 2),
                'date_range': {
                    'start': str(date_range[0]) if date_range[0] else 'N/A',
                    'end': str(date_range[1]) if date_range[1] else 'N/A'
                },
                'severity_distribution': severity_dist
            }

            logger.info(f"Verificación: {stats['total_records']} registros total")
            logger.info(f"Tasa de optimalidad: {stats['optimal_rate']}%")

            return stats

        except Exception as e:
            logger.error(f"Error verificando datos: {e}")
            return {}


if __name__ == "__main__":
    # Configuración de logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Crear generador
    generator = DataGenerator(
        server='192.168.1.38',
        database='ms_ml_despacho',
        username='sa',
        password='1234'
    )

    # Generar datos
    print("\n=== GENERADOR DE DATOS SINTÉTICOS ===\n")
    df = DataGenerator.generate_synthetic_data(num_records=500)
    print(f"Generados {len(df)} registros")
    print(f"\nPrimeras 5 filas:")
    print(df.head())
    print(f"\nEstadísticas básicas:")
    print(f"Total registros: {len(df)}")
    print(f"Registros óptimos: {df['was_optimal'].sum()}")
    print(f"Tasa de optimalidad: {df['was_optimal'].sum() / len(df) * 100:.2f}%")

    # Conectar a BD e insertar
    if generator.connect():
        print("\n=== INSERTANDO DATOS EN SQL SERVER ===\n")
        if generator.insert_data_batch(df, batch_size=50):
            print("\n=== VERIFICANDO DATOS ===\n")
            stats = generator.verify_data()
            print(f"Total registros en BD: {stats.get('total_records', 0)}")
            print(f"Tasa de optimalidad: {stats.get('optimal_rate', 0):.2f}%")
            print(f"Distribución por severidad: {stats.get('severity_distribution', {})}")
            print(f"Rango de fechas: {stats.get('date_range', {})}")
        generator.disconnect()
    else:
        print("No se pudo conectar a la BD")

    print("\n=== COMPLETADO ===\n")
