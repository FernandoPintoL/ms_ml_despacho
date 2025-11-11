"""
Drift Detection Module - Detectar cambios en la distribución de datos
Monitor si los datos actuales difieren significativamente de los datos de entrenamiento
"""

import logging
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta
import pyodbc
import json
import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


class DriftDetector:
    """
    Sistema de detección de drift (cambio de distribución)
    Monitorea cambios en features y predicciones
    """

    def __init__(self, server: str, database: str, username: str, password: str,
                 drift_threshold: float = 0.05):
        """
        Inicializar drift detector

        Args:
            server: Servidor SQL Server
            database: Nombre de BD
            username: Usuario
            password: Contraseña
            drift_threshold: Umbral para considerar drift (default 5%)
        """
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.connection = None
        self.drift_threshold = drift_threshold

        # Estadísticas de entrenamiento (para comparar)
        self.training_stats = {
            'confidence_mean': 0.91,  # De fase 2
            'confidence_std': 0.08,
            'phase1_mean': 0.82,
            'phase2_mean': 0.92,
            'fallback_rate': 0.02
        }

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
            logger.info("Connected to database for drift detection")
            return True
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            return False

    def disconnect(self):
        """Cerrar conexión"""
        if self.connection:
            self.connection.close()

    def detect_prediction_drift(self, hours: int = 24) -> Dict:
        """
        Detectar drift en predicciones
        Compara distribución actual vs entrenamiento

        Args:
            hours: Período en horas

        Returns:
            Diccionario con drift detection results
        """
        if not self.connection:
            if not self.connect():
                return {'error': 'No database connection'}

        try:
            cursor = self.connection.cursor()

            # Obtener predicciones recientes
            query = """
            SELECT
                AVG(CAST(JSON_VALUE(phase2_result_json, '$.confidence') as float)) as avg_confidence,
                STDEV(CAST(JSON_VALUE(phase2_result_json, '$.confidence') as float)) as std_confidence,
                COUNT(*) as count,
                AVG(CAST(JSON_VALUE(phase1_result_json, '$.confidence') as float)) as phase1_avg,
                AVG(CAST(JSON_VALUE(phase2_result_json, '$.confidence') as float)) as phase2_avg
            FROM ml.ab_test_log
            WHERE created_at > DATEADD(hour, -?, GETDATE())
            AND phase2_result_json IS NOT NULL
            """

            cursor.execute(query, (hours,))
            row = cursor.fetchone()

            if not row or not row[2]:  # No count
                cursor.close()
                return {
                    'has_drift': False,
                    'drift_type': 'insufficient_data',
                    'message': f'Less than {hours}h of data available'
                }

            current_avg_confidence = row[0] or 0
            current_std_confidence = row[1] or 0
            current_phase2_avg = row[4] or 0

            cursor.close()

            # Detecciones de drift
            drift_results = {
                'period_hours': hours,
                'timestamp': datetime.now().isoformat(),
                'current_metrics': {
                    'avg_confidence': round(current_avg_confidence, 4),
                    'std_confidence': round(current_std_confidence, 4),
                    'sample_count': int(row[2])
                },
                'training_metrics': {
                    'avg_confidence': self.training_stats['confidence_mean'],
                    'std_confidence': self.training_stats['confidence_std']
                },
                'drifts_detected': []
            }

            # 1. Detectar drift en confianza promedio
            confidence_drift = abs(current_avg_confidence - self.training_stats['confidence_mean'])
            confidence_drift_pct = (confidence_drift / self.training_stats['confidence_mean'] * 100) \
                if self.training_stats['confidence_mean'] > 0 else 0

            if confidence_drift_pct > self.drift_threshold * 100:
                drift_results['drifts_detected'].append({
                    'type': 'CONFIDENCE_DRIFT',
                    'severity': 'HIGH' if confidence_drift_pct > 15 else 'MEDIUM',
                    'current_value': round(current_avg_confidence, 4),
                    'training_value': self.training_stats['confidence_mean'],
                    'difference_percent': round(confidence_drift_pct, 2),
                    'message': f'Confianza promedio ha {'disminuido' if current_avg_confidence < self.training_stats['confidence_mean'] else 'aumentado'} {confidence_drift_pct:.2f}%'
                })

            # 2. Detectar drift en varianza
            variance_drift = abs(current_std_confidence - self.training_stats['confidence_std'])
            if variance_drift > 0.05:
                drift_results['drifts_detected'].append({
                    'type': 'VARIANCE_DRIFT',
                    'severity': 'MEDIUM',
                    'current_std': round(current_std_confidence, 4),
                    'training_std': self.training_stats['confidence_std'],
                    'difference': round(variance_drift, 4),
                    'message': 'Varianza de confianza ha cambiado significativamente'
                })

            drift_results['has_drift'] = len(drift_results['drifts_detected']) > 0
            drift_results['drift_count'] = len(drift_results['drifts_detected'])
            drift_results['severity'] = self._calculate_overall_severity(drift_results['drifts_detected'])

            return drift_results

        except Exception as e:
            logger.error(f"Error detecting drift: {e}")
            return {'error': str(e)}

    def detect_performance_degradation(self, hours: int = 24, comparison_hours: int = 72) -> Dict:
        """
        Detectar degradación de performance
        Compara período actual vs período anterior

        Args:
            hours: Período a analizar (último)
            comparison_hours: Período anterior para comparar

        Returns:
            Diccionario con degradation detection results
        """
        if not self.connection:
            if not self.connect():
                return {'error': 'No database connection'}

        try:
            cursor = self.connection.cursor()

            # Obtener métricas del período actual
            query_current = """
            SELECT
                AVG(CAST(JSON_VALUE(phase2_result_json, '$.confidence') as float)) as avg_confidence,
                COUNT(*) as count
            FROM ml.ab_test_log
            WHERE created_at > DATEADD(hour, -?, GETDATE())
            AND phase2_result_json IS NOT NULL
            """

            # Obtener métricas del período anterior
            query_previous = """
            SELECT
                AVG(CAST(JSON_VALUE(phase2_result_json, '$.confidence') as float)) as avg_confidence,
                COUNT(*) as count
            FROM ml.ab_test_log
            WHERE created_at > DATEADD(hour, -?, GETDATE())
            AND created_at <= DATEADD(hour, -?, GETDATE())
            AND phase2_result_json IS NOT NULL
            """

            cursor.execute(query_current, (hours,))
            current = cursor.fetchone()

            cursor.execute(query_previous, (comparison_hours, hours))
            previous = cursor.fetchone()

            cursor.close()

            current_confidence = current[0] or 0 if current else 0
            current_count = current[1] or 0 if current else 0
            previous_confidence = previous[0] or 0 if previous else 0
            previous_count = previous[1] or 0 if previous else 0

            degradation = {
                'period_hours': hours,
                'comparison_hours': comparison_hours,
                'timestamp': datetime.now().isoformat(),
                'current': {
                    'avg_confidence': round(current_confidence, 4),
                    'sample_count': int(current_count)
                },
                'previous': {
                    'avg_confidence': round(previous_confidence, 4),
                    'sample_count': int(previous_count)
                },
                'degradations': []
            }

            if previous_confidence > 0:
                # Calcular degradación
                confidence_change = current_confidence - previous_confidence
                confidence_change_pct = (confidence_change / previous_confidence * 100)

                degradation['confidence_change_percent'] = round(confidence_change_pct, 2)

                # Detectar degradación significativa
                if confidence_change_pct < -5:
                    degradation['degradations'].append({
                        'type': 'PERFORMANCE_DEGRADATION',
                        'severity': 'HIGH' if confidence_change_pct < -10 else 'MEDIUM',
                        'metric': 'confidence',
                        'change_percent': round(confidence_change_pct, 2),
                        'message': f'Performance ha degradado {abs(confidence_change_pct):.2f}% vs período anterior'
                    })

            degradation['has_degradation'] = len(degradation['degradations']) > 0
            degradation['degradation_count'] = len(degradation['degradations'])

            return degradation

        except Exception as e:
            logger.error(f"Error detecting degradation: {e}")
            return {'error': str(e)}

    def detect_data_quality_issues(self, hours: int = 24) -> Dict:
        """
        Detectar problemas de calidad de datos
        Verifica valores nulos, outliers, etc.

        Args:
            hours: Período en horas

        Returns:
            Diccionario con data quality issues
        """
        if not self.connection:
            if not self.connect():
                return {'error': 'No database connection'}

        try:
            cursor = self.connection.cursor()

            # Contar registros nulos
            query_nulls = """
            SELECT
                SUM(CASE WHEN phase2_result_json IS NULL THEN 1 ELSE 0 END) as null_phase2,
                COUNT(*) as total
            FROM ml.ab_test_log
            WHERE created_at > DATEADD(hour, -?, GETDATE())
            """

            cursor.execute(query_nulls, (hours,))
            null_row = cursor.fetchone()

            null_count = null_row[0] or 0 if null_row else 0
            total_count = null_row[1] or 0 if null_row else 0

            issues = {
                'period_hours': hours,
                'timestamp': datetime.now().isoformat(),
                'total_records': int(total_count),
                'quality_issues': []
            }

            # 1. Valores nulos
            null_pct = (null_count / total_count * 100) if total_count > 0 else 0
            if null_pct > 5:
                issues['quality_issues'].append({
                    'type': 'HIGH_NULL_RATE',
                    'severity': 'HIGH' if null_pct > 20 else 'MEDIUM',
                    'null_count': int(null_count),
                    'null_percentage': round(null_pct, 2),
                    'message': f'{null_pct:.2f}% de registros tienen phase2_result nulo'
                })

            # 2. Detectar outliers en confianza
            query_confidence = """
            SELECT
                CAST(JSON_VALUE(phase2_result_json, '$.confidence') as float) as confidence
            FROM ml.ab_test_log
            WHERE created_at > DATEADD(hour, -?, GETDATE())
            AND phase2_result_json IS NOT NULL
            """

            cursor.execute(query_confidence, (hours,))
            confidences = [row[0] for row in cursor.fetchall() if row[0] is not None]

            if len(confidences) > 10:  # Necesitamos mínimo de datos
                # Detectar outliers usando IQR
                q1 = np.percentile(confidences, 25)
                q3 = np.percentile(confidences, 75)
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr

                outliers = [c for c in confidences if c < lower_bound or c > upper_bound]
                outlier_pct = (len(outliers) / len(confidences) * 100) if len(confidences) > 0 else 0

                if outlier_pct > 5:
                    issues['quality_issues'].append({
                        'type': 'OUTLIERS_DETECTED',
                        'severity': 'MEDIUM',
                        'outlier_count': len(outliers),
                        'outlier_percentage': round(outlier_pct, 2),
                        'bounds': {
                            'lower': round(lower_bound, 4),
                            'upper': round(upper_bound, 4)
                        },
                        'message': f'{outlier_pct:.2f}% de valores de confianza son outliers'
                    })

            cursor.close()

            issues['has_issues'] = len(issues['quality_issues']) > 0
            issues['issue_count'] = len(issues['quality_issues'])

            return issues

        except Exception as e:
            logger.error(f"Error detecting data quality issues: {e}")
            return {'error': str(e)}

    def _ensure_drift_log_table(self, cursor):
        """Crear tabla de drift log si no existe"""
        try:
            create_table_query = """
            IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES
                          WHERE TABLE_NAME = 'drift_alerts' AND TABLE_SCHEMA = 'ml')
            BEGIN
                CREATE TABLE ml.drift_alerts (
                    id INT PRIMARY KEY IDENTITY(1,1),
                    drift_type NVARCHAR(50) NOT NULL,
                    severity NVARCHAR(20),
                    message NVARCHAR(MAX),
                    metrics_json NVARCHAR(MAX),
                    created_at DATETIME2 DEFAULT GETDATE(),
                    resolved DATETIME2,
                    INDEX idx_drift_type (drift_type),
                    INDEX idx_created_at (created_at)
                )
            END
            """
            cursor.execute(create_table_query)
            self.connection.commit()
        except Exception as e:
            logger.warning(f"Error ensuring drift_alerts table: {e}")

    def log_drift(self, drift_type: str, severity: str, message: str, metrics: Dict) -> bool:
        """Registrar alerta de drift"""
        if not self.connection:
            if not self.connect():
                return False

        try:
            cursor = self.connection.cursor()
            self._ensure_drift_log_table(cursor)

            insert_query = """
            INSERT INTO ml.drift_alerts (drift_type, severity, message, metrics_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """

            values = (
                drift_type,
                severity,
                message,
                json.dumps(metrics),
                datetime.now()
            )

            cursor.execute(insert_query, values)
            self.connection.commit()
            cursor.close()

            logger.info(f"Logged drift alert: {drift_type} ({severity})")
            return True

        except Exception as e:
            logger.error(f"Error logging drift: {e}")
            return False

    @staticmethod
    def _calculate_overall_severity(drifts: list) -> str:
        """Calcular severidad general basada en drifts detectados"""
        if not drifts:
            return 'NONE'

        severities = [d.get('severity', 'MEDIUM') for d in drifts]
        if 'HIGH' in severities:
            return 'HIGH'
        elif 'MEDIUM' in severities:
            return 'MEDIUM'
        else:
            return 'LOW'


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    detector = DriftDetector(
        server='192.168.1.38',
        database='ms_ml_despacho',
        username='sa',
        password='1234'
    )

    print("\n=== DRIFT DETECTION TEST ===\n")

    if detector.connect():
        # Test prediction drift
        print("Testing prediction drift detection...")
        drift_results = detector.detect_prediction_drift(24)
        print(f"Has drift: {drift_results.get('has_drift')}")
        print(f"Drifts detected: {drift_results.get('drift_count', 0)}")

        # Test degradation
        print("\nTesting performance degradation detection...")
        degradation = detector.detect_performance_degradation(24, 72)
        print(f"Has degradation: {degradation.get('has_degradation')}")

        # Test data quality
        print("\nTesting data quality detection...")
        quality = detector.detect_data_quality_issues(24)
        print(f"Quality issues: {quality.get('issue_count', 0)}")

        detector.disconnect()
    else:
        print("Failed to connect to database")

    print("\n=== TEST COMPLETE ===\n")
