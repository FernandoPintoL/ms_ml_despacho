"""
Model Optimizer - Optimizaciones y mejoras avanzadas
Feature engineering, ensemble learning, y hyperparameter optimization
"""

import logging
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from xgboost import XGBClassifier
import lightgbm as lgb

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Feature engineering avanzado"""

    @staticmethod
    def create_interaction_features(df: pd.DataFrame) -> pd.DataFrame:
        """Crear features de interacción"""
        try:
            new_df = df.copy()

            # Interacciones importantes
            if 'severity_level' in df.columns and 'distance_km' in df.columns:
                new_df['severity_distance_interaction'] = df['severity_level'] * df['distance_km']

            if 'available_ambulances' in df.columns and 'response_time_minutes' in df.columns:
                new_df['availability_response_interaction'] = df['available_ambulances'] * df['response_time_minutes']

            if 'senior_paramedics' in df.columns and 'patient_age' in df.columns:
                new_df['expertise_age_interaction'] = df['senior_paramedics'] * df['patient_age']

            logger.info(f"Created interaction features: {new_df.shape[1] - df.shape[1]} new features")
            return new_df
        except Exception as e:
            logger.error(f"Error creating interaction features: {e}")
            return df

    @staticmethod
    def create_polynomial_features(df: pd.DataFrame, degree: int = 2) -> pd.DataFrame:
        """Crear features polinomiales para relaciones no-lineales"""
        try:
            new_df = df.copy()

            # Features importantes para polinomios
            poly_features = ['distance_km', 'response_time_minutes', 'availability_index']
            existing_poly = [f for f in poly_features if f in df.columns]

            if existing_poly:
                poly = PolynomialFeatures(degree=degree, include_bias=False)
                X_poly = poly.fit_transform(df[existing_poly])
                feature_names = poly.get_feature_names_out(existing_poly)

                for i, name in enumerate(feature_names):
                    if name not in new_df.columns:
                        new_df[f'poly_{name}'] = X_poly[:, i]

            logger.info(f"Created polynomial features")
            return new_df
        except Exception as e:
            logger.error(f"Error creating polynomial features: {e}")
            return df

    @staticmethod
    def create_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
        """Crear features temporales"""
        try:
            new_df = df.copy()

            if 'hour_of_day' in df.columns:
                # Peak hours indicator
                new_df['is_peak_hours'] = ((df['hour_of_day'] >= 9) & (df['hour_of_day'] < 17)).astype(int)

                # Morning/Afternoon/Night
                new_df['is_morning'] = ((df['hour_of_day'] >= 6) & (df['hour_of_day'] < 12)).astype(int)
                new_df['is_afternoon'] = ((df['hour_of_day'] >= 12) & (df['hour_of_day'] < 18)).astype(int)
                new_df['is_night'] = ((df['hour_of_day'] >= 18) | (df['hour_of_day'] < 6)).astype(int)

            if 'day_of_week' in df.columns:
                # Weekend indicator
                new_df['is_weekend'] = ((df['day_of_week'] >= 5) & (df['day_of_week'] <= 6)).astype(int)

            logger.info("Created temporal features")
            return new_df
        except Exception as e:
            logger.error(f"Error creating temporal features: {e}")
            return df

    @staticmethod
    def create_aggregated_features(df: pd.DataFrame) -> pd.DataFrame:
        """Crear features agregadas"""
        try:
            new_df = df.copy()

            # Agregaciones de recursos
            if 'senior_paramedics' in df.columns and 'junior_paramedics' in df.columns:
                new_df['total_paramedics'] = df['senior_paramedics'] + df['junior_paramedics']
                new_df['senior_ratio'] = df['senior_paramedics'] / (new_df['total_paramedics'] + 1e-6)

            # Satisfacción promedio
            if 'patient_satisfaction' in df.columns and 'paramedic_satisfaction' in df.columns:
                new_df['avg_satisfaction'] = (df['patient_satisfaction'] + df['paramedic_satisfaction']) / 2

            logger.info("Created aggregated features")
            return new_df
        except Exception as e:
            logger.error(f"Error creating aggregated features: {e}")
            return df


class EnsembleModelBuilder:
    """Constructor de modelos ensemble"""

    @staticmethod
    def build_voting_ensemble(X_train: np.ndarray, y_train: np.ndarray) -> VotingClassifier:
        """
        Construir voting ensemble de múltiples modelos

        Args:
            X_train: Features de entrenamiento
            y_train: Target

        Returns:
            VotingClassifier entrenado
        """
        try:
            # Modelos base
            xgb = XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42
            )

            lgb_model = lgb.LGBMClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42
            )

            rf = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )

            gb = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42
            )

            # Voting ensemble (weighted voting)
            ensemble = VotingClassifier(
                estimators=[
                    ('xgb', xgb),
                    ('lgb', lgb_model),
                    ('rf', rf),
                    ('gb', gb)
                ],
                voting='soft',
                weights=[3, 3, 1, 2]  # XGBoost y LightGBM más peso
            )

            ensemble.fit(X_train, y_train)
            logger.info("Voting ensemble built and trained")
            return ensemble

        except Exception as e:
            logger.error(f"Error building ensemble: {e}")
            return None

    @staticmethod
    def build_stacking_ensemble(X_train: np.ndarray, y_train: np.ndarray) -> Dict:
        """
        Construir stacking ensemble (más avanzado)

        Args:
            X_train: Features
            y_train: Target

        Returns:
            Diccionario con modelos layer 1 y meta-model
        """
        try:
            # Layer 1: Base learners
            base_models = {
                'xgb': XGBClassifier(n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42),
                'rf': RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42),
                'gb': GradientBoostingClassifier(n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42)
            }

            # Train base models
            meta_features = []
            for name, model in base_models.items():
                model.fit(X_train, y_train)
                meta_features.append(model.predict_proba(X_train))
                logger.info(f"Trained {name}")

            # Layer 2: Meta-model
            X_meta = np.hstack(meta_features)
            meta_model = XGBClassifier(n_estimators=50, max_depth=3, random_state=42)
            meta_model.fit(X_meta, y_train)

            logger.info("Stacking ensemble built successfully")
            return {
                'base_models': base_models,
                'meta_model': meta_model,
                'type': 'stacking'
            }

        except Exception as e:
            logger.error(f"Error building stacking ensemble: {e}")
            return None


class HyperparameterOptimizer:
    """Optimización de hiperparámetros"""

    @staticmethod
    def get_optimized_params() -> Dict:
        """
        Obtener parámetros optimizados basados en análisis

        Returns:
            Diccionario con parámetros recomendados
        """
        return {
            'xgboost': {
                'n_estimators': 200,
                'max_depth': 7,
                'learning_rate': 0.05,
                'subsample': 0.85,
                'colsample_bytree': 0.85,
                'gamma': 1,
                'reg_alpha': 0.5,
                'reg_lambda': 1.0,
                'min_child_weight': 1
            },
            'lightgbm': {
                'n_estimators': 150,
                'max_depth': 8,
                'learning_rate': 0.05,
                'num_leaves': 31,
                'subsample': 0.9,
                'colsample_bytree': 0.9,
                'lambda_l1': 0.5,
                'lambda_l2': 1.0
            },
            'random_forest': {
                'n_estimators': 200,
                'max_depth': 12,
                'min_samples_split': 5,
                'min_samples_leaf': 2,
                'max_features': 'sqrt'
            }
        }


class ModelExplainability:
    """Explainability y interpretability"""

    @staticmethod
    def get_feature_importance(model, feature_names: List[str]) -> Dict:
        """
        Obtener importancia de features

        Args:
            model: Modelo entrenado
            feature_names: Nombres de features

        Returns:
            Diccionario con importancia
        """
        try:
            if hasattr(model, 'feature_importances_'):
                importances = model.feature_importances_
            elif hasattr(model, 'feature_importances'):
                importances = model.feature_importances
            else:
                return {}

            importance_dict = dict(zip(feature_names, importances))
            sorted_importance = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)

            return {
                'top_features': sorted_importance[:10],
                'all_features': importance_dict
            }

        except Exception as e:
            logger.error(f"Error getting feature importance: {e}")
            return {}

    @staticmethod
    def get_shap_summary(model, X: np.ndarray) -> Dict:
        """
        Obtener SHAP summary (cuando disponible)

        Args:
            model: Modelo entrenado
            X: Datos de features

        Returns:
            Diccionario con resumen SHAP
        """
        try:
            import shap

            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X)

            return {
                'shap_available': True,
                'mean_abs_shap': np.abs(shap_values).mean(axis=0).tolist()
            }

        except ImportError:
            logger.warning("SHAP not installed, skipping SHAP analysis")
            return {'shap_available': False}
        except Exception as e:
            logger.error(f"Error getting SHAP values: {e}")
            return {'shap_available': False}


class ModelPerformanceOptimizer:
    """Optimización de performance en producción"""

    @staticmethod
    def get_optimization_recommendations(metrics: Dict) -> List[str]:
        """
        Obtener recomendaciones de optimización

        Args:
            metrics: Diccionario con métricas del modelo

        Returns:
            Lista de recomendaciones
        """
        recommendations = []

        accuracy = metrics.get('accuracy', 0)
        precision = metrics.get('precision', 0)
        recall = metrics.get('recall', 0)

        # Análisis de accuracy
        if accuracy < 0.85:
            recommendations.append("Low accuracy - consider ensemble methods or feature engineering")
        elif accuracy < 0.90:
            recommendations.append("Moderate accuracy - explore hyperparameter optimization")

        # Análisis de balance precision-recall
        if precision < 0.80:
            recommendations.append("Low precision - may cause false positives, consider adjusting threshold")
        if recall < 0.85:
            recommendations.append("Low recall - may miss positive cases, review feature importance")

        if precision > 0.95 and recall < 0.85:
            recommendations.append("High precision but low recall - consider lowering decision threshold")

        if precision < 0.85 and recall > 0.95:
            recommendations.append("High recall but low precision - consider raising decision threshold")

        return recommendations if recommendations else ["Model performance is good"]


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("\n=== MODEL OPTIMIZER TEST ===\n")

    # Test feature engineering
    print("Testing feature engineering...")
    sample_df = pd.DataFrame({
        'severity_level': [3, 4, 2],
        'distance_km': [2.5, 5.0, 1.5],
        'hour_of_day': [10, 20, 14],
        'day_of_week': [2, 5, 0]
    })

    engineer = FeatureEngineer()
    df_enhanced = engineer.create_interaction_features(sample_df)
    print(f"Enhanced features: {df_enhanced.shape[1]} total features")

    # Test optimization recommendations
    print("\nTesting optimization recommendations...")
    metrics = {'accuracy': 0.82, 'precision': 0.75, 'recall': 0.92}
    optimizer = ModelPerformanceOptimizer()
    recommendations = optimizer.get_optimization_recommendations(metrics)
    for rec in recommendations:
        print(f"  - {rec}")

    print("\n=== TEST COMPLETE ===\n")
