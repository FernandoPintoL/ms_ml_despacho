"""
Health Checker - Sistema de verificación de salud
Monitorea disponibilidad y performance del servicio
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
import pyodbc
import json
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Estados de salud"""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


class HealthChecker:
    """
    Sistema de verificación de salud del servicio
    Monitorea BD, modelos, endpoints y recursos
    """

    def __init__(self, server: str, database: str, username: str, password: str):
        """
        Inicializar HealthChecker

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
            logger.info("Connected to database for health check")
            return True
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            return False

    def disconnect(self):
        """Cerrar conexión"""
        if self.connection:
            self.connection.close()

    def check_database_health(self) -> Dict:
        """
        Verificar salud de la base de datos

        Returns:
            Diccionario con estado de BD
        """
        if not self.connection:
            if not self.connect():
                return {
                    'status': HealthStatus.UNHEALTHY.value,
                    'database': 'DISCONNECTED',
                    'message': 'Cannot connect to database'
                }

        try:
            cursor = self.connection.cursor()

            # Verificar tablas
            table_checks = {}
            tables = [
                ('ml.assignment_history', 'Training data'),
                ('ml.predictions_log', 'Prediction logs'),
                ('ml.ab_test_log', 'A/B test logs'),
                ('ml.drift_alerts', 'Drift alerts'),
                ('ml.system_alerts', 'System alerts')
            ]

            for table_name, description in tables:
                try:
                    parts = table_name.split('.')
                    cursor.execute(
                        f"SELECT COUNT(*) FROM {table_name}"
                    )
                    count = cursor.fetchone()[0]
                    table_checks[table_name] = {
                        'exists': True,
                        'record_count': count,
                        'status': 'OK'
                    }
                except Exception as e:
                    table_checks[table_name] = {
                        'exists': False,
                        'status': 'ERROR',
                        'error': str(e)
                    }

            # Verificar espacio en BD
            space_query = """
            SELECT
                SUM(size) * 8 / 1024 as size_mb
            FROM sys.database_files
            WHERE type_desc = 'ROWS'
            """

            cursor.execute(space_query)
            space_row = cursor.fetchone()
            db_size_mb = space_row[0] if space_row and space_row[0] else 0

            # Verificar últimas escrituras
            recent_writes = {}
            for table_name, description in tables[1:]:  # Skip training data
                try:
                    cursor.execute(
                        f"SELECT MAX(created_at) FROM {table_name}"
                    )
                    last_write = cursor.fetchone()[0]
                    recent_writes[table_name] = last_write.isoformat() if last_write else None
                except:
                    recent_writes[table_name] = None

            cursor.close()

            return {
                'status': HealthStatus.HEALTHY.value,
                'database': 'CONNECTED',
                'timestamp': datetime.now().isoformat(),
                'tables': table_checks,
                'database_size_mb': round(db_size_mb, 2),
                'recent_writes': recent_writes
            }

        except Exception as e:
            logger.error(f"Error checking database health: {e}")
            return {
                'status': HealthStatus.UNHEALTHY.value,
                'database': 'ERROR',
                'error': str(e)
            }

    def check_model_health(self) -> Dict:
        """
        Verificar salud del modelo ML

        Returns:
            Diccionario con estado del modelo
        """
        import os

        model_path = os.path.join(
            os.path.dirname(__file__),
            '..', '..', 'src', 'models', 'xgboost_model.pkl'
        )
        scaler_path = os.path.join(
            os.path.dirname(__file__),
            '..', '..', 'src', 'models', 'xgboost_model_scaler.pkl'
        )

        model_exists = os.path.exists(model_path)
        scaler_exists = os.path.exists(scaler_path)

        status = HealthStatus.HEALTHY.value if (model_exists and scaler_exists) else HealthStatus.UNHEALTHY.value

        return {
            'status': status,
            'model': {
                'file': 'xgboost_model.pkl',
                'exists': model_exists,
                'size_kb': round(os.path.getsize(model_path) / 1024, 2) if model_exists else 0,
                'modified': datetime.fromtimestamp(
                    os.path.getmtime(model_path)
                ).isoformat() if model_exists else None
            },
            'scaler': {
                'file': 'xgboost_model_scaler.pkl',
                'exists': scaler_exists,
                'size_kb': round(os.path.getsize(scaler_path) / 1024, 2) if scaler_exists else 0,
                'modified': datetime.fromtimestamp(
                    os.path.getmtime(scaler_path)
                ).isoformat() if scaler_exists else None
            },
            'timestamp': datetime.now().isoformat()
        }

    def check_prediction_service_health(self) -> Dict:
        """
        Verificar salud del servicio de predicciones

        Returns:
            Diccionario con estado del servicio
        """
        if not self.connection:
            if not self.connect():
                return {
                    'status': HealthStatus.UNHEALTHY.value,
                    'message': 'Cannot connect to database'
                }

        try:
            cursor = self.connection.cursor()

            # Verificar predicciones recientes
            query = """
            SELECT
                COUNT(*) as total_24h,
                AVG(CAST(JSON_VALUE(phase2_result_json, '$.confidence') as float)) as avg_confidence,
                SUM(CASE WHEN CAST(JSON_VALUE(phase2_result_json, '$.confidence') as float) < 0.75 THEN 1 ELSE 0 END) as low_confidence_count
            FROM ml.ab_test_log
            WHERE created_at > DATEADD(hour, -24, GETDATE())
            AND phase2_result_json IS NOT NULL
            """

            cursor.execute(query)
            row = cursor.fetchone()

            total_24h = row[0] if row and row[0] else 0
            avg_confidence = row[1] if row and row[1] else 0
            low_confidence_count = row[2] if row and row[2] else 0

            # Tasa de confianza baja
            low_conf_rate = (low_confidence_count / total_24h * 100) if total_24h > 0 else 0

            # Determinar estado
            if total_24h == 0:
                status = HealthStatus.DEGRADED.value
                message = "No predictions in last 24 hours"
            elif avg_confidence < 0.75 or low_conf_rate > 20:
                status = HealthStatus.UNHEALTHY.value
                message = "Low confidence levels detected"
            elif avg_confidence < 0.85:
                status = HealthStatus.DEGRADED.value
                message = "Confidence below optimal threshold"
            else:
                status = HealthStatus.HEALTHY.value
                message = "Predictions healthy"

            cursor.close()

            return {
                'status': status,
                'message': message,
                'metrics': {
                    'total_predictions_24h': total_24h,
                    'avg_confidence': round(avg_confidence, 4),
                    'low_confidence_count': low_confidence_count,
                    'low_confidence_rate': round(low_conf_rate, 2)
                },
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error checking prediction service: {e}")
            return {
                'status': HealthStatus.UNHEALTHY.value,
                'error': str(e)
            }

    def check_fallback_health(self) -> Dict:
        """
        Verificar salud basada en tasa de fallback

        Returns:
            Diccionario con estado de fallbacks
        """
        if not self.connection:
            if not self.connect():
                return {
                    'status': HealthStatus.UNHEALTHY.value,
                    'message': 'Cannot connect to database'
                }

        try:
            cursor = self.connection.cursor()

            query = """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN used_fallback = 1 THEN 1 ELSE 0 END) as fallback_count
            FROM ml.predictions_log
            WHERE created_at > DATEADD(hour, -24, GETDATE())
            """

            cursor.execute(query)
            row = cursor.fetchone()
            cursor.close()

            total = row[0] if row and row[0] else 0
            fallback_count = row[1] if row and row[1] else 0
            fallback_rate = (fallback_count / total * 100) if total > 0 else 0

            # Determinar estado
            if fallback_rate > 10:
                status = HealthStatus.UNHEALTHY.value
                message = "Critical fallback rate"
            elif fallback_rate > 5:
                status = HealthStatus.DEGRADED.value
                message = "High fallback rate"
            else:
                status = HealthStatus.HEALTHY.value
                message = "Fallback rate normal"

            return {
                'status': status,
                'message': message,
                'metrics': {
                    'total_predictions': total,
                    'fallback_count': fallback_count,
                    'fallback_rate': round(fallback_rate, 2)
                },
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error checking fallback health: {e}")
            return {
                'status': HealthStatus.UNHEALTHY.value,
                'error': str(e)
            }

    def get_overall_health(self) -> Dict:
        """
        Obtener estado general del sistema

        Returns:
            Diccionario con estado general
        """
        db_health = self.check_database_health()
        model_health = self.check_model_health()
        prediction_health = self.check_prediction_service_health()
        fallback_health = self.check_fallback_health()

        # Determinar estado general
        statuses = [
            db_health.get('status'),
            model_health.get('status'),
            prediction_health.get('status'),
            fallback_health.get('status')
        ]

        if HealthStatus.UNHEALTHY.value in statuses:
            overall_status = HealthStatus.UNHEALTHY.value
        elif HealthStatus.DEGRADED.value in statuses:
            overall_status = HealthStatus.DEGRADED.value
        else:
            overall_status = HealthStatus.HEALTHY.value

        return {
            'overall_status': overall_status,
            'timestamp': datetime.now().isoformat(),
            'checks': {
                'database': db_health,
                'model': model_health,
                'prediction_service': prediction_health,
                'fallback': fallback_health
            },
            'summary': {
                'healthy': sum(1 for s in statuses if s == HealthStatus.HEALTHY.value),
                'degraded': sum(1 for s in statuses if s == HealthStatus.DEGRADED.value),
                'unhealthy': sum(1 for s in statuses if s == HealthStatus.UNHEALTHY.value)
            }
        }

    def log_health_check(self, health_data: Dict) -> bool:
        """
        Registrar un health check en BD

        Args:
            health_data: Datos del health check

        Returns:
            True si fue exitoso
        """
        if not self.connection:
            if not self.connect():
                return False

        try:
            cursor = self.connection.cursor()
            self._ensure_health_check_table(cursor)

            insert_query = """
            INSERT INTO ml.health_checks (
                overall_status, database_status, model_status,
                prediction_status, fallback_status, details_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """

            values = (
                health_data.get('overall_status'),
                health_data.get('checks', {}).get('database', {}).get('status'),
                health_data.get('checks', {}).get('model', {}).get('status'),
                health_data.get('checks', {}).get('prediction_service', {}).get('status'),
                health_data.get('checks', {}).get('fallback', {}).get('status'),
                json.dumps(health_data),
                datetime.now()
            )

            cursor.execute(insert_query, values)
            self.connection.commit()
            cursor.close()

            return True

        except Exception as e:
            logger.error(f"Error logging health check: {e}")
            return False

    def _ensure_health_check_table(self, cursor):
        """Crear tabla de health checks si no existe"""
        try:
            create_table_query = """
            IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES
                          WHERE TABLE_NAME = 'health_checks' AND TABLE_SCHEMA = 'ml')
            BEGIN
                CREATE TABLE ml.health_checks (
                    id INT PRIMARY KEY IDENTITY(1,1),
                    overall_status NVARCHAR(20),
                    database_status NVARCHAR(20),
                    model_status NVARCHAR(20),
                    prediction_status NVARCHAR(20),
                    fallback_status NVARCHAR(20),
                    details_json NVARCHAR(MAX),
                    created_at DATETIME2 DEFAULT GETDATE(),
                    INDEX idx_overall_status (overall_status),
                    INDEX idx_created_at (created_at)
                )
            END
            """
            cursor.execute(create_table_query)
            self.connection.commit()
        except Exception as e:
            logger.warning(f"Error ensuring health_checks table: {e}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    checker = HealthChecker(
        server='192.168.1.38',
        database='ms_ml_despacho',
        username='sa',
        password='1234'
    )

    print("\n=== HEALTH CHECKER TEST ===\n")

    if checker.connect():
        print("1. Database Health:")
        db_health = checker.check_database_health()
        print(f"   Status: {db_health.get('status')}")
        print(f"   Tables: {len(db_health.get('tables', {}))}")

        print("\n2. Model Health:")
        model_health = checker.check_model_health()
        print(f"   Status: {model_health.get('status')}")

        print("\n3. Prediction Service Health:")
        pred_health = checker.check_prediction_service_health()
        print(f"   Status: {pred_health.get('status')}")

        print("\n4. Fallback Health:")
        fallback_health = checker.check_fallback_health()
        print(f"   Status: {fallback_health.get('status')}")

        print("\n5. Overall Health:")
        overall = checker.get_overall_health()
        print(f"   Status: {overall.get('overall_status')}")
        print(f"   Summary: {overall.get('summary')}")

        checker.disconnect()
    else:
        print("Failed to connect to database")

    print("\n=== TEST COMPLETE ===\n")
