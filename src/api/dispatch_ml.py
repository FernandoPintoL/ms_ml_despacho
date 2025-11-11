"""
Dispatch Assignment API Routes - Fase 2 con ML
Integra modelo XGBoost para predicciones inteligentes
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
import sys
import os
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ml.prediction_service import create_prediction_service

logger = logging.getLogger(__name__)

# Crear blueprint
dispatch_ml_bp = Blueprint(
    'dispatch_ml',
    __name__,
    url_prefix='/api/v2/dispatch'
)

# Inicializar servicio de predicciones (lazy)
_prediction_service = None


def get_prediction_service():
    """Obtener o inicializar servicio de predicciones"""
    global _prediction_service
    if _prediction_service is None:
        _prediction_service = create_prediction_service()
    return _prediction_service


# ============================================
# HEALTH CHECK ENDPOINT
# ============================================

@dispatch_ml_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint - Fase 2 con ML"""
    service = get_prediction_service()
    ml_status = 'loaded' if service is not None else 'failed'

    return jsonify({
        'status': 'healthy',
        'service': 'dispatch_assignment_ml',
        'phase': 2,
        'version': '2.0.0',
        'ml_status': ml_status,
        'timestamp': datetime.utcnow().isoformat(),
        'message': 'Fase 2 - Machine Learning with XGBoost - ONLINE'
    }), 200


# ============================================
# ML PREDICTION ENDPOINTS
# ============================================

@dispatch_ml_bp.route('/predict', methods=['POST'])
def predict_optimal_assignment():
    """
    Endpoint de predicción ML: determina si una asignación sería óptima

    POST /api/v2/dispatch/predict

    Request Body:
    {
        "dispatch_id": 123,
        "severity_level": 4,
        "hour_of_day": 14,
        "day_of_week": 2,
        "is_weekend": 0,
        "available_ambulances_count": 7,
        "nearest_ambulance_distance_km": 2.5,
        "paramedics_available_count": 10,
        "paramedics_senior_count": 5,
        "paramedics_junior_count": 5,
        "nurses_available_count": 3,
        "active_dispatches_count": 5,
        "ambulances_busy_percentage": 0.4,
        "average_response_time_minutes": 5.0,
        "actual_response_time_minutes": 4.5,
        "actual_travel_distance_km": 2.2,
        "optimization_score": 0.85,
        "paramedic_satisfaction_rating": 4,
        "patient_satisfaction_rating": 5
    }

    Response:
    {
        "success": true,
        "dispatch_id": 123,
        "prediction": 1,  // 0 = not optimal, 1 = optimal
        "confidence": 0.95,
        "probabilities": {
            "not_optimal": 0.05,
            "optimal": 0.95
        },
        "phase": 2,
        "recommendation": "ASSIGN - Assignment predicted to be optimal",
        "timestamp": "2025-11-11T00:45:00Z"
    }
    """
    service = get_prediction_service()

    if service is None:
        return jsonify({
            'success': False,
            'error': 'ML service not available'
        }), 503

    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No request body provided'
            }), 400

        # Validar campos requeridos para ML
        required_fields = [
            'severity_level', 'hour_of_day', 'day_of_week', 'is_weekend',
            'available_ambulances_count', 'nearest_ambulance_distance_km',
            'paramedics_available_count', 'paramedics_senior_count',
            'paramedics_junior_count', 'nurses_available_count',
            'active_dispatches_count', 'ambulances_busy_percentage',
            'average_response_time_minutes', 'actual_response_time_minutes',
            'actual_travel_distance_km', 'optimization_score',
            'paramedic_satisfaction_rating', 'patient_satisfaction_rating'
        ]

        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400

        # Hacer predicción
        pred_result = service.predict(data)

        if not pred_result['success']:
            return jsonify({
                'success': False,
                'error': pred_result['error']
            }), 400

        # Generar recomendación
        if pred_result['prediction'] == 1:
            recommendation = f"ASSIGN - Assignment predicted to be optimal (confidence: {pred_result['confidence']:.2%})"
        else:
            recommendation = f"REVIEW - Assignment may not be optimal (confidence: {pred_result['confidence']:.2%})"

        result = {
            'success': True,
            'dispatch_id': data.get('dispatch_id', -1),
            'prediction': pred_result['prediction'],
            'confidence': pred_result['confidence'],
            'probabilities': pred_result['probabilities'],
            'recommendation': recommendation,
            'phase': 2,
            'timestamp': datetime.utcnow().isoformat()
        }

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error in predict endpoint: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500


@dispatch_ml_bp.route('/predict/batch', methods=['POST'])
def predict_batch():
    """
    Endpoint para predicciones en lote

    POST /api/v2/dispatch/predict/batch

    Request Body:
    {
        "dispatches": [
            { ...prediction_request_1... },
            { ...prediction_request_2... }
        ]
    }

    Response:
    {
        "success": true,
        "total": 2,
        "successful": 2,
        "predictions": [
            { ...prediction_1_result... },
            { ...prediction_2_result... }
        ]
    }
    """
    service = get_prediction_service()

    if service is None:
        return jsonify({
            'success': False,
            'error': 'ML service not available'
        }), 503

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

        predictions = []
        successful = 0

        for dispatch_data in dispatches:
            pred_result = service.predict(dispatch_data)

            if pred_result['success']:
                if pred_result['prediction'] == 1:
                    recommendation = f"ASSIGN (confidence: {pred_result['confidence']:.2%})"
                else:
                    recommendation = f"REVIEW (confidence: {pred_result['confidence']:.2%})"

                result = {
                    'success': True,
                    'dispatch_id': dispatch_data.get('dispatch_id', -1),
                    'prediction': pred_result['prediction'],
                    'confidence': pred_result['confidence'],
                    'recommendation': recommendation
                }
                successful += 1
            else:
                result = {
                    'success': False,
                    'dispatch_id': dispatch_data.get('dispatch_id', -1),
                    'error': pred_result['error']
                }

            predictions.append(result)

        return jsonify({
            'success': successful == len(dispatches),
            'total': len(dispatches),
            'successful': successful,
            'phase': 2,
            'predictions': predictions
        }), 200

    except Exception as e:
        logger.error(f"Error in batch_predict: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500


# ============================================
# MODEL INFORMATION ENDPOINTS
# ============================================

@dispatch_ml_bp.route('/model/info', methods=['GET'])
def model_info():
    """Obtener información del modelo ML"""
    service = get_prediction_service()

    if service is None:
        return jsonify({
            'success': False,
            'error': 'ML service not available'
        }), 503

    return jsonify({
        'success': True,
        'model': {
            'type': 'XGBoost Classifier',
            'phase': 2,
            'status': 'trained',
            'performance': {
                'accuracy': 0.9000,
                'precision': 0.8933,
                'recall': 0.9710,
                'f1_score': 0.9306,
                'auc_roc': 0.9518
            },
            'features': len(service.feature_names),
            'feature_names': service.feature_names,
            'target': 'was_optimal (binary: 0=not_optimal, 1=optimal)'
        }
    }), 200


@dispatch_ml_bp.route('/model/feature-importance', methods=['GET'])
def feature_importance():
    """Obtener importancia de features del modelo"""
    service = get_prediction_service()

    if service is None:
        return jsonify({
            'success': False,
            'error': 'ML service not available'
        }), 503

    result = service.get_feature_importance()

    return jsonify({
        'success': result.get('success', False),
        'feature_importance': result.get('feature_importance', {}),
        'phase': 2
    }), 200


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Test
    service = get_prediction_service()
    if service:
        print("ML Service initialized successfully")
    else:
        print("Failed to initialize ML Service")
