"""
Real Data API
REST endpoints para recopilacion y validacion de datos reales
"""

from flask import Blueprint, jsonify, request
import logging
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data.real_data_collector import RealDataCollector

logger = logging.getLogger(__name__)

# Crear blueprint
real_data_bp = Blueprint(
    'real_data',
    __name__,
    url_prefix='/api/v5/data'
)

# Instancia global
_data_collector = None


def get_data_collector():
    """Obtener o inicializar RealDataCollector"""
    global _data_collector
    if _data_collector is None:
        _data_collector = RealDataCollector(
            server='192.168.1.38',
            database='ms_ml_despacho',
            username='sa',
            password='1234'
        )
    return _data_collector


# ============================================
# DATA VALIDATION ENDPOINTS
# ============================================

@real_data_bp.route('/validate', methods=['POST'])
def validate_prediction():
    """
    Validar predicción contra outcome real

    POST /api/v5/data/validate
    Body:
    {
        "dispatch_id": 123,
        "actual_outcome": true,
        "prediction": 1,
        "confidence": 0.95
    }
    """
    collector = get_data_collector()

    if not collector.connection:
        collector.connect()

    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No request body provided'
            }), 400

        dispatch_id = data.get('dispatch_id')
        actual_outcome = data.get('actual_outcome')
        prediction = data.get('prediction')
        confidence = data.get('confidence')

        if not all([dispatch_id, actual_outcome is not None, prediction is not None, confidence is not None]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: dispatch_id, actual_outcome, prediction, confidence'
            }), 400

        validation = collector.validate_prediction(
            dispatch_id=dispatch_id,
            actual_outcome=actual_outcome,
            prediction=prediction,
            confidence=confidence
        )

        return jsonify({
            'success': True,
            'validation': validation
        }), 200

    except Exception as e:
        logger.error(f"Error validating prediction: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@real_data_bp.route('/metrics', methods=['GET'])
def get_validation_metrics():
    """
    Obtener métricas de validación

    GET /api/v5/data/metrics?hours=24&phase=2
    """
    hours = request.args.get('hours', 24, type=int)
    phase = request.args.get('phase', None, type=int)

    collector = get_data_collector()

    if not collector.connection:
        collector.connect()

    try:
        metrics = collector.get_validation_metrics(hours, phase)

        return jsonify({
            'success': True,
            'metrics': metrics
        }), 200

    except Exception as e:
        logger.error(f"Error getting validation metrics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@real_data_bp.route('/distribution', methods=['GET'])
def get_data_distribution():
    """
    Obtener distribución de datos

    GET /api/v5/data/distribution?hours=24
    """
    hours = request.args.get('hours', 24, type=int)

    collector = get_data_collector()

    if not collector.connection:
        collector.connect()

    try:
        distribution = collector.get_data_distribution(hours)

        return jsonify({
            'success': True,
            'distribution': distribution
        }), 200

    except Exception as e:
        logger.error(f"Error getting data distribution: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@real_data_bp.route('/drift-indicators', methods=['GET'])
def get_drift_indicators():
    """
    Obtener indicadores de concept drift

    GET /api/v5/data/drift-indicators?hours=24&baseline_hours=168
    """
    hours = request.args.get('hours', 24, type=int)
    baseline_hours = request.args.get('baseline_hours', 168, type=int)

    collector = get_data_collector()

    if not collector.connection:
        collector.connect()

    try:
        indicators = collector.get_concept_drift_indicators(hours, baseline_hours)

        return jsonify({
            'success': True,
            'indicators': indicators
        }), 200

    except Exception as e:
        logger.error(f"Error getting drift indicators: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@real_data_bp.route('/training-data', methods=['GET'])
def get_training_data():
    """
    Obtener datos para reentrenamiento

    GET /api/v5/data/training-data?hours=24&min_quality=GOOD
    """
    hours = request.args.get('hours', 24, type=int)
    min_quality = request.args.get('min_quality', 'ACCEPTABLE', type=str)

    collector = get_data_collector()

    if not collector.connection:
        collector.connect()

    try:
        data, count = collector.get_training_data(hours, min_quality)

        return jsonify({
            'success': True,
            'training_data': data[:100],  # Limit to first 100 for API
            'total_available': count,
            'period_hours': hours,
            'min_quality': min_quality
        }), 200

    except Exception as e:
        logger.error(f"Error getting training data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@real_data_bp.route('/report', methods=['GET'])
def get_data_collection_report():
    """
    Obtener reporte completo de recopilación de datos

    GET /api/v5/data/report?hours=24
    """
    hours = request.args.get('hours', 24, type=int)

    collector = get_data_collector()

    if not collector.connection:
        collector.connect()

    try:
        metrics = collector.get_validation_metrics(hours)
        distribution = collector.get_data_distribution(hours)
        drift_indicators = collector.get_concept_drift_indicators(hours, 168)
        training_data, total_training = collector.get_training_data(hours)

        report = {
            'period_hours': hours,
            'timestamp': __import__('datetime').datetime.now().isoformat(),
            'validation_metrics': metrics,
            'data_distribution': distribution,
            'drift_indicators': drift_indicators,
            'training_data_available': total_training,
            'summary': {
                'data_quality': metrics.get('quality_level', 'UNKNOWN'),
                'accuracy': metrics.get('accuracy_percent', 0),
                'has_concept_drift': drift_indicators.get('has_drift', False),
                'positive_rate': distribution.get('outcome_distribution', {}).get('positive_rate', 0),
                'ready_for_retraining': total_training >= 100
            }
        }

        return jsonify({
            'success': True,
            'report': report
        }), 200

    except Exception as e:
        logger.error(f"Error generating data collection report: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("\n=== REAL DATA API TEST ===\n")

    collector = get_data_collector()
    if collector.connect():
        print("Connected to database")
        metrics = collector.get_validation_metrics(24)
        print(f"Validation metrics: {metrics}")
        collector.disconnect()

    print("\n=== TEST COMPLETE ===\n")
