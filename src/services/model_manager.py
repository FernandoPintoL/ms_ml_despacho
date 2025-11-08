"""
Model Manager Service
Manages ML model lifecycle, loading, and version control
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import pickle

from ..config.logger import LoggerMixin
from ..models import BaseModel, ETAModel, SeverityClassifier, AmbulanceSelector, RouteOptimizer
from ..repositories import ModelRepository


class ModelManager(LoggerMixin):
    """
    Service for managing ML model lifecycle

    Provides:
    - Model loading and caching
    - Version management
    - Active model tracking
    - Model validation
    - Performance monitoring
    """

    def __init__(self, model_repository: ModelRepository):
        """
        Initialize Model Manager

        Args:
            model_repository: ModelRepository instance
        """
        self.repo = model_repository
        self.active_models: Dict[str, Any] = {}
        self.model_classes = {
            'eta': ETAModel,
            'severity': SeverityClassifier,
            'ambulance': AmbulanceSelector,
            'route': RouteOptimizer
        }
        self.log_info("Initialized ModelManager")

    # ============================================
    # MODEL LOADING & INITIALIZATION
    # ============================================

    def load_active_models(self) -> Dict[str, bool]:
        """
        Load all active models from repository

        Returns:
            Dictionary with load status for each model
        """
        try:
            status = {}
            active_models = self.repo.get_all_active_models()

            for model_info in active_models:
                model_name = model_info['model_name']
                success = self._load_single_model(model_name, model_info)
                status[model_name] = success

            loaded_count = sum(1 for v in status.values() if v)
            self.log_info(f"Loaded {loaded_count}/{len(status)} active models")

            return status

        except Exception as e:
            self.log_error(f"Error loading active models: {str(e)}")
            return {}

    def _load_single_model(self, model_name: str, model_info: Dict) -> bool:
        """
        Load a single model

        Args:
            model_name: Model name
            model_info: Model metadata

        Returns:
            True if successful
        """
        try:
            # Get model file
            model_bytes = self.repo.get_model_file(model_name, model_info['version'])

            if not model_bytes:
                self.log_error(f"Could not retrieve model file for {model_name}")
                return False

            # Deserialize model
            try:
                loaded_model = pickle.loads(model_bytes)
                self.active_models[model_name] = {
                    'model': loaded_model,
                    'metadata': model_info,
                    'loaded_at': datetime.utcnow().isoformat(),
                    'prediction_count': 0
                }
                self.log_info(f"Loaded model: {model_name} v{model_info['version']}")
                return True

            except Exception as e:
                self.log_error(f"Could not deserialize {model_name}: {str(e)}")
                return False

        except Exception as e:
            self.log_error(f"Error loading model {model_name}: {str(e)}")
            return False

    def get_model(self, model_name: str) -> Optional[BaseModel]:
        """
        Get loaded model by name

        Args:
            model_name: Model name

        Returns:
            Model instance or None
        """
        if model_name not in self.active_models:
            # Try to load it
            model_info = self.repo.get_active_model(model_name)
            if model_info:
                self._load_single_model(model_name, model_info)

        if model_name in self.active_models:
            return self.active_models[model_name]['model']

        return None

    # ============================================
    # MODEL PREDICTION TRACKING
    # ============================================

    def record_prediction(
        self,
        model_name: str,
        prediction_time_ms: float,
        input_features: int,
        output_value: float,
        confidence: float,
        actual_value: Optional[float] = None
    ) -> bool:
        """
        Record prediction for monitoring

        Args:
            model_name: Model name
            prediction_time_ms: Prediction latency
            input_features: Number of features
            output_value: Prediction output
            confidence: Confidence score
            actual_value: Actual value (for validation)

        Returns:
            True if recorded
        """
        try:
            if model_name not in self.active_models:
                return False

            model_info = self.active_models[model_name]
            model_id = model_info['metadata'].get('id')

            # Increment prediction count
            model_info['prediction_count'] += 1

            # Record in repository
            success = self.repo.record_prediction_performance(
                model_id,
                {
                    'prediction_time_ms': prediction_time_ms,
                    'input_features': input_features,
                    'output_value': output_value,
                    'confidence': confidence,
                    'actual_value': actual_value
                }
            )

            if success:
                self.log_debug(f"Recorded prediction for {model_name}")

            return success

        except Exception as e:
            self.log_warning(f"Error recording prediction: {str(e)}")
            return False

    # ============================================
    # MODEL VERSIONING
    # ============================================

    def get_model_versions(self, model_name: str, limit: int = 10) -> List[Dict]:
        """
        Get all versions of a model

        Args:
            model_name: Model name
            limit: Maximum versions to return

        Returns:
            List of model version info
        """
        try:
            return self.repo.get_model_versions(model_name, limit)

        except Exception as e:
            self.log_error(f"Error getting model versions: {str(e)}")
            return []

    def activate_model_version(self, model_name: str, version: str) -> bool:
        """
        Activate specific model version

        Args:
            model_name: Model name
            version: Version to activate

        Returns:
            True if successful
        """
        try:
            # Get model version info
            model_info = self.repo.get_model_version(model_name, version)

            if not model_info:
                self.log_error(f"Model version not found: {model_name} v{version}")
                return False

            # Activate in repository
            success = self.repo.activate_model(model_info['id'])

            if success:
                # Reload the model
                self._load_single_model(model_name, model_info)
                self.log_info(f"Activated {model_name} v{version}")

            return success

        except Exception as e:
            self.log_error(f"Error activating model version: {str(e)}")
            return False

    def compare_models(self, model_name: str) -> Dict[str, Any]:
        """
        Compare all versions of a model

        Args:
            model_name: Model name

        Returns:
            Comparison data
        """
        try:
            return self.repo.compare_models(model_name)

        except Exception as e:
            self.log_error(f"Error comparing models: {str(e)}")
            return {}

    # ============================================
    # MODEL VALIDATION & TESTING
    # ============================================

    def validate_model(
        self,
        model_name: str,
        test_features: List[Dict],
        test_labels: List[Any]
    ) -> Dict[str, float]:
        """
        Validate model with test data

        Args:
            model_name: Model name
            test_features: List of feature dictionaries
            test_labels: List of expected labels/values

        Returns:
            Validation metrics
        """
        try:
            model = self.get_model(model_name)

            if not model:
                self.log_error(f"Model not found: {model_name}")
                return {}

            # Run predictions
            predictions = []
            for features in test_features:
                try:
                    result = model.predict(features)
                    if isinstance(result, dict) and 'level' in result:
                        predictions.append(result['level'])
                    elif isinstance(result, dict) and 'estimated_minutes' in result:
                        predictions.append(result['estimated_minutes'])
                    else:
                        predictions.append(result)
                except Exception as e:
                    self.log_warning(f"Prediction error in validation: {str(e)}")
                    continue

            # Calculate metrics
            if len(predictions) != len(test_labels):
                self.log_warning(f"Prediction count mismatch: {len(predictions)} vs {len(test_labels)}")

            metrics = self._calculate_validation_metrics(predictions, test_labels)

            # Store validation metrics
            if model_name in self.active_models:
                model_id = self.active_models[model_name]['metadata'].get('id')
                self.repo.validate_model(model_id, metrics)

            self.log_info(f"Validation metrics for {model_name}: {metrics}")
            return metrics

        except Exception as e:
            self.log_error(f"Error validating model: {str(e)}")
            return {}

    def _calculate_validation_metrics(
        self,
        predictions: List[Any],
        actual: List[Any]
    ) -> Dict[str, float]:
        """
        Calculate validation metrics

        Args:
            predictions: Model predictions
            actual: Actual values

        Returns:
            Dictionary with metrics
        """
        try:
            import numpy as np

            predictions = np.array(predictions)
            actual = np.array(actual)

            # Handle classification vs regression
            if all(isinstance(x, int) and 1 <= x <= 5 for x in predictions):
                # Classification (severity levels)
                accuracy = np.mean(predictions == actual)
                return {
                    'accuracy': float(accuracy),
                    'sample_count': len(predictions)
                }
            else:
                # Regression (ETA times)
                mae = np.mean(np.abs(predictions - actual))
                rmse = np.sqrt(np.mean((predictions - actual) ** 2))
                r2 = 1 - (np.sum((actual - predictions) ** 2) / np.sum((actual - np.mean(actual)) ** 2))

                return {
                    'mae': float(mae),
                    'rmse': float(rmse),
                    'r2': float(r2),
                    'sample_count': len(predictions)
                }

        except Exception as e:
            self.log_error(f"Error calculating metrics: {str(e)}")
            return {}

    # ============================================
    # MODEL PERFORMANCE MONITORING
    # ============================================

    def get_model_performance(self, model_name: str, hours: int = 1) -> Dict[str, Any]:
        """
        Get model performance statistics

        Args:
            model_name: Model name
            hours: Look back how many hours

        Returns:
            Performance statistics
        """
        try:
            if model_name not in self.active_models:
                return {}

            model_info = self.active_models[model_name]
            model_id = model_info['metadata'].get('id')

            stats = self.repo.get_model_performance_stats(model_id, hours)

            # Add local metrics
            stats['local_prediction_count'] = model_info['prediction_count']
            stats['loaded_at'] = model_info['loaded_at']

            return stats

        except Exception as e:
            self.log_error(f"Error getting model performance: {str(e)}")
            return {}

    def get_all_models_status(self) -> Dict[str, Dict]:
        """
        Get status of all active models

        Returns:
            Dictionary with status for each model
        """
        try:
            status = {}

            for model_name, model_data in self.active_models.items():
                status[model_name] = {
                    'is_loaded': True,
                    'version': model_data['metadata'].get('version'),
                    'loaded_at': model_data['loaded_at'],
                    'prediction_count': model_data['prediction_count'],
                    'model_type': model_data['metadata'].get('model_type'),
                    'training_samples': model_data['metadata'].get('training_samples')
                }

            return status

        except Exception as e:
            self.log_error(f"Error getting models status: {str(e)}")
            return {}

    # ============================================
    # UTILITY METHODS
    # ============================================

    def reload_model(self, model_name: str) -> bool:
        """
        Force reload a model

        Args:
            model_name: Model name

        Returns:
            True if successful
        """
        try:
            model_info = self.repo.get_active_model(model_name)

            if not model_info:
                self.log_error(f"Active model not found: {model_name}")
                return False

            return self._load_single_model(model_name, model_info)

        except Exception as e:
            self.log_error(f"Error reloading model: {str(e)}")
            return False

    def get_model_metadata(self, model_name: str) -> Optional[Dict]:
        """
        Get model metadata

        Args:
            model_name: Model name

        Returns:
            Model metadata or None
        """
        try:
            if model_name not in self.active_models:
                return None

            return self.active_models[model_name]['metadata']

        except Exception as e:
            self.log_error(f"Error getting model metadata: {str(e)}")
            return None

    def health_check(self) -> Dict[str, Any]:
        """
        Check health of all models

        Returns:
            Health status dictionary
        """
        try:
            status = {
                'healthy': True,
                'models': {}
            }

            for model_name in self.model_classes.keys():
                if model_name in self.active_models:
                    status['models'][model_name] = {
                        'status': 'loaded',
                        'version': self.active_models[model_name]['metadata'].get('version')
                    }
                else:
                    status['models'][model_name] = {
                        'status': 'not_loaded'
                    }
                    status['healthy'] = False

            self.log_debug(f"Health check: {status}")
            return status

        except Exception as e:
            self.log_error(f"Error in health check: {str(e)}")
            return {'healthy': False, 'error': str(e)}
