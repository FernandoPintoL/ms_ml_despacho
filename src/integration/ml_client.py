"""
ML Client - Cliente para integrarse con ms-despacho
Permite a ms-despacho hacer predicciones al modelo ML
"""

import requests
import logging
from typing import Dict, Optional, List
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class MLClient:
    """Cliente para hacer predicciones desde ms-despacho"""

    def __init__(self, ml_service_url: str = 'http://localhost:5000',
                 timeout: int = 5,
                 fallback_to_v1: bool = True):
        """
        Inicializar cliente ML

        Args:
            ml_service_url: URL del servicio ML
            timeout: Timeout en segundos
            fallback_to_v1: Si fallover a Fase 1 (reglas determinísticas)
        """
        self.ml_service_url = ml_service_url
        self.timeout = timeout
        self.fallback_to_v1 = fallback_to_v1
        self.v2_endpoint = f"{ml_service_url}/api/v2/dispatch/predict"
        self.v1_endpoint = f"{ml_service_url}/api/v1/dispatch/assign"
        self.health_endpoint = f"{ml_service_url}/api/v2/dispatch/health"

    def check_health(self) -> bool:
        """
        Verificar si el servicio ML está disponible

        Returns:
            True si está disponible, False si no
        """
        try:
            response = requests.get(self.health_endpoint, timeout=self.timeout)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"ML service health check failed: {e}")
            return False

    def predict(self, features: Dict) -> Dict:
        """
        Hacer predicción usando el modelo ML (Fase 2)

        Args:
            features: Diccionario con 18 características

        Returns:
            Diccionario con predicción
        """
        try:
            response = requests.post(
                self.v2_endpoint,
                json=features,
                timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"ML prediction successful for dispatch {features.get('dispatch_id')}")
                return result
            else:
                logger.error(f"ML prediction failed: {response.status_code}")
                if self.fallback_to_v1:
                    logger.info("Falling back to Phase 1 (deterministic rules)")
                    return self.fallback_to_phase1(features)
                return {
                    'success': False,
                    'error': f'ML service returned {response.status_code}'
                }

        except requests.Timeout:
            logger.warning("ML prediction timeout")
            if self.fallback_to_v1:
                return self.fallback_to_phase1(features)
            return {'success': False, 'error': 'Prediction timeout'}

        except Exception as e:
            logger.error(f"ML prediction error: {e}")
            if self.fallback_to_v1:
                return self.fallback_to_phase1(features)
            return {'success': False, 'error': str(e)}

    def predict_batch(self, features_list: List[Dict]) -> Dict:
        """
        Hacer predicciones en lote

        Args:
            features_list: Lista de diccionarios con características

        Returns:
            Diccionario con resultados
        """
        try:
            response = requests.post(
                f"{self.v2_endpoint}/batch",
                json={'dispatches': features_list},
                timeout=self.timeout * len(features_list)
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"ML batch prediction successful ({len(features_list)} items)")
                return result
            else:
                logger.error(f"ML batch prediction failed: {response.status_code}")
                return {
                    'success': False,
                    'total': len(features_list),
                    'predictions': []
                }

        except Exception as e:
            logger.error(f"ML batch prediction error: {e}")
            return {
                'success': False,
                'total': len(features_list),
                'predictions': []
            }

    def fallback_to_phase1(self, features: Dict) -> Dict:
        """
        Fallback a Fase 1 (reglas determinísticas)
        Convierte features ML al formato esperado por Fase 1

        Args:
            features: Diccionario con características ML

        Returns:
            Respuesta en formato compatible
        """
        try:
            # Convertir features ML al formato de Fase 1
            phase1_request = self._convert_to_phase1_format(features)

            response = requests.post(
                self.v1_endpoint,
                json=phase1_request,
                timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                result['fallback'] = True
                result['phase'] = 1
                logger.info(f"Phase 1 fallback successful for dispatch {features.get('dispatch_id')}")
                return result
            else:
                logger.error(f"Phase 1 fallback failed: {response.status_code}")
                return {
                    'success': False,
                    'error': f'Phase 1 fallback failed: {response.status_code}',
                    'fallback': True
                }

        except Exception as e:
            logger.error(f"Phase 1 fallback error: {e}")
            return {
                'success': False,
                'error': f'Phase 1 fallback error: {str(e)}',
                'fallback': True
            }

    @staticmethod
    def _convert_to_phase1_format(ml_features: Dict) -> Dict:
        """
        Convertir features ML al formato esperado por Fase 1

        Args:
            ml_features: Diccionario con features ML

        Returns:
            Diccionario con formato Fase 1
        """
        return {
            'dispatch_id': ml_features.get('dispatch_id'),
            'patient_latitude': ml_features.get('emergency_latitude', 4.71),
            'patient_longitude': ml_features.get('emergency_longitude', -74.07),
            'emergency_type': ml_features.get('emergency_type', 'trauma'),
            'severity_level': ml_features.get('severity_level', 3),
            'zone_code': ml_features.get('zone_code'),
            'available_ambulances': [
                {
                    'id': i,
                    'latitude': ml_features.get('latitude', 4.71),
                    'longitude': ml_features.get('longitude', -74.07),
                    'status': 'available',
                    'crew_level': 'senior' if i % 2 == 0 else 'junior',
                    'unit_type': 'advanced'
                }
                for i in range(1, ml_features.get('available_ambulances_count', 5) + 1)
            ],
            'available_paramedics': [
                {
                    'id': i,
                    'level': 'senior' if i <= ml_features.get('paramedics_senior_count', 2) else 'junior',
                    'status': 'available'
                }
                for i in range(1, ml_features.get('paramedics_available_count', 3) + 1)
            ],
            'available_nurses': [
                {'id': i, 'status': 'available'}
                for i in range(1, ml_features.get('nurses_available_count', 1) + 1)
            ]
        }

    def get_model_info(self) -> Dict:
        """Obtener información del modelo"""
        try:
            response = requests.get(
                f"{self.ml_service_url}/api/v2/dispatch/model/info",
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            return {'success': False}
        except Exception as e:
            logger.error(f"Error getting model info: {e}")
            return {'success': False}

    def get_feature_importance(self) -> Dict:
        """Obtener importancia de features"""
        try:
            response = requests.get(
                f"{self.ml_service_url}/api/v2/dispatch/model/feature-importance",
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            return {'success': False}
        except Exception as e:
            logger.error(f"Error getting feature importance: {e}")
            return {'success': False}


class MLClientPool:
    """Pool de conexiones para múltiples instancias de cliente"""

    def __init__(self, num_clients: int = 5, **kwargs):
        """
        Inicializar pool de clientes

        Args:
            num_clients: Número de instancias a mantener
            **kwargs: Argumentos para MLClient
        """
        self.clients = [MLClient(**kwargs) for _ in range(num_clients)]
        self.current_index = 0

    def get_client(self) -> MLClient:
        """Obtener siguiente cliente del pool (round-robin)"""
        client = self.clients[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.clients)
        return client

    def predict(self, features: Dict) -> Dict:
        """Hacer predicción usando cliente del pool"""
        client = self.get_client()
        return client.predict(features)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Test
    client = MLClient()

    print("\n=== ML CLIENT TEST ===\n")

    # Test health
    print("Testing health check...")
    is_healthy = client.check_health()
    print(f"Health: {is_healthy}\n")

    # Test prediction
    test_features = {
        'dispatch_id': 999,
        'severity_level': 4,
        'hour_of_day': 14,
        'day_of_week': 2,
        'is_weekend': 0,
        'available_ambulances_count': 7,
        'nearest_ambulance_distance_km': 2.5,
        'paramedics_available_count': 10,
        'paramedics_senior_count': 5,
        'paramedics_junior_count': 5,
        'nurses_available_count': 3,
        'active_dispatches_count': 5,
        'ambulances_busy_percentage': 0.4,
        'average_response_time_minutes': 5.0,
        'actual_response_time_minutes': 4.5,
        'actual_travel_distance_km': 2.2,
        'optimization_score': 0.85,
        'paramedic_satisfaction_rating': 4,
        'patient_satisfaction_rating': 5
    }

    print("Testing prediction...")
    result = client.predict(test_features)
    print(f"Result: {json.dumps(result, indent=2)}\n")

    # Test model info
    print("Testing model info...")
    info = client.get_model_info()
    print(f"Model: {info.get('model', {}).get('type')}")
    print(f"Performance: {info.get('model', {}).get('performance')}\n")

    print("=== TEST COMPLETE ===\n")
