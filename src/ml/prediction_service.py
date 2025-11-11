"""
Prediction Service - Usa modelo XGBoost para prediciones en tiempo real
Servicio que carga el modelo entrenado y hace predicciones para nuevos casos
"""

import joblib
import numpy as np
import logging
from typing import Dict, List, Tuple
import os

logger = logging.getLogger(__name__)


class PredictionService:
    """Servicio de predicciones con modelo XGBoost"""

    def __init__(self, model_path: str = 'src/models/xgboost_model.pkl',
                 scaler_path: str = 'src/models/xgboost_model_scaler.pkl'):
        """
        Inicializar servicio de predicciones

        Args:
            model_path: Ruta al modelo entrenado
            scaler_path: Ruta al scaler de normalización
        """
        self.model_path = model_path
        self.scaler_path = scaler_path
        self.model = None
        self.scaler = None
        self.feature_names = [
            'severity_level', 'hour_of_day', 'day_of_week', 'is_weekend',
            'available_ambulances_count', 'nearest_ambulance_distance_km',
            'paramedics_available_count', 'paramedics_senior_count',
            'paramedics_junior_count', 'nurses_available_count',
            'active_dispatches_count', 'ambulances_busy_percentage',
            'average_response_time_minutes', 'actual_response_time_minutes',
            'actual_travel_distance_km', 'optimization_score',
            'paramedic_satisfaction_rating', 'patient_satisfaction_rating'
        ]

    def load_model(self) -> bool:
        """Cargar modelo entrenado"""
        try:
            if not os.path.exists(self.model_path):
                logger.error(f"Modelo no encontrado: {self.model_path}")
                return False

            self.model = joblib.load(self.model_path)
            logger.info(f"Modelo cargado: {self.model_path}")

            if os.path.exists(self.scaler_path):
                self.scaler = joblib.load(self.scaler_path)
                logger.info(f"Scaler cargado: {self.scaler_path}")
            else:
                logger.warning(f"Scaler no encontrado: {self.scaler_path}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error cargando modelo: {e}")
            return False

    def predict(self, features: Dict) -> Dict:
        """
        Hacer predicción para un caso

        Args:
            features: Diccionario con características

        Returns:
            Diccionario con predicción y confianza
        """
        if self.model is None:
            return {
                'success': False,
                'error': 'Modelo no cargado',
                'prediction': None,
                'confidence': None
            }

        try:
            # Extraer features en el orden correcto
            feature_values = []
            for feature_name in self.feature_names:
                if feature_name not in features:
                    logger.warning(f"Feature faltante: {feature_name}")
                    return {
                        'success': False,
                        'error': f'Feature faltante: {feature_name}',
                        'prediction': None,
                        'confidence': None
                    }
                feature_values.append(float(features[feature_name]))

            # Convertir a array
            X = np.array([feature_values])

            # Normalizar
            if self.scaler:
                X = self.scaler.transform(X)

            # Predicción
            prediction = self.model.predict(X)[0]
            prediction_proba = self.model.predict_proba(X)[0]

            # Confianza (probabilidad más alta)
            confidence = float(max(prediction_proba))

            return {
                'success': True,
                'prediction': int(prediction),
                'confidence': round(confidence, 4),
                'probabilities': {
                    'not_optimal': round(float(prediction_proba[0]), 4),
                    'optimal': round(float(prediction_proba[1]), 4)
                }
            }

        except Exception as e:
            logger.error(f"Error en predicción: {e}")
            return {
                'success': False,
                'error': str(e),
                'prediction': None,
                'confidence': None
            }

    def predict_batch(self, features_list: List[Dict]) -> Dict:
        """
        Hacer predicciones en lote

        Args:
            features_list: Lista de diccionarios con características

        Returns:
            Diccionario con predicciones
        """
        if self.model is None:
            return {
                'success': False,
                'error': 'Modelo no cargado',
                'predictions': []
            }

        try:
            predictions = []

            for idx, features in enumerate(features_list):
                result = self.predict(features)
                result['index'] = idx
                predictions.append(result)

            # Contar exitosas
            successful = sum(1 for p in predictions if p['success'])

            return {
                'success': successful == len(predictions),
                'total': len(predictions),
                'successful': successful,
                'predictions': predictions
            }

        except Exception as e:
            logger.error(f"Error en predicción batch: {e}")
            return {
                'success': False,
                'error': str(e),
                'predictions': []
            }

    def get_feature_importance(self) -> Dict:
        """Obtener importancia de features"""
        if self.model is None:
            return {'error': 'Modelo no cargado'}

        try:
            importance_dict = {}
            for name, importance in zip(self.feature_names, self.model.feature_importances_):
                importance_dict[name] = round(float(importance), 4)

            # Ordenar por importancia
            sorted_importance = dict(sorted(
                importance_dict.items(),
                key=lambda x: x[1],
                reverse=True
            ))

            return {
                'success': True,
                'feature_importance': sorted_importance
            }

        except Exception as e:
            logger.error(f"Error obteniendo feature importance: {e}")
            return {'error': str(e)}


def create_prediction_service() -> PredictionService:
    """Factory para crear e inicializar servicio de predicciones"""
    service = PredictionService()
    if service.load_model():
        return service
    else:
        logger.error("Fallo al cargar modelo")
        return None


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Crear servicio
    service = PredictionService()
    if not service.load_model():
        print("Error cargando modelo")
        exit(1)

    # Ejemplo de predicción
    test_features = {
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

    print("\n" + "=" * 70)
    print("SERVICIO DE PREDICCIONES")
    print("=" * 70)

    # Predicción individual
    print("\nTest de Predicción Individual:")
    result = service.predict(test_features)
    print(f"  Predicción: {'OPTIMAL' if result['prediction'] == 1 else 'NOT OPTIMAL'}")
    print(f"  Confianza: {result['confidence']:.2%}")
    print(f"  Probabilidades: {result['probabilities']}")

    # Feature importance
    print("\nFeature Importance (Top 5):")
    importance = service.get_feature_importance()
    top_5 = list(importance['feature_importance'].items())[:5]
    for feature, imp in top_5:
        print(f"  {feature:40s}: {imp:.4f}")

    print("\n" + "=" * 70)
