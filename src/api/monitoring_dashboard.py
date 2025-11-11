"""
Monitoring Dashboard API
REST endpoints para visualizar monitoreo y alertas del sistema
"""

from flask import Blueprint, jsonify, request
import logging
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from monitoring.drift_detector import DriftDetector
from monitoring.alert_manager import AlertManager, AlertType, AlertSeverity
from monitoring.health_checker import HealthChecker

logger = logging.getLogger(__name__)

# Crear blueprint
monitoring_bp = Blueprint(
    'monitoring',
    __name__,
    url_prefix='/api/v4/monitoring'
)

# Instancias globales (lazy initialization)
_drift_detector = None
_alert_manager = None
_health_checker = None


def get_drift_detector():
    """Obtener o inicializar DriftDetector"""
    global _drift_detector
    if _drift_detector is None:
        _drift_detector = DriftDetector(
            server='192.168.1.38',
            database='ms_ml_despacho',
            username='sa',
            password='1234'
        )
    return _drift_detector


def get_alert_manager():
    """Obtener o inicializar AlertManager"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager(
            server='192.168.1.38',
            database='ms_ml_despacho',
            username='sa',
            password='1234'
        )
    return _alert_manager


def get_health_checker():
    """Obtener o inicializar HealthChecker"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker(
            server='192.168.1.38',
            database='ms_ml_despacho',
            username='sa',
            password='1234'
        )
    return _health_checker


# ============================================
# HEALTH CHECK ENDPOINTS
# ============================================

@monitoring_bp.route('/health', methods=['GET'])
def system_health():
    """
    Obtener estado general del sistema

    GET /api/v4/monitoring/health
    """
    checker = get_health_checker()

    if not checker.connection:
        checker.connect()

    try:
        health = checker.get_overall_health()

        # Log health check
        checker.log_health_check(health)

        return jsonify({
            'success': True,
            'health': health
        }), 200

    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@monitoring_bp.route('/health/database', methods=['GET'])
def database_health():
    """
    Verificar salud de la base de datos

    GET /api/v4/monitoring/health/database
    """
    checker = get_health_checker()

    if not checker.connection:
        checker.connect()

    try:
        health = checker.check_database_health()
        return jsonify({
            'success': True,
            'database_health': health
        }), 200

    except Exception as e:
        logger.error(f"Error checking database health: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@monitoring_bp.route('/health/model', methods=['GET'])
def model_health():
    """
    Verificar salud del modelo ML

    GET /api/v4/monitoring/health/model
    """
    checker = get_health_checker()

    try:
        health = checker.check_model_health()
        return jsonify({
            'success': True,
            'model_health': health
        }), 200

    except Exception as e:
        logger.error(f"Error checking model health: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@monitoring_bp.route('/health/predictions', methods=['GET'])
def predictions_health():
    """
    Verificar salud del servicio de predicciones

    GET /api/v4/monitoring/health/predictions
    """
    checker = get_health_checker()

    if not checker.connection:
        checker.connect()

    try:
        health = checker.check_prediction_service_health()
        return jsonify({
            'success': True,
            'prediction_health': health
        }), 200

    except Exception as e:
        logger.error(f"Error checking prediction health: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@monitoring_bp.route('/health/fallback', methods=['GET'])
def fallback_health():
    """
    Verificar salud basada en fallbacks

    GET /api/v4/monitoring/health/fallback
    """
    checker = get_health_checker()

    if not checker.connection:
        checker.connect()

    try:
        health = checker.check_fallback_health()
        return jsonify({
            'success': True,
            'fallback_health': health
        }), 200

    except Exception as e:
        logger.error(f"Error checking fallback health: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# DRIFT DETECTION ENDPOINTS
# ============================================

@monitoring_bp.route('/drift/prediction', methods=['GET'])
def detect_prediction_drift():
    """
    Detectar drift en predicciones

    GET /api/v4/monitoring/drift/prediction?hours=24
    """
    hours = request.args.get('hours', 24, type=int)

    detector = get_drift_detector()

    if not detector.connection:
        detector.connect()

    try:
        drift = detector.detect_prediction_drift(hours)

        # Crear alerta si hay drift detectado
        if drift.get('has_drift'):
            manager = get_alert_manager()
            if not manager.connection:
                manager.connect()

            for drift_item in drift.get('drifts_detected', []):
                manager.create_alert(
                    alert_type=AlertType.DRIFT_DETECTED,
                    severity=AlertSeverity[drift_item.get('severity', 'MEDIUM')],
                    title=f"Drift Detected: {drift_item.get('type')}",
                    description=drift_item.get('message'),
                    details=drift_item
                )
                # Log drift
                detector.log_drift(
                    drift_type=drift_item.get('type'),
                    severity=drift_item.get('severity'),
                    message=drift_item.get('message'),
                    metrics=drift_item
                )

        return jsonify({
            'success': True,
            'drift_detection': drift
        }), 200

    except Exception as e:
        logger.error(f"Error detecting drift: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@monitoring_bp.route('/drift/performance', methods=['GET'])
def detect_performance_drift():
    """
    Detectar degradación de performance

    GET /api/v4/monitoring/drift/performance?hours=24&comparison_hours=72
    """
    hours = request.args.get('hours', 24, type=int)
    comparison_hours = request.args.get('comparison_hours', 72, type=int)

    detector = get_drift_detector()

    if not detector.connection:
        detector.connect()

    try:
        degradation = detector.detect_performance_degradation(hours, comparison_hours)

        # Crear alerta si hay degradación
        if degradation.get('has_degradation'):
            manager = get_alert_manager()
            if not manager.connection:
                manager.connect()

            for deg_item in degradation.get('degradations', []):
                manager.create_alert(
                    alert_type=AlertType.PERFORMANCE_DEGRADATION,
                    severity=AlertSeverity[deg_item.get('severity', 'MEDIUM')],
                    title=f"Performance Degradation Detected",
                    description=deg_item.get('message'),
                    details=deg_item
                )

        return jsonify({
            'success': True,
            'performance_degradation': degradation
        }), 200

    except Exception as e:
        logger.error(f"Error detecting performance drift: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@monitoring_bp.route('/drift/data-quality', methods=['GET'])
def detect_data_quality_drift():
    """
    Detectar problemas de calidad de datos

    GET /api/v4/monitoring/drift/data-quality?hours=24
    """
    hours = request.args.get('hours', 24, type=int)

    detector = get_drift_detector()

    if not detector.connection:
        detector.connect()

    try:
        quality = detector.detect_data_quality_issues(hours)

        # Crear alertas si hay problemas
        if quality.get('has_issues'):
            manager = get_alert_manager()
            if not manager.connection:
                manager.connect()

            for issue in quality.get('quality_issues', []):
                manager.create_alert(
                    alert_type=AlertType.DATA_QUALITY,
                    severity=AlertSeverity[issue.get('severity', 'MEDIUM')],
                    title=f"Data Quality Issue: {issue.get('type')}",
                    description=issue.get('message'),
                    details=issue
                )

        return jsonify({
            'success': True,
            'data_quality': quality
        }), 200

    except Exception as e:
        logger.error(f"Error detecting data quality issues: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# ALERT ENDPOINTS
# ============================================

@monitoring_bp.route('/alerts/active', methods=['GET'])
def get_active_alerts():
    """
    Obtener todas las alertas activas

    GET /api/v4/monitoring/alerts/active
    """
    manager = get_alert_manager()

    if not manager.connection:
        manager.connect()

    try:
        alerts = manager.get_active_alerts()

        return jsonify({
            'success': True,
            'active_alerts': alerts,
            'count': len(alerts)
        }), 200

    except Exception as e:
        logger.error(f"Error getting active alerts: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@monitoring_bp.route('/alerts/history', methods=['GET'])
def get_alert_history():
    """
    Obtener historial de alertas

    GET /api/v4/monitoring/alerts/history?days=7
    """
    days = request.args.get('days', 7, type=int)

    manager = get_alert_manager()

    if not manager.connection:
        manager.connect()

    try:
        alerts = manager.get_alert_history(days)

        return jsonify({
            'success': True,
            'alert_history': alerts,
            'period_days': days,
            'count': len(alerts)
        }), 200

    except Exception as e:
        logger.error(f"Error getting alert history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@monitoring_bp.route('/alerts/statistics', methods=['GET'])
def get_alert_statistics():
    """
    Obtener estadísticas de alertas

    GET /api/v4/monitoring/alerts/statistics?days=7
    """
    days = request.args.get('days', 7, type=int)

    manager = get_alert_manager()

    if not manager.connection:
        manager.connect()

    try:
        stats = manager.get_alert_statistics(days)

        return jsonify({
            'success': True,
            'alert_statistics': stats
        }), 200

    except Exception as e:
        logger.error(f"Error getting alert statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@monitoring_bp.route('/alerts/<int:alert_id>/resolve', methods=['POST'])
def resolve_alert(alert_id):
    """
    Marcar alerta como resuelta

    POST /api/v4/monitoring/alerts/<alert_id>/resolve
    Body: {"resolution_notes": "..."}
    """
    manager = get_alert_manager()

    if not manager.connection:
        manager.connect()

    try:
        data = request.get_json() or {}
        resolution_notes = data.get('resolution_notes')

        success = manager.resolve_alert(alert_id, resolution_notes)

        return jsonify({
            'success': success,
            'message': 'Alert resolved' if success else 'Failed to resolve alert'
        }), 200 if success else 500

    except Exception as e:
        logger.error(f"Error resolving alert: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# DASHBOARD ENDPOINT
# ============================================

@monitoring_bp.route('/dashboard', methods=['GET'])
def monitoring_dashboard():
    """
    Dashboard completo de monitoreo

    GET /api/v4/monitoring/dashboard
    """
    checker = get_health_checker()
    detector = get_drift_detector()
    manager = get_alert_manager()

    if not checker.connection:
        checker.connect()
    if not detector.connection:
        detector.connect()
    if not manager.connection:
        manager.connect()

    try:
        # Recopilar todos los datos
        health = checker.get_overall_health()
        drift = detector.detect_prediction_drift(24)
        degradation = detector.detect_performance_degradation(24, 72)
        quality = detector.detect_data_quality_issues(24)
        active_alerts = manager.get_active_alerts()
        alert_stats = manager.get_alert_statistics(7)

        dashboard = {
            'timestamp': __import__('datetime').datetime.now().isoformat(),
            'overall_health': health,
            'drift_detection': {
                'prediction': drift,
                'performance': degradation,
                'data_quality': quality
            },
            'alerts': {
                'active_count': len(active_alerts),
                'active_alerts': active_alerts[:10],  # Top 10
                'statistics': alert_stats
            },
            'summary': {
                'system_status': health.get('overall_status'),
                'critical_issues': sum(1 for a in active_alerts if a.get('severity') == 'CRITICAL'),
                'high_severity': sum(1 for a in active_alerts if a.get('severity') == 'HIGH'),
                'drifts_detected': drift.get('drift_count', 0),
                'performance_degradations': degradation.get('degradation_count', 0),
                'data_quality_issues': quality.get('issue_count', 0)
            }
        }

        return jsonify({
            'success': True,
            'dashboard': dashboard
        }), 200

    except Exception as e:
        logger.error(f"Error generating dashboard: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("\n=== MONITORING DASHBOARD API TEST ===\n")

    # Test drift detection
    detector = get_drift_detector()
    if detector.connect():
        print("Connected to database")
        drift = detector.detect_prediction_drift(24)
        print(f"Drift detection result: {drift.get('has_drift')}")
        detector.disconnect()

    print("\n=== TEST COMPLETE ===\n")
