"""
A/B Testing Framework - Sistema de pruebas A/B entre Fase 1 y Fase 2
Permite dividir tráfico y comparar performance de ambas fases
"""

import random
import logging
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta
import pyodbc
import json

logger = logging.getLogger(__name__)


class ABTestingStrategy:
    """Estrategias de división de tráfico"""

    RANDOM_50_50 = "random_50_50"
    ROUND_ROBIN = "round_robin"
    TIME_BASED = "time_based"
    WEIGHT_BASED = "weight_based"


class ABTest:
    """Sistema de A/B Testing para Fase 1 vs Fase 2"""

    def __init__(self, server: str, database: str, username: str, password: str,
                 strategy: str = ABTestingStrategy.RANDOM_50_50,
                 phase2_weight: float = 0.5):
        """
        Inicializar A/B Test

        Args:
            server: Servidor SQL Server
            database: Nombre de BD
            username: Usuario
            password: Contraseña
            strategy: Estrategia de división de tráfico
            phase2_weight: Peso de Fase 2 (0.0-1.0), default 0.5 (50%)
        """
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.connection = None
        self.strategy = strategy
        self.phase2_weight = phase2_weight
        self.request_counter = 0

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
            logger.info("Connected to database for A/B testing")
            return True
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            return False

    def disconnect(self):
        """Cerrar conexión"""
        if self.connection:
            self.connection.close()

    def decide_phase(self, dispatch_id: int = None) -> int:
        """
        Decidir qué fase usar para esta solicitud

        Args:
            dispatch_id: ID del dispatch (opcional, para consistencia)

        Returns:
            Fase a usar (1 o 2)
        """
        if self.strategy == ABTestingStrategy.RANDOM_50_50:
            return self._random_50_50()

        elif self.strategy == ABTestingStrategy.ROUND_ROBIN:
            return self._round_robin()

        elif self.strategy == ABTestingStrategy.TIME_BASED:
            return self._time_based()

        elif self.strategy == ABTestingStrategy.WEIGHT_BASED:
            return self._weight_based()

        else:
            # Default: random
            return self._random_50_50()

    def _random_50_50(self) -> int:
        """División aleatoria 50% Fase 1, 50% Fase 2"""
        return 2 if random.random() < self.phase2_weight else 1

    def _round_robin(self) -> int:
        """División round-robin: alterna entre fase 1 y 2"""
        self.request_counter += 1
        threshold = int(1.0 / self.phase2_weight)
        return 2 if (self.request_counter % threshold) == 0 else 1

    def _time_based(self) -> int:
        """División por tiempo: Fase 2 en horarios específicos"""
        hour = datetime.now().hour

        # Peak hours (9-17): más Fase 2 para validar en producción
        if 9 <= hour < 17:
            return 2 if random.random() < 0.7 else 1
        # Off-peak: más Fase 1 para estabilidad
        else:
            return 2 if random.random() < 0.3 else 1

    def _weight_based(self) -> int:
        """División por peso: según phase2_weight"""
        return 2 if random.random() < self.phase2_weight else 1

    def log_ab_test(self, dispatch_id: int, phase_used: int,
                   phase1_result: Dict = None, phase2_result: Dict = None) -> bool:
        """
        Registrar resultado de A/B test

        Args:
            dispatch_id: ID del dispatch
            phase_used: Fase utilizada (1 o 2)
            phase1_result: Resultado de Fase 1 (si se evaluó)
            phase2_result: Resultado de Fase 2 (si se evaluó)

        Returns:
            True si fue exitoso
        """
        if not self.connection:
            if not self.connect():
                return False

        try:
            cursor = self.connection.cursor()

            # Crear tabla si no existe
            self._ensure_ab_test_log_table(cursor)

            # Insertar registro
            insert_query = """
            INSERT INTO ml.ab_test_log (
                dispatch_id,
                phase_used,
                strategy,
                phase1_result_json,
                phase2_result_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """

            values = (
                dispatch_id,
                phase_used,
                self.strategy,
                json.dumps(phase1_result) if phase1_result else None,
                json.dumps(phase2_result) if phase2_result else None,
                datetime.now()
            )

            cursor.execute(insert_query, values)
            self.connection.commit()
            cursor.close()

            logger.info(f"Logged A/B test for dispatch {dispatch_id} (Phase {phase_used})")
            return True

        except Exception as e:
            logger.error(f"Error logging A/B test: {e}")
            return False

    def get_ab_test_results(self, hours: int = 24) -> Dict:
        """
        Obtener resultados de A/B test

        Args:
            hours: Período en horas

        Returns:
            Diccionario con estadísticas
        """
        if not self.connection:
            if not self.connect():
                return {}

        try:
            cursor = self.connection.cursor()

            # Contar uso de fases
            query = """
            SELECT
                phase_used,
                COUNT(*) as count,
                AVG(CAST(JSON_VALUE(phase1_result_json, '$.confidence') as float)) as phase1_avg_confidence,
                AVG(CAST(JSON_VALUE(phase2_result_json, '$.confidence') as float)) as phase2_avg_confidence
            FROM ml.ab_test_log
            WHERE created_at > DATEADD(hour, -?, GETDATE())
            GROUP BY phase_used
            """

            cursor.execute(query, (hours,))
            rows = cursor.fetchall()

            phase1_count = 0
            phase2_count = 0
            phase1_confidence = 0
            phase2_confidence = 0

            for row in rows:
                phase = row[0]
                count = row[1]
                avg_conf = row[2] or row[3]  # Use whichever is available

                if phase == 1:
                    phase1_count = count
                    phase1_confidence = avg_conf
                elif phase == 2:
                    phase2_count = count
                    phase2_confidence = avg_conf

            total = phase1_count + phase2_count

            cursor.close()

            return {
                'total_tests': total,
                'phase1_count': phase1_count,
                'phase2_count': phase2_count,
                'phase1_percentage': (phase1_count / total * 100) if total > 0 else 0,
                'phase2_percentage': (phase2_count / total * 100) if total > 0 else 0,
                'phase1_avg_confidence': phase1_confidence,
                'phase2_avg_confidence': phase2_confidence,
                'hours': hours,
                'strategy': self.strategy
            }

        except Exception as e:
            logger.error(f"Error getting A/B test results: {e}")
            return {}

    def compare_phases(self, hours: int = 24) -> Dict:
        """
        Comparación detallada de Fase 1 vs Fase 2

        Args:
            hours: Período en horas

        Returns:
            Diccionario con comparativa
        """
        if not self.connection:
            if not self.connect():
                return {}

        try:
            cursor = self.connection.cursor()

            # Obtener métricas de Fase 1
            query_phase1 = """
            SELECT
                COUNT(*) as total,
                AVG(CAST(JSON_VALUE(phase1_result_json, '$.confidence') as float)) as avg_confidence,
                MIN(CAST(JSON_VALUE(phase1_result_json, '$.confidence') as float)) as min_confidence,
                MAX(CAST(JSON_VALUE(phase1_result_json, '$.confidence') as float)) as max_confidence
            FROM ml.ab_test_log
            WHERE created_at > DATEADD(hour, -?, GETDATE())
            AND phase1_result_json IS NOT NULL
            """

            # Obtener métricas de Fase 2
            query_phase2 = """
            SELECT
                COUNT(*) as total,
                AVG(CAST(JSON_VALUE(phase2_result_json, '$.confidence') as float)) as avg_confidence,
                MIN(CAST(JSON_VALUE(phase2_result_json, '$.confidence') as float)) as min_confidence,
                MAX(CAST(JSON_VALUE(phase2_result_json, '$.confidence') as float)) as max_confidence
            FROM ml.ab_test_log
            WHERE created_at > DATEADD(hour, -?, GETDATE())
            AND phase2_result_json IS NOT NULL
            """

            cursor.execute(query_phase1, (hours,))
            phase1_row = cursor.fetchone()

            cursor.execute(query_phase2, (hours,))
            phase2_row = cursor.fetchone()

            cursor.close()

            phase1_stats = {
                'total': phase1_row[0] if phase1_row else 0,
                'avg_confidence': float(phase1_row[1] or 0) if phase1_row else 0,
                'min_confidence': float(phase1_row[2] or 0) if phase1_row else 0,
                'max_confidence': float(phase1_row[3] or 0) if phase1_row else 0,
            }

            phase2_stats = {
                'total': phase2_row[0] if phase2_row else 0,
                'avg_confidence': float(phase2_row[1] or 0) if phase2_row else 0,
                'min_confidence': float(phase2_row[2] or 0) if phase2_row else 0,
                'max_confidence': float(phase2_row[3] or 0) if phase2_row else 0,
            }

            # Calcular diferencias
            confidence_diff = phase2_stats['avg_confidence'] - phase1_stats['avg_confidence']
            confidence_improvement = (confidence_diff / phase1_stats['avg_confidence'] * 100) \
                if phase1_stats['avg_confidence'] > 0 else 0

            return {
                'period_hours': hours,
                'phase1': phase1_stats,
                'phase2': phase2_stats,
                'comparison': {
                    'confidence_difference': round(confidence_diff, 4),
                    'confidence_improvement_percent': round(confidence_improvement, 2),
                    'phase2_better': confidence_diff > 0,
                    'recommendation': 'Phase 2 performing better' if confidence_diff > 0.05
                              else 'Results similar' if abs(confidence_diff) <= 0.05
                              else 'Phase 1 more reliable'
                }
            }

        except Exception as e:
            logger.error(f"Error comparing phases: {e}")
            return {}

    def _ensure_ab_test_log_table(self, cursor):
        """Crear tabla de log si no existe"""
        try:
            create_table_query = """
            IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES
                          WHERE TABLE_NAME = 'ab_test_log' AND TABLE_SCHEMA = 'ml')
            BEGIN
                CREATE TABLE ml.ab_test_log (
                    id INT PRIMARY KEY IDENTITY(1,1),
                    dispatch_id INT NOT NULL,
                    phase_used INT NOT NULL,
                    strategy NVARCHAR(50),
                    phase1_result_json NVARCHAR(MAX),
                    phase2_result_json NVARCHAR(MAX),
                    created_at DATETIME2 DEFAULT GETDATE(),
                    INDEX idx_dispatch_id (dispatch_id),
                    INDEX idx_phase_used (phase_used),
                    INDEX idx_created_at (created_at)
                )
            END
            """
            cursor.execute(create_table_query)
            self.connection.commit()
        except Exception as e:
            logger.warning(f"Error ensuring ab_test_log table: {e}")


class ABTestDashboard:
    """Dashboard de métricas A/B test"""

    @staticmethod
    def generate_report(ab_test: ABTest, hours: int = 24) -> Dict:
        """
        Generar reporte completo de A/B test

        Args:
            ab_test: Instancia de ABTest
            hours: Período en horas

        Returns:
            Diccionario con reporte
        """
        results = ab_test.get_ab_test_results(hours)
        comparison = ab_test.compare_phases(hours)

        if not results or not comparison:
            return {'error': 'No data available'}

        return {
            'period': f"Last {hours} hours",
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_requests': results.get('total_tests', 0),
                'phase1_requests': results.get('phase1_count', 0),
                'phase2_requests': results.get('phase2_count', 0),
                'phase1_percentage': round(results.get('phase1_percentage', 0), 2),
                'phase2_percentage': round(results.get('phase2_percentage', 0), 2),
            },
            'phase1_metrics': {
                'total': comparison.get('phase1', {}).get('total', 0),
                'avg_confidence': round(comparison.get('phase1', {}).get('avg_confidence', 0), 4),
                'confidence_range': {
                    'min': round(comparison.get('phase1', {}).get('min_confidence', 0), 4),
                    'max': round(comparison.get('phase1', {}).get('max_confidence', 0), 4),
                }
            },
            'phase2_metrics': {
                'total': comparison.get('phase2', {}).get('total', 0),
                'avg_confidence': round(comparison.get('phase2', {}).get('avg_confidence', 0), 4),
                'confidence_range': {
                    'min': round(comparison.get('phase2', {}).get('min_confidence', 0), 4),
                    'max': round(comparison.get('phase2', {}).get('max_confidence', 0), 4),
                }
            },
            'comparison': comparison.get('comparison', {}),
            'strategy': results.get('strategy', 'unknown'),
            'recommendation': ABTestDashboard._get_recommendation(comparison)
        }

    @staticmethod
    def _get_recommendation(comparison: Dict) -> str:
        """Generar recomendación basada en resultados"""
        if not comparison or 'comparison' not in comparison:
            return "Insufficient data"

        comp = comparison['comparison']
        improvement = comp.get('confidence_improvement_percent', 0)

        if improvement > 10:
            return "Phase 2 showing significant improvement. Consider gradual rollout."
        elif improvement > 5:
            return "Phase 2 showing moderate improvement. Continue testing."
        elif improvement > 0:
            return "Phase 2 slightly better. Collect more data."
        elif improvement > -5:
            return "Results are similar. Both phases are viable."
        else:
            return "Phase 1 more reliable. Phase 2 needs optimization."


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Test
    ab_test = ABTest(
        server='192.168.1.38',
        database='ms_ml_despacho',
        username='sa',
        password='1234',
        strategy=ABTestingStrategy.RANDOM_50_50,
        phase2_weight=0.5
    )

    print("\n=== A/B TESTING FRAMEWORK TEST ===\n")

    if ab_test.connect():
        # Test phase decision
        print("Testing phase decisions (10 samples):")
        for i in range(10):
            phase = ab_test.decide_phase(dispatch_id=i)
            print(f"  Request {i+1}: Phase {phase}")

        print("\nGetting A/B test results...")
        results = ab_test.get_ab_test_results(24)
        print(f"Total tests: {results.get('total_tests')}")
        print(f"Phase 1: {results.get('phase1_percentage'):.1f}%")
        print(f"Phase 2: {results.get('phase2_percentage'):.1f}%")

        print("\nGenerating dashboard report...")
        report = ABTestDashboard.generate_report(ab_test, 24)
        print(f"Recommendation: {report.get('recommendation')}\n")

        ab_test.disconnect()
    else:
        print("Failed to connect to database")

    print("=== TEST COMPLETE ===\n")
