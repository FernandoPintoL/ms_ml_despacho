"""
A/B Testing Dashboard API
Endpoints REST para visualizar y monitorear resultados de A/B testing
"""

from flask import Blueprint, jsonify, request
import logging
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from integration.ab_testing import ABTest, ABTestingStrategy, ABTestDashboard

logger = logging.getLogger(__name__)

# Crear blueprint
ab_testing_bp = Blueprint(
    'ab_testing',
    __name__,
    url_prefix='/api/v3/ab-testing'
)

# Instancia global de ABTest (se inicializa lazy)
_ab_test = None


def get_ab_test():
    """Obtener o inicializar instancia de ABTest"""
    global _ab_test
    if _ab_test is None:
        _ab_test = ABTest(
            server='192.168.1.38',
            database='ms_ml_despacho',
            username='sa',
            password='1234',
            strategy=ABTestingStrategy.RANDOM_50_50,
            phase2_weight=0.5
        )
    return _ab_test


# ============================================
# ENDPOINTS DE A/B TESTING
# ============================================

@ab_testing_bp.route('/status', methods=['GET'])
def ab_test_status():
    """
    Obtener estado actual del A/B test

    GET /api/v3/ab-testing/status
    """
    ab_test = get_ab_test()

    if not ab_test.connection:
        ab_test.connect()

    try:
        results = ab_test.get_ab_test_results(hours=24)

        return jsonify({
            'success': True,
            'strategy': results.get('strategy'),
            'total_tests_24h': results.get('total_tests', 0),
            'phase1_percentage': round(results.get('phase1_percentage', 0), 2),
            'phase2_percentage': round(results.get('phase2_percentage', 0), 2),
            'phase1_avg_confidence': round(results.get('phase1_avg_confidence', 0), 4),
            'phase2_avg_confidence': round(results.get('phase2_avg_confidence', 0), 4),
        }), 200

    except Exception as e:
        logger.error(f"Error getting A/B test status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ab_testing_bp.route('/dashboard', methods=['GET'])
def ab_test_dashboard():
    """
    Obtener dashboard completo de A/B test

    GET /api/v3/ab-testing/dashboard?hours=24
    """
    hours = request.args.get('hours', 24, type=int)

    ab_test = get_ab_test()

    if not ab_test.connection:
        ab_test.connect()

    try:
        report = ABTestDashboard.generate_report(ab_test, hours)

        return jsonify({
            'success': True,
            'report': report
        }), 200

    except Exception as e:
        logger.error(f"Error generating dashboard: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ab_testing_bp.route('/comparison', methods=['GET'])
def phase_comparison():
    """
    Comparación detallada de Fase 1 vs Fase 2

    GET /api/v3/ab-testing/comparison?hours=24
    """
    hours = request.args.get('hours', 24, type=int)

    ab_test = get_ab_test()

    if not ab_test.connection:
        ab_test.connect()

    try:
        comparison = ab_test.compare_phases(hours)

        return jsonify({
            'success': True,
            'comparison': comparison
        }), 200

    except Exception as e:
        logger.error(f"Error comparing phases: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ab_testing_bp.route('/decide-phase', methods=['POST'])
def decide_phase():
    """
    Decidir qué fase usar para una solicitud

    POST /api/v3/ab-testing/decide-phase
    Body: {"dispatch_id": 123}

    Response: {"phase": 1 or 2, "strategy": "random_50_50"}
    """
    ab_test = get_ab_test()

    if not ab_test.connection:
        ab_test.connect()

    try:
        data = request.get_json() or {}
        dispatch_id = data.get('dispatch_id')

        phase = ab_test.decide_phase(dispatch_id=dispatch_id)

        return jsonify({
            'success': True,
            'phase': phase,
            'strategy': ab_test.strategy,
            'dispatch_id': dispatch_id
        }), 200

    except Exception as e:
        logger.error(f"Error deciding phase: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ab_testing_bp.route('/log', methods=['POST'])
def log_ab_test():
    """
    Registrar resultado de A/B test

    POST /api/v3/ab-testing/log
    Body:
    {
        "dispatch_id": 123,
        "phase_used": 2,
        "phase1_result": {...},
        "phase2_result": {...}
    }
    """
    ab_test = get_ab_test()

    if not ab_test.connection:
        ab_test.connect()

    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No request body provided'
            }), 400

        dispatch_id = data.get('dispatch_id')
        phase_used = data.get('phase_used')
        phase1_result = data.get('phase1_result')
        phase2_result = data.get('phase2_result')

        if not dispatch_id or not phase_used:
            return jsonify({
                'success': False,
                'error': 'dispatch_id and phase_used are required'
            }), 400

        success = ab_test.log_ab_test(
            dispatch_id=dispatch_id,
            phase_used=phase_used,
            phase1_result=phase1_result,
            phase2_result=phase2_result
        )

        return jsonify({
            'success': success,
            'message': 'A/B test logged successfully'
        }), 200 if success else 500

    except Exception as e:
        logger.error(f"Error logging A/B test: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ab_testing_bp.route('/recommendation', methods=['GET'])
def get_recommendation():
    """
    Obtener recomendación basada en resultados

    GET /api/v3/ab-testing/recommendation?hours=24
    """
    hours = request.args.get('hours', 24, type=int)

    ab_test = get_ab_test()

    if not ab_test.connection:
        ab_test.connect()

    try:
        comparison = ab_test.compare_phases(hours)
        recommendation = ABTestDashboard._get_recommendation(comparison)

        return jsonify({
            'success': True,
            'recommendation': recommendation,
            'period_hours': hours,
            'data_available': bool(comparison.get('phase1', {}).get('total', 0) > 0)
        }), 200

    except Exception as e:
        logger.error(f"Error getting recommendation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ab_testing_bp.route('/metrics', methods=['GET'])
def get_metrics():
    """
    Obtener métricas detalladas por período

    GET /api/v3/ab-testing/metrics?hours=24
    """
    hours = request.args.get('hours', 24, type=int)

    ab_test = get_ab_test()

    if not ab_test.connection:
        ab_test.connect()

    try:
        results = ab_test.get_ab_test_results(hours)
        comparison = ab_test.compare_phases(hours)

        return jsonify({
            'success': True,
            'period_hours': hours,
            'distribution': {
                'phase1': {
                    'count': results.get('phase1_count', 0),
                    'percentage': round(results.get('phase1_percentage', 0), 2)
                },
                'phase2': {
                    'count': results.get('phase2_count', 0),
                    'percentage': round(results.get('phase2_percentage', 0), 2)
                }
            },
            'phase1_metrics': comparison.get('phase1', {}),
            'phase2_metrics': comparison.get('phase2', {}),
            'improvement': comparison.get('comparison', {})
        }), 200

    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ab_testing_bp.route('/strategies', methods=['GET'])
def get_available_strategies():
    """Obtener estrategias de A/B testing disponibles"""
    return jsonify({
        'success': True,
        'strategies': [
            {
                'name': ABTestingStrategy.RANDOM_50_50,
                'description': 'Random 50/50 split between Phase 1 and Phase 2',
                'use_case': 'General comparison'
            },
            {
                'name': ABTestingStrategy.ROUND_ROBIN,
                'description': 'Alternate between phases in round-robin fashion',
                'use_case': 'Consistent distribution'
            },
            {
                'name': ABTestingStrategy.TIME_BASED,
                'description': 'Different split based on time of day',
                'use_case': 'Peak vs off-peak testing'
            },
            {
                'name': ABTestingStrategy.WEIGHT_BASED,
                'description': 'Custom weight distribution',
                'use_case': 'Gradual rollout'
            }
        ]
    }), 200


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Test
    print("\n=== A/B TESTING DASHBOARD API TEST ===\n")

    ab_test = get_ab_test()
    if ab_test.connect():
        print("Connected to database")

        # Test phase decision
        phase = ab_test.decide_phase(dispatch_id=123)
        print(f"Decided phase: {phase}")

        # Test report generation
        report = ABTestDashboard.generate_report(ab_test, 24)
        print(f"Recommendation: {report.get('recommendation')}")

        ab_test.disconnect()
    else:
        print("Failed to connect")

    print("\n=== TEST COMPLETE ===\n")
