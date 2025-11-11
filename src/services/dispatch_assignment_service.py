"""
Dispatch Assignment Service - Fase 1 (Deterministic Rules)
Handles ambulance selection and paramedic assignment based on deterministic rules
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json
import logging
import math

from ..repositories.dispatch_repository import DispatchRepository
from ..repositories.assignment_history_repository import AssignmentHistoryRepository
from ..config.settings import Config

logger = logging.getLogger(__name__)


class DispatchAssignmentService:
    """
    Servicio para asignar ambulancias y personal según reglas determinísticas (Fase 1)

    Reglas Implementadas:
    1. Ambulancia más cercana disponible
    2. Validación de disponibilidad
    3. Asignación de personal según severidad
    """

    def __init__(
        self,
        dispatch_repo: DispatchRepository = None,
        assignment_history_repo: AssignmentHistoryRepository = None
    ):
        """
        Inicializar servicio

        Args:
            dispatch_repo: Repositorio de despachos
            assignment_history_repo: Repositorio de histórico de asignaciones
        """
        self.dispatch_repo = dispatch_repo
        self.assignment_history_repo = assignment_history_repo

        # Configuración de reglas para asignación de personal
        self.paramedic_assignment_rules = {
            5: {  # Crítico/Extremo
                'min_paramedics': 3,
                'levels': ['senior', 'senior', 'junior'],
                'include_nurse': True,
                'include_specialist': True,
                'description': 'Critical case - 3 paramedics + nurse + specialist'
            },
            4: {  # Alto
                'min_paramedics': 2,
                'levels': ['senior', 'junior'],
                'include_nurse': True,
                'include_specialist': False,
                'description': 'High severity - 2 paramedics + nurse'
            },
            3: {  # Medio
                'min_paramedics': 2,
                'levels': ['junior', 'junior'],
                'include_nurse': False,
                'include_specialist': False,
                'description': 'Medium severity - 2 paramedics'
            },
            2: {  # Bajo-Medio
                'min_paramedics': 1,
                'levels': ['junior'],
                'include_nurse': False,
                'include_specialist': False,
                'description': 'Low-Medium severity - 1 paramedic'
            },
            1: {  # Bajo
                'min_paramedics': 1,
                'levels': ['junior'],
                'include_nurse': False,
                'include_specialist': False,
                'description': 'Low severity - 1 paramedic'
            }
        }

    # ============================================
    # MAIN ASSIGNMENT LOGIC
    # ============================================

    def assign_ambulance_and_personnel(
        self,
        dispatch_data: Dict
    ) -> Dict:
        """
        Asignar ambulancia y personal según reglas determinísticas

        Args:
            dispatch_data: Dictionary con:
                - dispatch_id: INT
                - patient_latitude: FLOAT
                - patient_longitude: FLOAT
                - emergency_type: STR
                - severity_level: INT (1-5)
                - zone_code: STR (opcional)
                - available_ambulances: LIST of {id, lat, lon, status, crew_level}
                - available_paramedics: LIST of {id, level, status}
                - available_nurses: LIST of {id, status}

        Returns:
            Dictionary con:
                {
                    'success': BOOLEAN,
                    'ambulance_id': INT,
                    'paramedic_ids': LIST[INT],
                    'nurse_id': INT (opcional),
                    'confidence': FLOAT (0-1),
                    'assignment_type': STR ('nearest', 'fallback'),
                    'reasoning': STR,
                    'timestamp': DATETIME,
                    'error': STR (si aplica)
                }
        """
        try:
            dispatch_id = dispatch_data.get('dispatch_id')
            severity = dispatch_data.get('severity_level', 3)

            logger.info(f"Starting assignment process for dispatch {dispatch_id}")

            # Validar datos de entrada
            if not self._validate_input_data(dispatch_data):
                return self._error_response(
                    "Invalid input data",
                    dispatch_id
                )

            # ============================================
            # PASO 1: SELECCIONAR AMBULANCIA
            # ============================================
            ambulance_result = self._select_ambulance(dispatch_data)

            if not ambulance_result['success']:
                return ambulance_result

            ambulance_id = ambulance_result['ambulance_id']
            distance_km = ambulance_result['distance_km']
            confidence_ambulance = ambulance_result['confidence']

            logger.info(f"Ambulance {ambulance_id} selected at {distance_km}km")

            # ============================================
            # PASO 2: ASIGNAR PERSONAL
            # ============================================
            paramedic_result = self._assign_paramedics(
                dispatch_data,
                severity
            )

            if not paramedic_result['success']:
                return paramedic_result

            paramedic_ids = paramedic_result['paramedic_ids']
            nurse_id = paramedic_result.get('nurse_id')
            confidence_paramedics = paramedic_result['confidence']

            # ============================================
            # PASO 3: CALCULAR CONFIANZA GENERAL
            # ============================================
            overall_confidence = (confidence_ambulance + confidence_paramedics) / 2

            # ============================================
            # PASO 4: REGISTRAR EN HISTÓRICO
            # ============================================
            history_result = self._record_assignment_history(
                dispatch_data=dispatch_data,
                ambulance_id=ambulance_id,
                paramedic_ids=paramedic_ids,
                nurse_id=nurse_id
            )

            if not history_result['success']:
                logger.warning(f"Failed to record history for dispatch {dispatch_id}")

            # ============================================
            # PASO 5: RETORNAR RESULTADO
            # ============================================
            return {
                'success': True,
                'dispatch_id': dispatch_id,
                'ambulance_id': ambulance_id,
                'paramedic_ids': paramedic_ids,
                'nurse_id': nurse_id,
                'distance_km': distance_km,
                'confidence': overall_confidence,
                'assignment_type': 'deterministic_rules',
                'phase': 1,
                'reasoning': self._build_reasoning_string(
                    ambulance_result,
                    paramedic_result,
                    distance_km
                ),
                'timestamp': datetime.utcnow().isoformat(),
                'history_id': history_result.get('history_id')
            }

        except Exception as e:
            logger.error(f"Error in assignment process: {str(e)}")
            return self._error_response(f"Assignment failed: {str(e)}", dispatch_data.get('dispatch_id'))

    # ============================================
    # RULE 1: SELECT NEAREST AMBULANCE
    # ============================================

    def _select_ambulance(self, dispatch_data: Dict) -> Dict:
        """
        REGLA 1: Seleccionar ambulancia más cercana disponible

        Lógica:
        1. Filtrar ambulancias disponibles
        2. Calcular distancia de cada una
        3. Retornar la más cercana
        4. Fallback: si no hay cercanas, usar la siguiente disponible

        Args:
            dispatch_data: Datos de la solicitud

        Returns:
            {
                'success': BOOL,
                'ambulance_id': INT,
                'distance_km': FLOAT,
                'confidence': FLOAT (0-1),
                'reasoning': STR
            }
        """
        try:
            available_ambulances = dispatch_data.get('available_ambulances', [])

            if not available_ambulances:
                logger.warning("No ambulances available")
                return {
                    'success': False,
                    'error': 'No ambulances available'
                }

            patient_lat = dispatch_data.get('patient_latitude')
            patient_lon = dispatch_data.get('patient_longitude')

            if not patient_lat or not patient_lon:
                return {
                    'success': False,
                    'error': 'Patient location not provided'
                }

            # Calcular distancias y filtrar
            ambulances_with_distance = []

            for ambulance in available_ambulances:
                if ambulance.get('status') != 'available':
                    continue

                distance = self._calculate_distance(
                    patient_lat,
                    patient_lon,
                    ambulance.get('latitude'),
                    ambulance.get('longitude')
                )

                # Aplicar máxima distancia configurada
                if distance <= Config.AMBULANCE_MAX_DISTANCE_KM:
                    ambulances_with_distance.append({
                        'id': ambulance.get('id'),
                        'distance': distance,
                        'crew_level': ambulance.get('crew_level', 'junior'),
                        'unit_type': ambulance.get('unit_type', 'basic')
                    })

            if not ambulances_with_distance:
                logger.warning("No ambulances within maximum distance")
                return {
                    'success': False,
                    'error': 'No ambulances within service area'
                }

            # Ordenar por distancia y seleccionar la más cercana
            ambulances_with_distance.sort(key=lambda x: x['distance'])
            selected = ambulances_with_distance[0]

            # Calcular confianza basada en distancia
            # Si está a 0-2km: muy alta confianza (0.95+)
            # Si está a 2-5km: alta confianza (0.8-0.95)
            # Si está a 5-10km: media confianza (0.6-0.8)
            # Si está a 10-15km: baja confianza (0.4-0.6)

            distance = selected['distance']
            if distance <= 2:
                confidence = 0.95
            elif distance <= 5:
                confidence = 0.85
            elif distance <= 10:
                confidence = 0.7
            else:
                confidence = 0.5

            logger.info(f"Selected ambulance {selected['id']} at {distance}km (confidence: {confidence})")

            return {
                'success': True,
                'ambulance_id': selected['id'],
                'distance_km': round(distance, 2),
                'confidence': confidence,
                'crew_level': selected['crew_level'],
                'unit_type': selected['unit_type'],
                'reasoning': f"Nearest ambulance at {distance:.2f}km (crew: {selected['crew_level']})"
            }

        except Exception as e:
            logger.error(f"Error selecting ambulance: {str(e)}")
            return {
                'success': False,
                'error': f'Ambulance selection failed: {str(e)}'
            }

    # ============================================
    # RULE 2: ASSIGN PARAMEDICS BY SEVERITY
    # ============================================

    def _assign_paramedics(
        self,
        dispatch_data: Dict,
        severity_level: int
    ) -> Dict:
        """
        REGLA 3: Asignar personal según severidad

        Lógica:
        1. Obtener regla para severidad
        2. Buscar paramedics del nivel requerido
        3. Si no hay suficientes del nivel, buscar superiores
        4. Asignar nurse si es necesario

        Args:
            dispatch_data: Datos de solicitud
            severity_level: Nivel de severidad (1-5)

        Returns:
            {
                'success': BOOL,
                'paramedic_ids': LIST[INT],
                'nurse_id': INT (opcional),
                'confidence': FLOAT (0-1),
                'reasoning': STR
            }
        """
        try:
            # Obtener regla para esta severidad
            rule = self.paramedic_assignment_rules.get(severity_level)

            if not rule:
                logger.warning(f"No rule found for severity {severity_level}, using default")
                rule = self.paramedic_assignment_rules[3]  # Default: medium

            min_paramedics = rule.get('min_paramedics', 1)
            required_levels = rule.get('levels', ['junior'])
            include_nurse = rule.get('include_nurse', False)

            available_paramedics = dispatch_data.get('available_paramedics', [])
            available_nurses = dispatch_data.get('available_nurses', [])

            # Separar paramédicos por nivel
            senior_paramedics = [p for p in available_paramedics if p.get('level') == 'senior' and p.get('status') == 'available']
            junior_paramedics = [p for p in available_paramedics if p.get('level') == 'junior' and p.get('status') == 'available']

            assigned_paramedics = []

            # Asignar paramedics según regla
            for required_level in required_levels:
                if required_level == 'senior':
                    if senior_paramedics:
                        paramedic = senior_paramedics.pop(0)
                        assigned_paramedics.append(paramedic['id'])
                    elif junior_paramedics:
                        # Fallback: usar junior si no hay senior
                        paramedic = junior_paramedics.pop(0)
                        assigned_paramedics.append(paramedic['id'])
                    else:
                        logger.warning("No paramedics available for assignment")
                        return {
                            'success': False,
                            'error': 'No paramedics available'
                        }

                else:  # junior
                    if junior_paramedics:
                        paramedic = junior_paramedics.pop(0)
                        assigned_paramedics.append(paramedic['id'])
                    elif senior_paramedics:
                        # Fallback: usar senior si no hay junior
                        paramedic = senior_paramedics.pop(0)
                        assigned_paramedics.append(paramedic['id'])
                    else:
                        logger.warning("No paramedics available for assignment")
                        return {
                            'success': False,
                            'error': 'No paramedics available'
                        }

            # Validar mínimo de paramedics
            if len(assigned_paramedics) < min_paramedics:
                logger.warning(f"Not enough paramedics assigned ({len(assigned_paramedics)} < {min_paramedics})")

            # Asignar nurse si es requerido
            nurse_id = None
            if include_nurse:
                if available_nurses:
                    nurse_id = available_nurses[0]['id']

            # Calcular confianza
            confidence = 0.9 if len(assigned_paramedics) >= min_paramedics else 0.6

            reasoning = f"Severity {severity_level}: {len(assigned_paramedics)} paramedics"
            if nurse_id:
                reasoning += f" + nurse {nurse_id}"

            logger.info(f"Assigned paramedics: {assigned_paramedics}, confidence: {confidence}")

            return {
                'success': True,
                'paramedic_ids': assigned_paramedics,
                'nurse_id': nurse_id,
                'confidence': confidence,
                'reasoning': reasoning
            }

        except Exception as e:
            logger.error(f"Error assigning paramedics: {str(e)}")
            return {
                'success': False,
                'error': f'Paramedic assignment failed: {str(e)}'
            }

    # ============================================
    # HELPER FUNCTIONS
    # ============================================

    def _calculate_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calcular distancia en km entre dos puntos usando Haversine formula

        Args:
            lat1, lon1: Coordenadas punto 1
            lat2, lon2: Coordenadas punto 2

        Returns:
            Distancia en km
        """
        try:
            # Validar coordenadas
            if not all(isinstance(x, (int, float)) for x in [lat1, lon1, lat2, lon2]):
                logger.error(f"Invalid coordinates: {lat1}, {lon1}, {lat2}, {lon2}")
                return float('inf')

            # Radio de la tierra en km
            R = 6371.0

            # Convertir a radianes
            lat1_rad = math.radians(lat1)
            lon1_rad = math.radians(lon1)
            lat2_rad = math.radians(lat2)
            lon2_rad = math.radians(lon2)

            # Diferencias
            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad

            # Fórmula Haversine
            a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
            c = 2 * math.asin(math.sqrt(a))

            distance = R * c

            return distance

        except Exception as e:
            logger.error(f"Error calculating distance: {str(e)}")
            return float('inf')

    def _validate_input_data(self, dispatch_data: Dict) -> bool:
        """Validar que los datos de entrada sean correctos"""
        required_fields = [
            'dispatch_id',
            'patient_latitude',
            'patient_longitude',
            'severity_level',
            'emergency_type'
        ]

        for field in required_fields:
            if field not in dispatch_data:
                logger.error(f"Missing required field: {field}")
                return False

        return True

    def _record_assignment_history(
        self,
        dispatch_data: Dict,
        ambulance_id: int,
        paramedic_ids: List[int],
        nurse_id: Optional[int] = None
    ) -> Dict:
        """Registrar la asignación en histórico para entrenar ML"""
        try:
            if not self.assignment_history_repo:
                logger.warning("Assignment history repository not available")
                return {'success': False}

            history_data = {
                'dispatch_id': dispatch_data.get('dispatch_id'),
                'emergency_latitude': dispatch_data.get('patient_latitude'),
                'emergency_longitude': dispatch_data.get('patient_longitude'),
                'emergency_type': dispatch_data.get('emergency_type'),
                'severity_level': dispatch_data.get('severity_level'),
                'zone_code': dispatch_data.get('zone_code'),
                'available_ambulances_count': len(dispatch_data.get('available_ambulances', [])),
                'paramedics_available_count': len(dispatch_data.get('available_paramedics', [])),
                'assigned_ambulance_id': ambulance_id,
                'assigned_paramedic_ids': json.dumps(paramedic_ids),
                'assigned_paramedic_levels': json.dumps(['senior' if pid in [p['id'] for p in dispatch_data.get('available_paramedics', []) if p.get('level') == 'senior'] else 'junior' for pid in paramedic_ids])
            }

            history_id = self.assignment_history_repo.create_assignment_history(history_data)

            return {
                'success': True,
                'history_id': history_id
            }

        except Exception as e:
            logger.error(f"Error recording assignment history: {str(e)}")
            return {'success': False}

    def _build_reasoning_string(
        self,
        ambulance_result: Dict,
        paramedic_result: Dict,
        distance_km: float
    ) -> str:
        """Construir string explicativo del porqué de la asignación"""
        return f"Ambulance: {ambulance_result.get('reasoning')}. Personnel: {paramedic_result.get('reasoning')}"

    def _error_response(self, error_message: str, dispatch_id: Optional[int] = None) -> Dict:
        """Crear respuesta de error estándar"""
        return {
            'success': False,
            'dispatch_id': dispatch_id,
            'error': error_message,
            'timestamp': datetime.utcnow().isoformat(),
            'phase': 1
        }
