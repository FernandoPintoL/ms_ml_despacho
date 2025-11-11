"""
Prediction Logger - Logging centralizado de predicciones
Registra todas las predicciones y sus outcomes para auditoría y análisis
"""

import logging
import json
from datetime import datetime
from typing import Dict, Optional
import pyodbc

logger = logging.getLogger(__name__)


class PredictionLogger:
    """Logger centralizado para predicciones del modelo ML"""

    def __init__(self, server: str, database: str, username: str, password: str):
        """
        Inicializar logger de predicciones

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
            logger.info("Connected to database for prediction logging")
            return True
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            return False

    def disconnect(self):
        """Cerrar conexión"""
        if self.connection:
            self.connection.close()

    def log_prediction(self, dispatch_id: int, phase: int,
                      prediction: int, confidence: float,
                      features: Dict, recommendation: str = None,
                      fallback: bool = False) -> bool:
        """
        Registrar una predicción

        Args:
            dispatch_id: ID del despacho
            phase: Fase utilizada (1 o 2)
            prediction: Predicción (0 o 1)
            confidence: Confianza (0-1)
            features: Diccionario con features utilizadas
            recommendation: Recomendación generada
            fallback: Si fue fallback a Fase 1

        Returns:
            True si fue exitoso
        """
        if not self.connection:
            if not self.connect():
                return False

        try:
            cursor = self.connection.cursor()

            # Crear tabla si no existe
            self._ensure_predictions_log_table(cursor)

            # Insertar predicción
            insert_query = """
            INSERT INTO ml.predictions_log (
                dispatch_id, phase, prediction, confidence,
                recommendation, used_fallback, features_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """

            values = (
                dispatch_id,
                phase,
                prediction,
                confidence,
                recommendation or f"{'ASSIGN' if prediction == 1 else 'REVIEW'}",
                1 if fallback else 0,
                json.dumps(features),
                datetime.now()
            )

            cursor.execute(insert_query, values)
            self.connection.commit()
            cursor.close()

            logger.info(f"Logged prediction for dispatch {dispatch_id}")
            return True

        except Exception as e:
            logger.error(f"Error logging prediction: {e}")
            return False

    def log_outcome(self, dispatch_id: int,
                   actual_response_time: float,
                   was_optimal: int,
                   patient_satisfaction: int = None,
                   paramedic_satisfaction: int = None) -> bool:
        """
        Registrar outcome de una asignación

        Args:
            dispatch_id: ID del despacho
            actual_response_time: Tiempo real de respuesta en minutos
            was_optimal: Si fue óptimo (0 o 1)
            patient_satisfaction: Calificación de paciente (1-5)
            paramedic_satisfaction: Calificación de paramedic (1-5)

        Returns:
            True si fue exitoso
        """
        if not self.connection:
            if not self.connect():
                return False

        try:
            cursor = self.connection.cursor()

            # Actualizar assignment_history con outcome
            update_query = """
            UPDATE ml.assignment_history
            SET
                actual_response_time_minutes = ?,
                was_optimal = ?,
                patient_satisfaction_rating = ?,
                paramedic_satisfaction_rating = ?,
                updated_at = ?
            WHERE dispatch_id = ?
            """

            values = (
                actual_response_time,
                was_optimal,
                patient_satisfaction,
                paramedic_satisfaction,
                datetime.now(),
                dispatch_id
            )

            cursor.execute(update_query, values)
            self.connection.commit()
            cursor.close()

            logger.info(f"Logged outcome for dispatch {dispatch_id}")
            return True

        except Exception as e:
            logger.error(f"Error logging outcome: {e}")
            return False

    def get_prediction_history(self, dispatch_id: int) -> Dict:
        """
        Obtener historial de predicciones para un dispatch

        Args:
            dispatch_id: ID del despacho

        Returns:
            Diccionario con predicciones
        """
        if not self.connection:
            if not self.connect():
                return {}

        try:
            cursor = self.connection.cursor()

            query = """
            SELECT TOP 1
                dispatch_id, phase, prediction, confidence,
                recommendation, used_fallback, features_json,
                created_at
            FROM ml.predictions_log
            WHERE dispatch_id = ?
            ORDER BY created_at DESC
            """

            cursor.execute(query, (dispatch_id,))
            row = cursor.fetchone()
            cursor.close()

            if row:
                return {
                    'dispatch_id': row[0],
                    'phase': row[1],
                    'prediction': row[2],
                    'confidence': row[3],
                    'recommendation': row[4],
                    'used_fallback': bool(row[5]),
                    'features': json.loads(row[6]),
                    'created_at': str(row[7])
                }
            return {}

        except Exception as e:
            logger.error(f"Error getting prediction history: {e}")
            return {}

    def get_statistics(self, hours: int = 24) -> Dict:
        """
        Obtener estadísticas de predicciones

        Args:
            hours: Últimas N horas

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
                COUNT(*) as total_predictions,
                SUM(CASE WHEN phase = 2 THEN 1 ELSE 0 END) as ml_predictions,
                SUM(CASE WHEN phase = 1 THEN 1 ELSE 0 END) as phase1_predictions,
                SUM(CASE WHEN used_fallback = 1 THEN 1 ELSE 0 END) as fallback_count,
                AVG(CAST(confidence as float)) as avg_confidence
            FROM ml.predictions_log
            WHERE created_at > DATEADD(hour, -?, GETDATE())
            """

            cursor.execute(query, (hours,))
            row = cursor.fetchone()
            cursor.close()

            if row:
                total = row[0] or 0
                ml_preds = row[1] or 0
                p1_preds = row[2] or 0
                fallbacks = row[3] or 0

                return {
                    'total_predictions': total,
                    'ml_predictions': ml_preds,
                    'phase1_predictions': p1_preds,
                    'fallback_count': fallbacks,
                    'fallback_rate': (fallbacks / total * 100) if total > 0 else 0,
                    'avg_confidence': float(row[4] or 0),
                    'ml_rate': (ml_preds / total * 100) if total > 0 else 0,
                    'hours': hours
                }
            return {}

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}

    def _ensure_predictions_log_table(self, cursor):
        """Crear tabla de log si no existe"""
        try:
            create_table_query = """
            IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES
                          WHERE TABLE_NAME = 'predictions_log' AND TABLE_SCHEMA = 'ml')
            BEGIN
                CREATE TABLE ml.predictions_log (
                    id INT PRIMARY KEY IDENTITY(1,1),
                    dispatch_id INT NOT NULL,
                    phase INT NOT NULL,
                    prediction INT NOT NULL,
                    confidence DECIMAL(10, 4),
                    recommendation NVARCHAR(255),
                    used_fallback BIT DEFAULT 0,
                    features_json NVARCHAR(MAX),
                    created_at DATETIME2 DEFAULT GETDATE(),
                    INDEX idx_dispatch_id (dispatch_id),
                    INDEX idx_phase (phase),
                    INDEX idx_created_at (created_at)
                )
            END
            """
            cursor.execute(create_table_query)
            self.connection.commit()
        except Exception as e:
            logger.warning(f"Error ensuring predictions_log table: {e}")


class PredictionMetrics:
    """Calcula métricas de predicciones"""

    @staticmethod
    def compare_phase1_vs_phase2(logger: PredictionLogger, hours: int = 24) -> Dict:
        """
        Comparar performance de Fase 1 vs Fase 2

        Args:
            logger: Instancia de PredictionLogger
            hours: Período en horas

        Returns:
            Diccionario con comparativa
        """
        stats = logger.get_statistics(hours)

        if stats.get('total_predictions', 0) == 0:
            return {'error': 'No data available'}

        return {
            'period_hours': hours,
            'total_predictions': stats['total_predictions'],
            'phase2_percentage': stats.get('ml_rate', 0),
            'phase1_percentage': (stats.get('phase1_predictions', 0) /
                                 stats.get('total_predictions', 1) * 100),
            'fallback_rate': stats.get('fallback_rate', 0),
            'avg_confidence_phase2': stats.get('avg_confidence', 0),
            'recommendations': {
                'status': 'Phase 2 performing well' if stats.get('fallback_rate', 0) < 5 else 'Phase 2 experiencing issues',
                'fallback_rate_high': stats.get('fallback_rate', 0) > 10,
                'ml_adoption': f"{stats.get('ml_rate', 0):.1f}% requests using ML"
            }
        }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Test
    logger_instance = PredictionLogger(
        server='192.168.1.38',
        database='ms_ml_despacho',
        username='sa',
        password='1234'
    )

    print("\n=== PREDICTION LOGGER TEST ===\n")

    if logger_instance.connect():
        # Log test prediction
        test_features = {
            'severity_level': 4,
            'hour_of_day': 14,
            'dispatch_id': 999
        }

        print("Logging test prediction...")
        logger_instance.log_prediction(
            dispatch_id=999,
            phase=2,
            prediction=1,
            confidence=0.95,
            features=test_features,
            recommendation="ASSIGN - High confidence",
            fallback=False
        )

        # Get statistics
        print("Getting statistics...")
        stats = logger_instance.get_statistics(24)
        print(f"Total predictions (24h): {stats.get('total_predictions')}")
        print(f"ML predictions: {stats.get('ml_predictions')}")
        print(f"Fallback rate: {stats.get('fallback_rate'):.2f}%\n")

        logger_instance.disconnect()
    else:
        print("Failed to connect to database")

    print("=== TEST COMPLETE ===\n")
