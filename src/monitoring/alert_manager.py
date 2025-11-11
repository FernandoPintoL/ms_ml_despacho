"""
Alert Manager - Sistema de gestión de alertas
Configura umbrales, envía notificaciones y registra alertas
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pyodbc
import json
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Niveles de severidad de alertas"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class AlertType(Enum):
    """Tipos de alertas"""
    DRIFT_DETECTED = "DRIFT_DETECTED"
    PERFORMANCE_DEGRADATION = "PERFORMANCE_DEGRADATION"
    SERVICE_DOWN = "SERVICE_DOWN"
    HIGH_FALLBACK_RATE = "HIGH_FALLBACK_RATE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    DATA_QUALITY = "DATA_QUALITY"
    MEMORY_USAGE = "MEMORY_USAGE"
    DATABASE_ERROR = "DATABASE_ERROR"


class AlertThresholds:
    """Umbrales para diferentes tipos de alertas"""

    def __init__(self):
        # Drift thresholds
        self.drift_confidence_change = 10  # % de cambio en confianza
        self.drift_variance_change = 0.05  # Cambio en desviación estándar

        # Performance thresholds
        self.performance_degradation = -5  # % de cambio negativo
        self.confidence_minimum = 0.75  # Confianza mínima aceptable

        # Fallback thresholds
        self.fallback_rate_warning = 5  # %
        self.fallback_rate_critical = 10  # %

        # Data quality thresholds
        self.null_rate_warning = 5  # %
        self.null_rate_critical = 20  # %
        self.outlier_rate_warning = 5  # %

        # Service thresholds
        self.service_timeout = 30  # segundos
        self.service_response_time = 5  # segundos para warning

        # Resource thresholds
        self.memory_usage_warning = 80  # %
        self.memory_usage_critical = 95  # %


class AlertManager:
    """
    Gestor centralizado de alertas
    Configura umbrales, registra y notifica
    """

    def __init__(self, server: str, database: str, username: str, password: str):
        """
        Inicializar AlertManager

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
        self.thresholds = AlertThresholds()
        self.alert_handlers = []

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
            logger.info("Connected to database for alert management")
            return True
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            return False

    def disconnect(self):
        """Cerrar conexión"""
        if self.connection:
            self.connection.close()

    def create_alert(self, alert_type: AlertType, severity: AlertSeverity,
                    title: str, description: str, details: Dict = None,
                    resolution_steps: List[str] = None) -> bool:
        """
        Crear una nueva alerta

        Args:
            alert_type: Tipo de alerta
            severity: Nivel de severidad
            title: Título de la alerta
            description: Descripción
            details: Detalles adicionales
            resolution_steps: Pasos de resolución

        Returns:
            True si fue exitoso
        """
        if not self.connection:
            if not self.connect():
                return False

        try:
            cursor = self.connection.cursor()
            self._ensure_alerts_table(cursor)

            insert_query = """
            INSERT INTO ml.system_alerts (
                alert_type, severity, title, description,
                details_json, resolution_steps_json, created_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """

            values = (
                alert_type.value,
                severity.value,
                title,
                description,
                json.dumps(details or {}),
                json.dumps(resolution_steps or []),
                datetime.now(),
                'OPEN'
            )

            cursor.execute(insert_query, values)
            self.connection.commit()

            alert_id = cursor.execute("SELECT @@IDENTITY").fetchone()[0]
            cursor.close()

            logger.warning(f"Alert created: {alert_type.value} (ID: {alert_id}, {severity.value})")

            # Notificar handlers
            self._notify_handlers({
                'id': alert_id,
                'type': alert_type.value,
                'severity': severity.value,
                'title': title,
                'description': description
            })

            return True

        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            return False

    def check_fallback_rate(self, hours: int = 24) -> Optional[AlertType]:
        """
        Verificar tasa de fallback

        Args:
            hours: Período en horas

        Returns:
            AlertType si se debe crear alerta, None si todo está bien
        """
        if not self.connection:
            if not self.connect():
                return None

        try:
            cursor = self.connection.cursor()

            query = """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN used_fallback = 1 THEN 1 ELSE 0 END) as fallback_count
            FROM ml.predictions_log
            WHERE created_at > DATEADD(hour, -?, GETDATE())
            """

            cursor.execute(query, (hours,))
            row = cursor.fetchone()
            cursor.close()

            if not row or not row[0]:
                return None

            total = row[0]
            fallback_count = row[1] or 0
            fallback_rate = (fallback_count / total * 100) if total > 0 else 0

            if fallback_rate > self.thresholds.fallback_rate_critical:
                return AlertType.HIGH_FALLBACK_RATE

            return None

        except Exception as e:
            logger.error(f"Error checking fallback rate: {e}")
            return None

    def check_confidence_levels(self, hours: int = 24) -> Optional[AlertType]:
        """
        Verificar niveles de confianza

        Args:
            hours: Período en horas

        Returns:
            AlertType si se debe crear alerta, None si todo está bien
        """
        if not self.connection:
            if not self.connect():
                return None

        try:
            cursor = self.connection.cursor()

            query = """
            SELECT
                AVG(CAST(JSON_VALUE(phase2_result_json, '$.confidence') as float)) as avg_confidence
            FROM ml.ab_test_log
            WHERE created_at > DATEADD(hour, -?, GETDATE())
            AND phase2_result_json IS NOT NULL
            """

            cursor.execute(query, (hours,))
            row = cursor.fetchone()
            cursor.close()

            if not row or not row[0]:
                return None

            avg_confidence = row[0]

            if avg_confidence < self.thresholds.confidence_minimum:
                return AlertType.LOW_CONFIDENCE

            return None

        except Exception as e:
            logger.error(f"Error checking confidence levels: {e}")
            return None

    def resolve_alert(self, alert_id: int, resolution_notes: str = None) -> bool:
        """
        Marcar una alerta como resuelta

        Args:
            alert_id: ID de la alerta
            resolution_notes: Notas sobre la resolución

        Returns:
            True si fue exitoso
        """
        if not self.connection:
            if not self.connect():
                return False

        try:
            cursor = self.connection.cursor()

            update_query = """
            UPDATE ml.system_alerts
            SET status = 'RESOLVED', resolved_at = ?, resolution_notes = ?
            WHERE id = ?
            """

            cursor.execute(update_query, (datetime.now(), resolution_notes, alert_id))
            self.connection.commit()
            cursor.close()

            logger.info(f"Alert {alert_id} resolved")
            return True

        except Exception as e:
            logger.error(f"Error resolving alert: {e}")
            return False

    def get_active_alerts(self) -> List[Dict]:
        """
        Obtener todas las alertas activas

        Returns:
            Lista de alertas activas
        """
        if not self.connection:
            if not self.connect():
                return []

        try:
            cursor = self.connection.cursor()

            query = """
            SELECT
                id, alert_type, severity, title, description,
                created_at, resolution_steps_json
            FROM ml.system_alerts
            WHERE status = 'OPEN'
            ORDER BY created_at DESC
            """

            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()

            alerts = []
            for row in rows:
                alerts.append({
                    'id': row[0],
                    'type': row[1],
                    'severity': row[2],
                    'title': row[3],
                    'description': row[4],
                    'created_at': row[5].isoformat() if row[5] else None,
                    'resolution_steps': json.loads(row[6]) if row[6] else []
                })

            return alerts

        except Exception as e:
            logger.error(f"Error getting active alerts: {e}")
            return []

    def get_alert_history(self, days: int = 7) -> List[Dict]:
        """
        Obtener historial de alertas

        Args:
            days: Número de días a revisar

        Returns:
            Lista de alertas históricas
        """
        if not self.connection:
            if not self.connect():
                return []

        try:
            cursor = self.connection.cursor()

            query = """
            SELECT
                id, alert_type, severity, title, status,
                created_at, resolved_at
            FROM ml.system_alerts
            WHERE created_at > DATEADD(day, -?, GETDATE())
            ORDER BY created_at DESC
            """

            cursor.execute(query, (days,))
            rows = cursor.fetchall()
            cursor.close()

            alerts = []
            for row in rows:
                alerts.append({
                    'id': row[0],
                    'type': row[1],
                    'severity': row[2],
                    'title': row[3],
                    'status': row[4],
                    'created_at': row[5].isoformat() if row[5] else None,
                    'resolved_at': row[6].isoformat() if row[6] else None
                })

            return alerts

        except Exception as e:
            logger.error(f"Error getting alert history: {e}")
            return []

    def get_alert_statistics(self, days: int = 7) -> Dict:
        """
        Obtener estadísticas de alertas

        Args:
            days: Número de días a considerar

        Returns:
            Diccionario con estadísticas
        """
        if not self.connection:
            if not self.connect():
                return {}

        try:
            cursor = self.connection.cursor()

            query = """
            SELECT
                severity,
                COUNT(*) as count
            FROM ml.system_alerts
            WHERE created_at > DATEADD(day, -?, GETDATE())
            GROUP BY severity
            """

            cursor.execute(query, (days,))
            rows = cursor.fetchall()

            # Alertas por tipo
            query_type = """
            SELECT
                alert_type,
                COUNT(*) as count
            FROM ml.system_alerts
            WHERE created_at > DATEADD(day, -?, GETDATE())
            GROUP BY alert_type
            """

            cursor.execute(query_type, (days,))
            type_rows = cursor.fetchall()

            # Alertas resueltas vs abiertas
            query_status = """
            SELECT
                status,
                COUNT(*) as count
            FROM ml.system_alerts
            WHERE created_at > DATEADD(day, -?, GETDATE())
            GROUP BY status
            """

            cursor.execute(query_status, (days,))
            status_rows = cursor.fetchall()

            cursor.close()

            stats = {
                'period_days': days,
                'timestamp': datetime.now().isoformat(),
                'by_severity': {row[0]: row[1] for row in rows},
                'by_type': {row[0]: row[1] for row in type_rows},
                'by_status': {row[0]: row[1] for row in status_rows},
                'total_alerts': sum(row[1] for row in rows),
                'resolution_rate': 0
            }

            # Calcular tasa de resolución
            status_dict = {row[0]: row[1] for row in status_rows}
            total = status_dict.get('OPEN', 0) + status_dict.get('RESOLVED', 0)
            if total > 0:
                stats['resolution_rate'] = round(
                    status_dict.get('RESOLVED', 0) / total * 100, 2
                )

            return stats

        except Exception as e:
            logger.error(f"Error getting alert statistics: {e}")
            return {}

    def register_handler(self, handler_func):
        """
        Registrar handler para notificaciones de alertas

        Args:
            handler_func: Función que recibe el diccionario de alerta
        """
        self.alert_handlers.append(handler_func)

    def _notify_handlers(self, alert_dict: Dict):
        """Notificar todos los handlers registrados"""
        for handler in self.alert_handlers:
            try:
                handler(alert_dict)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}")

    def _ensure_alerts_table(self, cursor):
        """Crear tabla de alertas si no existe"""
        try:
            create_table_query = """
            IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES
                          WHERE TABLE_NAME = 'system_alerts' AND TABLE_SCHEMA = 'ml')
            BEGIN
                CREATE TABLE ml.system_alerts (
                    id INT PRIMARY KEY IDENTITY(1,1),
                    alert_type NVARCHAR(50) NOT NULL,
                    severity NVARCHAR(20) NOT NULL,
                    title NVARCHAR(255) NOT NULL,
                    description NVARCHAR(MAX),
                    details_json NVARCHAR(MAX),
                    resolution_steps_json NVARCHAR(MAX),
                    status NVARCHAR(20) DEFAULT 'OPEN',
                    created_at DATETIME2 DEFAULT GETDATE(),
                    resolved_at DATETIME2,
                    resolution_notes NVARCHAR(MAX),
                    INDEX idx_status (status),
                    INDEX idx_severity (severity),
                    INDEX idx_created_at (created_at)
                )
            END
            """
            cursor.execute(create_table_query)
            self.connection.commit()
        except Exception as e:
            logger.warning(f"Error ensuring system_alerts table: {e}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    manager = AlertManager(
        server='192.168.1.38',
        database='ms_ml_despacho',
        username='sa',
        password='1234'
    )

    print("\n=== ALERT MANAGER TEST ===\n")

    if manager.connect():
        # Test creating alert
        print("Creating test alert...")
        success = manager.create_alert(
            alert_type=AlertType.HIGH_FALLBACK_RATE,
            severity=AlertSeverity.HIGH,
            title="High Fallback Rate Detected",
            description="Fallback rate exceeded 10% threshold",
            details={'current_rate': 12.5, 'threshold': 10},
            resolution_steps=[
                "Check ML service health",
                "Review recent changes",
                "Restart ML service if needed"
            ]
        )
        print(f"Alert created: {success}")

        # Test getting active alerts
        print("\nActive alerts:")
        alerts = manager.get_active_alerts()
        print(f"Count: {len(alerts)}")

        # Test getting statistics
        print("\nAlert statistics:")
        stats = manager.get_alert_statistics(7)
        print(f"Total alerts (7 days): {stats.get('total_alerts')}")

        manager.disconnect()
    else:
        print("Failed to connect to database")

    print("\n=== TEST COMPLETE ===\n")
