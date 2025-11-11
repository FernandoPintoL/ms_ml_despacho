"""
Dispatch Assignment API Routes
REST endpoints for Fase 1 (deterministic assignment)
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
import sys
import os

# Agregar src al path para imports absolutos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logger = logging.getLogger(__name__)

# Crear blueprint
dispatch_assignment_bp = Blueprint(
    'dispatch_assignment',
    __name__,
    url_prefix='/api/v1/dispatch'
)

# Inicializar servicios (lazy initialization)
dispatch_service = None
assignment_history_repo = None
dispatch_repo = None

def init_services():
    """Inicializar servicios con BD cuando sea necesario"""
    global dispatch_service, assignment_history_repo, dispatch_repo

    try:
        from services.dispatch_assignment_service import DispatchAssignmentService
        from repositories.assignment_history_repository import AssignmentHistoryRepository
        from repositories.dispatch_repository import DispatchRepository

        dispatch_service = DispatchAssignmentService()
        assignment_history_repo = AssignmentHistoryRepository()
        dispatch_repo = DispatchRepository()
        logger.info("Services initialized successfully")
    except Exception as e:
        logger.warning(f"Could not initialize all services: {e}")


# ============================================
# HEALTH CHECK ENDPOINT
# ============================================

@dispatch_assignment_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint - Sin requerir BD"""
    return jsonify({
        'status': 'healthy',
        'service': 'dispatch_assignment',
        'phase': 1,
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat(),
        'message': 'Fase 1 - Deterministic Rules - ONLINE'
    }), 200


# ============================================
# MAIN ENDPOINTS
# ============================================

@dispatch_assignment_bp.route('/assign', methods=['POST'])
def assign_ambulance_and_personnel():
    """
    Endpoint principal: Asignar ambulancia y personal

    POST /api/v1/dispatch/assign

    Request Body:
    {
        "dispatch_id": 123,
        "patient_latitude": 4.7110,
        "patient_longitude": -74.0721,
        "emergency_type": "trauma",
        "severity_level": 4,
        "zone_code": "ZONA_1",
        "available_ambulances": [
            {
                "id": 1,
                "latitude": 4.7120,
                "longitude": -74.0700,
                "status": "available",
                "crew_level": "senior",
                "unit_type": "advanced"
            }
        ],
        "available_paramedics": [
            {"id": 1, "level": "senior", "status": "available"},
            {"id": 2, "level": "junior", "status": "available"}
        ],
        "available_nurses": [
            {"id": 10, "status": "available"}
        ]
    }

    Response:
    {
        "success": true,
        "dispatch_id": 123,
        "ambulance_id": 1,
        "paramedic_ids": [1, 2],
        "nurse_id": 10,
        "distance_km": 0.25,
        "confidence": 0.92,
        "assignment_type": "deterministic_rules",
        "phase": 1,
        "reasoning": "Ambulance 1 at 0.25km + 2 paramedics + nurse for critical case",
        "timestamp": "2025-11-10T12:34:56Z",
        "history_id": 456
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No request body provided'
            }), 400

        # Validar campos requeridos
        required_fields = [
            'dispatch_id',
            'patient_latitude',
            'patient_longitude',
            'emergency_type',
            'severity_level',
            'available_ambulances',
            'available_paramedics'
        ]

        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400

        # Llamar servicio
        result = dispatch_service.assign_ambulance_and_personnel(data)

        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error in assign endpoint: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500


@dispatch_assignment_bp.route('/assign/batch', methods=['POST'])
def batch_assign():
    """
    Endpoint para asignaciones en lote

    POST /api/v1/dispatch/assign/batch

    Request Body:
    {
        "dispatches": [
            { ...dispatch_data... },
            { ...dispatch_data... }
        ]
    }

    Response:
    {
        "success": true,
        "total": 2,
        "successful": 2,
        "failed": 0,
        "results": [...]
    }
    """
    try:
        data = request.get_json()

        if not data or 'dispatches' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing "dispatches" field'
            }), 400

        dispatches = data['dispatches']

        if not isinstance(dispatches, list):
            return jsonify({
                'success': False,
                'error': '"dispatches" must be a list'
            }), 400

        results = []
        successful = 0
        failed = 0

        for dispatch_data in dispatches:
            result = dispatch_service.assign_ambulance_and_personnel(dispatch_data)
            results.append(result)

            if result['success']:
                successful += 1
            else:
                failed += 1

        return jsonify({
            'success': failed == 0,
            'total': len(dispatches),
            'successful': successful,
            'failed': failed,
            'results': results
        }), 200

    except Exception as e:
        logger.error(f"Error in batch_assign: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500


# ============================================
# HISTORY ENDPOINTS
# ============================================

@dispatch_assignment_bp.route('/history/<int:dispatch_id>', methods=['GET'])
def get_assignment_history(dispatch_id):
    """
    Obtener histórico de asignación para un dispatch

    GET /api/v1/dispatch/history/123

    Response:
    {
        "success": true,
        "dispatch_id": 123,
        "assignment": {
            "id": 456,
            "dispatch_id": 123,
            "ambulance_id": 1,
            "paramedic_ids": [1, 2],
            "severity_level": 4,
            "response_time": 2.5,
            "created_at": "2025-11-10T12:30:00Z"
        }
    }
    """
    try:
        assignment = assignment_history_repo.get_assignment_by_dispatch(dispatch_id)

        if assignment:
            return jsonify({
                'success': True,
                'dispatch_id': dispatch_id,
                'assignment': dict(assignment)
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Assignment not found'
            }), 404

    except Exception as e:
        logger.error(f"Error getting assignment history: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500


@dispatch_assignment_bp.route('/history/recent', methods=['GET'])
def get_recent_assignments():
    """
    Obtener asignaciones recientes

    GET /api/v1/dispatch/history/recent?limit=50&hours=24

    Query Params:
    - limit: Número de registros (default: 50, max: 500)
    - hours: Últimas N horas (default: 24)

    Response:
    {
        "success": true,
        "count": 42,
        "limit": 50,
        "assignments": [...]
    }
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        hours = request.args.get('hours', 24, type=int)

        # Validar límites
        limit = min(limit, 500)
        limit = max(limit, 1)

        assignments = assignment_history_repo.get_recent_assignments(
            limit=limit,
            hours=hours
        )

        return jsonify({
            'success': True,
            'count': len(assignments),
            'limit': limit,
            'hours': hours,
            'assignments': [dict(a) for a in assignments]
        }), 200

    except Exception as e:
        logger.error(f"Error getting recent assignments: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500


@dispatch_assignment_bp.route('/history/ambulance/<int:ambulance_id>', methods=['GET'])
def get_ambulance_history(ambulance_id):
    """
    Obtener histórico de una ambulancia

    GET /api/v1/dispatch/history/ambulance/1

    Response:
    {
        "success": true,
        "ambulance_id": 1,
        "total_assignments": 45,
        "assignments": [...]
    }
    """
    try:
        assignments = assignment_history_repo.get_assignments_by_ambulance(ambulance_id)

        return jsonify({
            'success': True,
            'ambulance_id': ambulance_id,
            'total_assignments': len(assignments),
            'assignments': [dict(a) for a in assignments]
        }), 200

    except Exception as e:
        logger.error(f"Error getting ambulance history: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500


# ============================================
# STATISTICS ENDPOINTS
# ============================================

@dispatch_assignment_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """
    Obtener estadísticas de asignaciones

    GET /api/v1/dispatch/statistics?hours=24

    Query Params:
    - hours: Período en horas (default: 24)

    Response:
    {
        "success": true,
        "period_hours": 24,
        "statistics": {
            "total_assignments": 150,
            "optimal_assignments": 127,
            "optimal_rate": 84.67,
            "avg_response_time": 3.2,
            "avg_optimization_score": 0.85,
            "avg_patient_satisfaction": 4.2
        }
    }
    """
    try:
        hours = request.args.get('hours', 24, type=int)

        stats = assignment_history_repo.get_assignment_statistics(hours=hours)

        if stats:
            # Calcular tasa de optimalidad
            total = stats.get('total_assignments', 0)
            optimal = stats.get('optimal_count', 0)
            optimal_rate = (optimal / total * 100) if total > 0 else 0

            return jsonify({
                'success': True,
                'period_hours': hours,
                'statistics': {
                    'total_assignments': total,
                    'optimal_assignments': optimal,
                    'optimal_rate': round(optimal_rate, 2),
                    'avg_response_time': float(stats.get('avg_response_time', 0) or 0),
                    'avg_optimization_score': float(stats.get('avg_optimization_score', 0) or 0),
                    'avg_patient_satisfaction': float(stats.get('avg_patient_satisfaction', 0) or 0),
                    'unique_ambulances': stats.get('unique_ambulances', 0)
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No data available'
            }), 404

    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500


@dispatch_assignment_bp.route('/statistics/ambulance/<int:ambulance_id>', methods=['GET'])
def get_ambulance_statistics(ambulance_id):
    """
    Obtener estadísticas de una ambulancia

    GET /api/v1/dispatch/statistics/ambulance/1?hours=168

    Response:
    {
        "success": true,
        "ambulance_id": 1,
        "performance": {
            "total_assignments": 45,
            "optimal_assignments": 38,
            "optimal_rate": 84.44,
            "avg_response_time": 2.8,
            "avg_optimization_score": 0.87,
            "avg_patient_satisfaction": 4.4
        }
    }
    """
    try:
        hours = request.args.get('hours', 168, type=int)

        performance = assignment_history_repo.get_ambulance_performance(
            ambulance_id=ambulance_id,
            hours=hours
        )

        if performance:
            total = performance.get('total_assignments', 0)
            optimal = performance.get('optimal_assignments', 0)
            optimal_rate = (optimal / total * 100) if total > 0 else 0

            return jsonify({
                'success': True,
                'ambulance_id': ambulance_id,
                'period_hours': hours,
                'performance': {
                    'total_assignments': total,
                    'optimal_assignments': optimal,
                    'optimal_rate': round(optimal_rate, 2),
                    'avg_response_time': float(performance.get('avg_response_time', 0) or 0),
                    'avg_optimization_score': float(performance.get('avg_optimization_score', 0) or 0),
                    'avg_patient_satisfaction': float(performance.get('avg_patient_satisfaction', 0) or 0)
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'No data available'
            }), 404

    except Exception as e:
        logger.error(f"Error getting ambulance statistics: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500


@dispatch_assignment_bp.route('/statistics/severity-distribution', methods=['GET'])
def get_severity_distribution():
    """
    Obtener distribución por severidad

    GET /api/v1/dispatch/statistics/severity-distribution?hours=168

    Response:
    {
        "success": true,
        "period_hours": 168,
        "distribution": {
            "1": 5,
            "2": 15,
            "3": 45,
            "4": 60,
            "5": 25
        }
    }
    """
    try:
        hours = request.args.get('hours', 168, type=int)

        distribution = assignment_history_repo.get_severity_distribution(hours=hours)

        return jsonify({
            'success': True,
            'period_hours': hours,
            'distribution': {str(k): v for k, v in distribution.items()}
        }), 200

    except Exception as e:
        logger.error(f"Error getting severity distribution: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500
