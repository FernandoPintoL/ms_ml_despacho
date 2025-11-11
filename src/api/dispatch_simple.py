"""
Dispatch Assignment API Routes - Version Simple
"""

from flask import Blueprint, jsonify
from datetime import datetime

# Crear blueprint - SIN LOGGER NI IMPORTS COMPLICADOS
dispatch_assignment_bp = Blueprint(
    'dispatch_assignment',
    __name__,
    url_prefix='/api/v1/dispatch'
)


# ============================================
# HEALTH CHECK ENDPOINT
# ============================================

@dispatch_assignment_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint - Fase 1"""
    return jsonify({
        'status': 'healthy',
        'service': 'dispatch_assignment',
        'phase': 1,
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat(),
        'message': 'Fase 1 - Deterministic Rules - ONLINE'
    }), 200


@dispatch_assignment_bp.route('/test', methods=['GET'])
def test_endpoint():
    """Test endpoint para verificar que funciona"""
    return jsonify({
        'status': 'ok',
        'message': 'Dispatch Assignment API is working',
        'endpoints': [
            '/api/v1/dispatch/health',
            '/api/v1/dispatch/test',
            '/api/v1/dispatch/assign'
        ]
    }), 200


# ============================================
# MAIN ASSIGNMENT ENDPOINT
# ============================================

@dispatch_assignment_bp.route('/assign', methods=['POST'])
def assign_ambulance_and_personnel():
    """
    Endpoint principal: Asignar ambulancia y personal

    POST /api/v1/dispatch/assign
    """
    from flask import request
    import math

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

        # Haversine formula para calcular distancia GPS
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371  # Radio de la Tierra en km
            lat1_rad = math.radians(lat1)
            lon1_rad = math.radians(lon1)
            lat2_rad = math.radians(lat2)
            lon2_rad = math.radians(lon2)

            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad

            a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            return R * c

        # Buscar ambulancia más cercana
        ambulances = data.get('available_ambulances', [])
        patient_lat = data['patient_latitude']
        patient_lon = data['patient_longitude']

        best_ambulance = None
        min_distance = float('inf')

        for ambulance in ambulances:
            if ambulance.get('status') != 'available':
                continue

            distance = haversine(
                patient_lat, patient_lon,
                ambulance['latitude'], ambulance['longitude']
            )

            if distance < min_distance:
                min_distance = distance
                best_ambulance = ambulance

        if best_ambulance is None:
            return jsonify({
                'success': False,
                'error': 'No available ambulances found'
            }), 400

        # Determinar paramedics y nurses por severidad
        severity = data['severity_level']
        available_paramedics = data.get('available_paramedics', [])
        available_nurses = data.get('available_nurses', [])

        paramedic_count = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3}.get(severity, 1)
        needs_nurse = severity >= 4

        # Seleccionar paramedics
        selected_paramedics = [p['id'] for p in available_paramedics[:paramedic_count]]

        # Seleccionar nurse si es necesario
        selected_nurse = None
        if needs_nurse and available_nurses:
            selected_nurse = available_nurses[0]['id']

        # Calcular confianza (0.5 a 0.95 basado en distancia)
        max_distance = 15  # km
        confidence = max(0.5, 1.0 - (min_distance / max_distance) * 0.45)

        result = {
            'success': True,
            'dispatch_id': data['dispatch_id'],
            'ambulance_id': best_ambulance['id'],
            'paramedic_ids': selected_paramedics,
            'nurse_id': selected_nurse,
            'distance_km': round(min_distance, 2),
            'confidence': round(confidence, 2),
            'assignment_type': 'deterministic_rules',
            'phase': 1,
            'reasoning': f'Ambulance {best_ambulance["id"]} at {min_distance:.2f}km + {len(selected_paramedics)} paramedics' +
                         (f' + nurse' if selected_nurse else '') + f' for severity {severity}',
            'timestamp': datetime.utcnow().isoformat()
        }

        return jsonify(result), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500
