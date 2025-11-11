"""
Real Data Collector - Recopilacion de datos reales en produccion
Valida predicciones contra outcomes reales y prepara datos para reentrenamiento
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pyodbc
import json
from enum import Enum

logger = logging.getLogger(__name__)


class DataQualityLevel(Enum):
    """Niveles de calidad de datos"""
    EXCELLENT = "EXCELLENT"      # 95-100% de confianza
    GOOD = "GOOD"                # 85-95%
    ACCEPTABLE = "ACCEPTABLE"    # 70-85%
    POOR = "POOR"                # < 70%


class RealDataCollector:
    """
    Recopilador de datos reales en produccion
    Valida predicciones vs outcomes y prepara para reentrenamiento
    """

    def __init__(self, server: str, database: str, username: str, password: str):
        """
        Inicializar RealDataCollector

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
            logger.info("Connected to database for real data collection")
            return True
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            return False

    def disconnect(self):
        """Cerrar conexión"""
        if self.connection:
            self.connection.close()

    def validate_prediction(self, dispatch_id: int, actual_outcome: bool,
                           prediction: int, confidence: float) -> Dict:
        """
        Validar predicción contra outcome real

        Args:
            dispatch_id: ID del dispatch
            actual_outcome: Resultado real (True si fue óptimo)
            prediction: Predicción del modelo (0 o 1)
            confidence: Confianza de la predicción

        Returns:
            Diccionario con validación
        """
        # Convertir outcome a 0/1
        actual = 1 if actual_outcome else 0

        # Validación
        is_correct = (prediction == actual)
        prediction_error = abs(prediction - actual)

        # Calcular metrics
        validation = {
            'dispatch_id': dispatch_id,
            'prediction': prediction,
            'actual': actual,
            'is_correct': is_correct,
            'prediction_error': prediction_error,
            'confidence': confidence,
            'confidence_calibration': confidence if is_correct else (1 - confidence),
            'timestamp': datetime.now().isoformat()
        }

        # Log validación
        self._log_prediction_validation(validation)

        return validation

    def get_validation_metrics(self, hours: int = 24, phase: Optional[int] = None) -> Dict:
        """
        Obtener métricas de validación

        Args:
            hours: Período en horas
            phase: Fase específica (1 o 2) o None para ambas

        Returns:
            Diccionario con métricas
        """
        if not self.connection:
            if not self.connect():
                return {}

        try:
            cursor = self.connection.cursor()

            # Query base
            query = """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_predictions,
                AVG(CAST(confidence as float)) as avg_confidence,
                AVG(CAST(prediction_error as float)) as avg_error,
                MIN(CAST(confidence as float)) as min_confidence,
                MAX(CAST(confidence as float)) as max_confidence
            FROM ml.prediction_validation
            WHERE validated_at > DATEADD(hour, -?, GETDATE())
            """

            if phase:
                query += f" AND phase = {phase}"

            cursor.execute(query, (hours,))
            row = cursor.fetchone()
            cursor.close()

            if not row or not row[0]:
                return {
                    'total_validations': 0,
                    'message': f'No validation data for {hours}h'
                }

            total = row[0]
            correct = row[1] or 0
            accuracy = (correct / total * 100) if total > 0 else 0

            metrics = {
                'period_hours': hours,
                'total_validations': int(total),
                'correct_predictions': int(correct),
                'accuracy_percent': round(accuracy, 2),
                'avg_confidence': round(row[2] or 0, 4),
                'avg_error': round(row[3] or 0, 4),
                'confidence_range': {
                    'min': round(row[4] or 0, 4),
                    'max': round(row[5] or 0, 4)
                },
                'timestamp': datetime.now().isoformat()
            }

            # Determinar quality level
            if accuracy >= 95:
                metrics['quality_level'] = DataQualityLevel.EXCELLENT.value
            elif accuracy >= 85:
                metrics['quality_level'] = DataQualityLevel.GOOD.value
            elif accuracy >= 70:
                metrics['quality_level'] = DataQualityLevel.ACCEPTABLE.value
            else:
                metrics['quality_level'] = DataQualityLevel.POOR.value

            return metrics

        except Exception as e:
            logger.error(f"Error getting validation metrics: {e}")
            return {}

    def get_training_data(self, hours: int = 24, min_quality: str = "ACCEPTABLE") -> Tuple[List[Dict], int]:
        """
        Obtener datos listos para reentrenamiento

        Args:
            hours: Período en horas
            min_quality: Nivel mínimo de calidad

        Returns:
            Tupla (lista de records, count)
        """
        if not self.connection:
            if not self.connect():
                return [], 0

        try:
            cursor = self.connection.cursor()

            query = """
            SELECT
                dispatch_id, prediction, actual, confidence,
                features_json, validated_at
            FROM ml.prediction_validation
            WHERE validated_at > DATEADD(hour, -?, GETDATE())
            AND is_correct = 1
            ORDER BY validated_at DESC
            """

            cursor.execute(query, (hours,))
            rows = cursor.fetchall()
            cursor.close()

            data = []
            for row in rows:
                try:
                    features = json.loads(row[4]) if row[4] else {}
                    record = {
                        'dispatch_id': row[0],
                        'prediction': row[1],
                        'actual': row[2],
                        'confidence': row[3],
                        'features': features,
                        'timestamp': row[5]
                    }
                    data.append(record)
                except:
                    continue

            return data, len(data)

        except Exception as e:
            logger.error(f"Error getting training data: {e}")
            return [], 0

    def get_data_distribution(self, hours: int = 24) -> Dict:
        """
        Obtener distribución de datos en período

        Args:
            hours: Período en horas

        Returns:
            Diccionario con distribución
        """
        if not self.connection:
            if not self.connect():
                return {}

        try:
            cursor = self.connection.cursor()

            # Distribución de outcomes
            query = """
            SELECT
                actual,
                COUNT(*) as count
            FROM ml.prediction_validation
            WHERE validated_at > DATEADD(hour, -?, GETDATE())
            GROUP BY actual
            """

            cursor.execute(query, (hours,))
            rows = cursor.fetchall()

            distribution = {'0': 0, '1': 0}
            for row in rows:
                distribution[str(row[0])] = row[1]

            total = sum(distribution.values())

            # Distribución temporal
            time_query = """
            SELECT
                DATEPART(HOUR, validated_at) as hour,
                COUNT(*) as count
            FROM ml.prediction_validation
            WHERE validated_at > DATEADD(hour, -?, GETDATE())
            GROUP BY DATEPART(HOUR, validated_at)
            ORDER BY hour
            """

            cursor.execute(time_query, (hours,))
            time_rows = cursor.fetchall()
            cursor.close()

            time_distribution = {str(row[0]): row[1] for row in time_rows}

            return {
                'period_hours': hours,
                'outcome_distribution': {
                    'negative': distribution['0'],
                    'positive': distribution['1'],
                    'total': total,
                    'positive_rate': round((distribution['1'] / total * 100), 2) if total > 0 else 0
                },
                'hourly_distribution': time_distribution,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting data distribution: {e}")
            return {}

    def get_concept_drift_indicators(self, hours: int = 24, baseline_hours: int = 168) -> Dict:
        """
        Detectar indicadores de concept drift

        Args:
            hours: Período actual
            baseline_hours: Período baseline (default: 1 semana)

        Returns:
            Diccionario con indicadores
        """
        if not self.connection:
            if not self.connect():
                return {}

        try:
            cursor = self.connection.cursor()

            # Accuracy actual
            current_query = """
            SELECT
                AVG(CAST(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END as float)) as accuracy
            FROM ml.prediction_validation
            WHERE validated_at > DATEADD(hour, -?, GETDATE())
            """

            # Accuracy baseline
            baseline_query = """
            SELECT
                AVG(CAST(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END as float)) as accuracy
            FROM ml.prediction_validation
            WHERE validated_at > DATEADD(hour, -?, GETDATE())
            AND validated_at <= DATEADD(hour, -?, GETDATE())
            """

            cursor.execute(current_query, (hours,))
            current_row = cursor.fetchone()
            current_accuracy = current_row[0] or 0 if current_row else 0

            cursor.execute(baseline_query, (baseline_hours, hours))
            baseline_row = cursor.fetchone()
            baseline_accuracy = baseline_row[0] or 0 if baseline_row else 0

            cursor.close()

            # Calcular drift
            accuracy_change = current_accuracy - baseline_accuracy
            accuracy_change_pct = (accuracy_change / baseline_accuracy * 100) if baseline_accuracy > 0 else 0

            indicators = {
                'period_hours': hours,
                'baseline_hours': baseline_hours,
                'current_accuracy': round(current_accuracy, 4),
                'baseline_accuracy': round(baseline_accuracy, 4),
                'accuracy_change': round(accuracy_change, 4),
                'accuracy_change_percent': round(accuracy_change_pct, 2),
                'has_drift': abs(accuracy_change_pct) > 5,
                'drift_severity': 'NONE' if abs(accuracy_change_pct) <= 5
                                  else 'LOW' if abs(accuracy_change_pct) <= 10
                                  else 'MEDIUM' if abs(accuracy_change_pct) <= 20
                                  else 'HIGH',
                'timestamp': datetime.now().isoformat()
            }

            return indicators

        except Exception as e:
            logger.error(f"Error getting concept drift indicators: {e}")
            return {}

    def _log_prediction_validation(self, validation: Dict) -> bool:
        """Registrar validación de predicción"""
        if not self.connection:
            if not self.connect():
                return False

        try:
            cursor = self.connection.cursor()
            self._ensure_validation_table(cursor)

            insert_query = """
            INSERT INTO ml.prediction_validation (
                dispatch_id, prediction, actual, is_correct,
                confidence, confidence_calibration, prediction_error,
                features_json, validated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            values = (
                validation.get('dispatch_id'),
                validation.get('prediction'),
                validation.get('actual'),
                1 if validation.get('is_correct') else 0,
                validation.get('confidence'),
                validation.get('confidence_calibration'),
                validation.get('prediction_error'),
                json.dumps({}),  # Features will be added separately
                datetime.now()
            )

            cursor.execute(insert_query, values)
            self.connection.commit()
            cursor.close()

            return True

        except Exception as e:
            logger.error(f"Error logging prediction validation: {e}")
            return False

    def _ensure_validation_table(self, cursor):
        """Crear tabla de validación si no existe"""
        try:
            create_table_query = """
            IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES
                          WHERE TABLE_NAME = 'prediction_validation' AND TABLE_SCHEMA = 'ml')
            BEGIN
                CREATE TABLE ml.prediction_validation (
                    id INT PRIMARY KEY IDENTITY(1,1),
                    dispatch_id INT NOT NULL,
                    prediction INT NOT NULL,
                    actual INT NOT NULL,
                    is_correct BIT,
                    confidence FLOAT,
                    confidence_calibration FLOAT,
                    prediction_error FLOAT,
                    features_json NVARCHAR(MAX),
                    validated_at DATETIME2 DEFAULT GETDATE(),
                    INDEX idx_dispatch_id (dispatch_id),
                    INDEX idx_is_correct (is_correct),
                    INDEX idx_validated_at (validated_at)
                )
            END
            """
            cursor.execute(create_table_query)
            self.connection.commit()
        except Exception as e:
            logger.warning(f"Error ensuring validation table: {e}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    collector = RealDataCollector(
        server='192.168.1.38',
        database='ms_ml_despacho',
        username='sa',
        password='1234'
    )

    print("\n=== REAL DATA COLLECTOR TEST ===\n")

    if collector.connect():
        # Test validation
        print("Testing prediction validation...")
        validation = collector.validate_prediction(
            dispatch_id=123,
            actual_outcome=True,
            prediction=1,
            confidence=0.95
        )
        print(f"Validation result: {validation.get('is_correct')}")

        # Test metrics
        print("\nGetting validation metrics...")
        metrics = collector.get_validation_metrics(24)
        print(f"Total validations: {metrics.get('total_validations')}")

        # Test distribution
        print("\nGetting data distribution...")
        dist = collector.get_data_distribution(24)
        print(f"Positive rate: {dist.get('outcome_distribution', {}).get('positive_rate')}%")

        # Test drift indicators
        print("\nGetting drift indicators...")
        drift = collector.get_concept_drift_indicators(24, 168)
        print(f"Has drift: {drift.get('has_drift')}")

        collector.disconnect()
    else:
        print("Failed to connect to database")

    print("\n=== TEST COMPLETE ===\n")
