"""
REST API Routes
REST endpoints for dispatch, ambulance, and prediction operations
"""

from flask import Blueprint, request, jsonify
from typing import Dict, Any

from ..config.logger import LoggerMixin
from ..services import (
    PredictionService, OptimizationService, HealthService
)
from ..repositories import DispatchRepository, AmbulanceRepository


class RESTAPIMixin(LoggerMixin):
    """Mixin for REST API route handlers"""
    pass


def create_rest_routes(
    prediction_service: PredictionService,
    optimization_service: OptimizationService,
    health_service: HealthService,
    dispatch_repo: DispatchRepository,
    ambulance_repo: AmbulanceRepository
) -> Blueprint:
    """
    Create REST API blueprint

    Args:
        prediction_service: PredictionService instance
        optimization_service: OptimizationService instance
        health_service: HealthService instance
        dispatch_repo: DispatchRepository instance
        ambulance_repo: AmbulanceRepository instance

    Returns:
        Flask Blueprint with routes
    """

    api = Blueprint('api', __name__, url_prefix='/api/v1')

    # ============================================
    # DISPATCH ENDPOINTS
    # ============================================

    @api.route('/dispatches', methods=['POST'])
    def create_dispatch():
        """Create new dispatch"""
        try:
            data = request.get_json()

            dispatch_id = dispatch_repo.create_dispatch({
                'patient_name': data.get('patient_name'),
                'patient_age': data.get('patient_age'),
                'patient_lat': data.get('patient_lat'),
                'patient_lon': data.get('patient_lon'),
                'description': data.get('description'),
                'severity_level': data.get('severity_level', 3),
                'status': 'pending'
            })

            if dispatch_id:
                dispatch = dispatch_repo.get_dispatch(dispatch_id)
                return jsonify({
                    'success': True,
                    'dispatch_id': dispatch_id,
                    'dispatch': dispatch
                }), 201

            return jsonify({
                'success': False,
                'error': 'Failed to create dispatch'
            }), 400

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @api.route('/dispatches/<int:dispatch_id>', methods=['GET'])
    def get_dispatch(dispatch_id):
        """Get dispatch by ID"""
        try:
            dispatch = dispatch_repo.get_dispatch(dispatch_id)

            if dispatch:
                return jsonify({
                    'success': True,
                    'dispatch': dispatch
                }), 200

            return jsonify({
                'success': False,
                'error': 'Dispatch not found'
            }), 404

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @api.route('/dispatches/<int:dispatch_id>/status', methods=['PUT'])
    def update_dispatch_status(dispatch_id):
        """Update dispatch status"""
        try:
            data = request.get_json()
            status = data.get('status')

            success = dispatch_repo.update_dispatch_status(dispatch_id, status)

            if success:
                dispatch = dispatch_repo.get_dispatch(dispatch_id)
                return jsonify({
                    'success': True,
                    'dispatch': dispatch
                }), 200

            return jsonify({
                'success': False,
                'error': 'Failed to update status'
            }), 400

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @api.route('/dispatches/<int:dispatch_id>/optimize', methods=['POST'])
    def optimize_dispatch(dispatch_id):
        """Optimize dispatch with predictions"""
        try:
            dispatch = dispatch_repo.get_dispatch(dispatch_id)

            if not dispatch:
                return jsonify({
                    'success': False,
                    'error': 'Dispatch not found'
                }), 404

            plan = optimization_service.optimize_dispatch(
                dispatch_id=dispatch_id,
                patient_lat=dispatch['patient_lat'],
                patient_lon=dispatch['patient_lon'],
                description=dispatch['description'],
                severity_level=dispatch['severity_level'],
                destination_lat=dispatch.get('destination_lat'),
                destination_lon=dispatch.get('destination_lon')
            )

            return jsonify({
                'success': True,
                'plan': plan
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @api.route('/dispatches/recent', methods=['GET'])
    def get_recent_dispatches():
        """Get recent dispatches"""
        try:
            hours = request.args.get('hours', 24, type=int)
            limit = request.args.get('limit', 50, type=int)

            dispatches = dispatch_repo.get_recent_dispatches(limit, hours)

            return jsonify({
                'success': True,
                'count': len(dispatches),
                'dispatches': dispatches
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @api.route('/dispatches/statistics', methods=['GET'])
    def dispatch_statistics():
        """Get dispatch statistics"""
        try:
            hours = request.args.get('hours', 24, type=int)

            stats = dispatch_repo.get_dispatch_statistics(hours)

            return jsonify({
                'success': True,
                'statistics': stats
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    # ============================================
    # AMBULANCE ENDPOINTS
    # ============================================

    @api.route('/ambulances/<int:ambulance_id>', methods=['GET'])
    def get_ambulance(ambulance_id):
        """Get ambulance by ID"""
        try:
            ambulance = ambulance_repo.get_ambulance(ambulance_id)

            if ambulance:
                return jsonify({
                    'success': True,
                    'ambulance': ambulance
                }), 200

            return jsonify({
                'success': False,
                'error': 'Ambulance not found'
            }), 404

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @api.route('/ambulances/<int:ambulance_id>/location', methods=['PUT'])
    def update_ambulance_location(ambulance_id):
        """Update ambulance GPS location"""
        try:
            data = request.get_json()

            success = ambulance_repo.update_ambulance_location(
                ambulance_id=ambulance_id,
                latitude=data.get('latitude'),
                longitude=data.get('longitude'),
                accuracy=data.get('accuracy')
            )

            if success:
                ambulance = ambulance_repo.get_ambulance(ambulance_id)
                return jsonify({
                    'success': True,
                    'ambulance': ambulance
                }), 200

            return jsonify({
                'success': False,
                'error': 'Failed to update location'
            }), 400

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @api.route('/ambulances/<int:ambulance_id>/status', methods=['PUT'])
    def set_ambulance_status(ambulance_id):
        """Set ambulance status"""
        try:
            data = request.get_json()
            status = data.get('status')

            success = ambulance_repo.set_ambulance_status(ambulance_id, status)

            if success:
                ambulance = ambulance_repo.get_ambulance(ambulance_id)
                return jsonify({
                    'success': True,
                    'ambulance': ambulance
                }), 200

            return jsonify({
                'success': False,
                'error': 'Failed to update status'
            }), 400

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @api.route('/ambulances/available', methods=['GET'])
    def get_available_ambulances():
        """Get available ambulances"""
        try:
            ambulance_type = request.args.get('type')

            ambulances = ambulance_repo.get_available_ambulances(ambulance_type)

            return jsonify({
                'success': True,
                'count': len(ambulances),
                'ambulances': ambulances
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @api.route('/ambulances/nearby', methods=['GET'])
    def get_nearby_ambulances():
        """Get ambulances near location"""
        try:
            latitude = request.args.get('latitude', type=float)
            longitude = request.args.get('longitude', type=float)
            radius_km = request.args.get('radius_km', 10, type=float)
            limit = request.args.get('limit', 5, type=int)

            ambulances = ambulance_repo.get_available_ambulances_near(
                latitude, longitude, radius_km, limit
            )

            return jsonify({
                'success': True,
                'count': len(ambulances),
                'ambulances': ambulances
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @api.route('/ambulances/fleet-status', methods=['GET'])
    def fleet_status():
        """Get fleet status"""
        try:
            status = ambulance_repo.get_fleet_status()

            return jsonify({
                'success': True,
                'fleet': status
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    # ============================================
    # PREDICTION ENDPOINTS
    # ============================================

    @api.route('/predictions/severity', methods=['POST'])
    def predict_severity():
        """Predict severity level"""
        try:
            data = request.get_json()

            prediction = prediction_service.predict_severity(
                description=data.get('description'),
                vital_signs=data.get('vital_signs'),
                age=data.get('age')
            )

            return jsonify({
                'success': True,
                'prediction': prediction
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @api.route('/predictions/eta', methods=['POST'])
    def predict_eta():
        """Predict ETA"""
        try:
            data = request.get_json()

            prediction = prediction_service.predict_eta(
                origin_lat=data.get('origin_lat'),
                origin_lon=data.get('origin_lon'),
                destination_lat=data.get('destination_lat'),
                destination_lon=data.get('destination_lon'),
                traffic_level=data.get('traffic_level', 1),
                time_of_day=data.get('time_of_day')
            )

            return jsonify({
                'success': True,
                'prediction': prediction
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @api.route('/predictions/dispatch', methods=['POST'])
    def predict_dispatch_rest():
        """Predict full dispatch"""
        try:
            data = request.get_json()

            prediction = prediction_service.predict_dispatch(
                patient_lat=data.get('patient_lat'),
                patient_lon=data.get('patient_lon'),
                description=data.get('description'),
                vital_signs=data.get('vital_signs'),
                age=data.get('age'),
                required_ambulance_type=data.get('required_ambulance_type'),
                destination_lat=data.get('destination_lat'),
                destination_lon=data.get('destination_lon')
            )

            return jsonify({
                'success': True,
                'prediction': prediction
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    # ============================================
    # HEALTH & MONITORING ENDPOINTS
    # ============================================

    @api.route('/health', methods=['GET'])
    def health_check():
        """Quick health check"""
        try:
            status = health_service.get_quick_status()

            return jsonify(status), 200

        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': str(e)
            }), 500

    @api.route('/health/detailed', methods=['GET'])
    def detailed_health_check():
        """Detailed health check"""
        try:
            health = health_service.check_system_health()

            return jsonify(health), 200

        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': str(e)
            }), 500

    @api.route('/diagnostics', methods=['GET'])
    def diagnostics():
        """Get diagnostic report"""
        try:
            report = health_service.generate_diagnostic_report()

            return jsonify(report), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    return api
