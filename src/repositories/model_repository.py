"""
Model Repository
Manages ML model persistence, versioning, and metadata
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import os

from .base_repository import BaseRepository


class ModelRepository(BaseRepository):
    """
    Repository for managing ML models

    Provides:
    - Model persistence and versioning
    - Model metadata management
    - Performance tracking
    - Model deployment management
    """

    def __init__(self, db_connection=None, redis_client=None, models_path: str = "/models"):
        """
        Initialize Model Repository

        Args:
            db_connection: Database connection object
            redis_client: Redis client instance
            models_path: Path to store model files
        """
        super().__init__(db_connection, redis_client)
        self.table_name = 'ml_models'
        self.models_path = models_path

        # Ensure models directory exists
        os.makedirs(models_path, exist_ok=True)

    # ============================================
    # MODEL PERSISTENCE
    # ============================================

    def save_model_version(self, model_info: Dict[str, Any], model_bytes: bytes) -> Optional[int]:
        """
        Save a new model version

        Args:
            model_info: Dictionary with:
                - model_name: str (eta, severity, ambulance, route)
                - version: str (semantic version)
                - model_type: str
                - training_date: datetime
                - training_samples: int
                - metrics: Dict with performance metrics
                - feature_names: List[str]
                - hyperparameters: Dict
                - description: str (optional)

            model_bytes: Serialized model binary data

        Returns:
            Model version ID if successful, None otherwise
        """
        try:
            model_info['created_at'] = datetime.utcnow().isoformat()
            model_info['updated_at'] = datetime.utcnow().isoformat()
            model_info['is_active'] = False  # Only activate after validation

            # Save model file
            model_filename = self._generate_model_filename(
                model_info['model_name'],
                model_info['version']
            )
            model_filepath = os.path.join(self.models_path, model_filename)

            with open(model_filepath, 'wb') as f:
                f.write(model_bytes)

            # Store metadata in database
            model_info['model_path'] = model_filename
            model_info['file_size'] = len(model_bytes)

            columns = ', '.join(model_info.keys())
            placeholders = ', '.join(['%s'] * len(model_info))
            query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"

            affected = self.execute_update(query, tuple(model_info.values()))

            if affected > 0:
                self.log_info(f"Model {model_info['model_name']} v{model_info['version']} saved")
                self.clear_cache_pattern(f"model:{model_info['model_name']}:*")
                return model_info.get('id')

            return None

        except Exception as e:
            self.log_error(f"Error saving model version: {str(e)}")
            return None

    def get_model_version(self, model_name: str, version: str) -> Optional[Dict]:
        """
        Get specific model version metadata

        Args:
            model_name: Model name (eta, severity, ambulance, route)
            version: Version string

        Returns:
            Model metadata dictionary or None
        """
        try:
            cache_key = f"model:{model_name}:{version}"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            query = f"""
                SELECT * FROM {self.table_name}
                WHERE model_name = %s AND version = %s
            """

            results = self.execute_query(query, (model_name, version))

            if results:
                model = results[0]
                self.set_cache(cache_key, model)
                return model

            return None

        except Exception as e:
            self.log_error(f"Error getting model version: {str(e)}")
            return None

    def get_active_model(self, model_name: str) -> Optional[Dict]:
        """
        Get currently active/deployed model

        Args:
            model_name: Model name

        Returns:
            Active model metadata or None
        """
        try:
            cache_key = f"model:active:{model_name}"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            query = f"""
                SELECT * FROM {self.table_name}
                WHERE model_name = %s AND is_active = TRUE
                ORDER BY created_at DESC
                LIMIT 1
            """

            results = self.execute_query(query, (model_name,))

            if results:
                model = results[0]
                self.set_cache(cache_key, model, ttl=3600)
                return model

            return None

        except Exception as e:
            self.log_error(f"Error getting active model: {str(e)}")
            return None

    def get_model_versions(self, model_name: str, limit: int = 10) -> List[Dict]:
        """
        Get all versions of a model

        Args:
            model_name: Model name
            limit: Maximum results

        Returns:
            List of model versions
        """
        try:
            cache_key = f"model:versions:{model_name}"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            query = f"""
                SELECT * FROM {self.table_name}
                WHERE model_name = %s
                ORDER BY created_at DESC
                LIMIT %s
            """

            results = self.execute_query(query, (model_name, limit))

            if results:
                self.set_cache(cache_key, results, ttl=1800)

            return results or []

        except Exception as e:
            self.log_error(f"Error getting model versions: {str(e)}")
            return []

    # ============================================
    # MODEL DEPLOYMENT
    # ============================================

    def activate_model(self, model_id: int) -> bool:
        """
        Activate a model version for production

        Args:
            model_id: Model ID

        Returns:
            True if successful
        """
        try:
            # Get model info first
            query = f"SELECT * FROM {self.table_name} WHERE id = %s"
            results = self.execute_query(query, (model_id,))

            if not results:
                return False

            model = results[0]
            model_name = model['model_name']

            # Deactivate all previous versions
            deactivate_query = f"""
                UPDATE {self.table_name}
                SET is_active = FALSE, updated_at = %s
                WHERE model_name = %s
            """
            self.execute_update(deactivate_query, (datetime.utcnow().isoformat(), model_name))

            # Activate new version
            activate_query = f"""
                UPDATE {self.table_name}
                SET is_active = TRUE, activated_at = %s, updated_at = %s
                WHERE id = %s
            """

            now = datetime.utcnow().isoformat()
            affected = self.execute_update(activate_query, (now, now, model_id))

            if affected > 0:
                # Clear cache
                self.delete_cache(f"model:active:{model_name}")
                self.clear_cache_pattern(f"model:{model_name}:*")

                self.log_info(f"Model {model_name} v{model['version']} activated")
                return True

            return False

        except Exception as e:
            self.log_error(f"Error activating model: {str(e)}")
            return False

    def deactivate_model(self, model_id: int) -> bool:
        """
        Deactivate a model version

        Args:
            model_id: Model ID

        Returns:
            True if successful
        """
        try:
            query = f"""
                UPDATE {self.table_name}
                SET is_active = FALSE, updated_at = %s
                WHERE id = %s
            """

            affected = self.execute_update(query, (datetime.utcnow().isoformat(), model_id))

            if affected > 0:
                # Clear relevant caches
                results = self.execute_query(f"SELECT model_name FROM {self.table_name} WHERE id = %s", (model_id,))
                if results:
                    model_name = results[0]['model_name']
                    self.delete_cache(f"model:active:{model_name}")
                    self.clear_cache_pattern(f"model:{model_name}:*")

                self.log_info(f"Model {model_id} deactivated")
                return True

            return False

        except Exception as e:
            self.log_error(f"Error deactivating model: {str(e)}")
            return False

    # ============================================
    # MODEL PERFORMANCE TRACKING
    # ============================================

    def record_prediction_performance(self, model_id: int, performance_data: Dict[str, Any]) -> bool:
        """
        Record prediction performance metrics

        Args:
            model_id: Model ID
            performance_data: Dictionary with:
                - prediction_time_ms: float
                - input_features: int
                - output_value: float
                - confidence: float
                - actual_value: float (optional, for post-validation)

        Returns:
            True if successful
        """
        try:
            perf_data = {
                'model_id': model_id,
                'prediction_time_ms': performance_data.get('prediction_time_ms'),
                'input_features': performance_data.get('input_features'),
                'output_value': performance_data.get('output_value'),
                'confidence': performance_data.get('confidence'),
                'actual_value': performance_data.get('actual_value'),
                'created_at': datetime.utcnow().isoformat()
            }

            columns = ', '.join(perf_data.keys())
            placeholders = ', '.join(['%s'] * len(perf_data))
            query = f"INSERT INTO model_predictions ({columns}) VALUES ({placeholders})"

            affected = self.execute_update(query, tuple(perf_data.values()))

            return affected > 0

        except Exception as e:
            self.log_error(f"Error recording prediction performance: {str(e)}")
            return False

    def get_model_performance_stats(self, model_id: int, hours: int = 24) -> Dict[str, Any]:
        """
        Get performance statistics for model

        Args:
            model_id: Model ID
            hours: Look back how many hours

        Returns:
            Dictionary with performance metrics
        """
        try:
            cache_key = f"model_perf:{model_id}:{hours}h"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

            query = """
                SELECT
                    COUNT(*) as total_predictions,
                    AVG(prediction_time_ms) as avg_prediction_time,
                    MIN(prediction_time_ms) as min_prediction_time,
                    MAX(prediction_time_ms) as max_prediction_time,
                    AVG(confidence) as avg_confidence,
                    STDDEV(confidence) as stddev_confidence,
                    AVG(ABS(actual_value - output_value)) as mae,
                    MAX(prediction_time_ms) as p99_latency
                FROM model_predictions
                WHERE model_id = %s AND created_at >= %s
            """

            results = self.execute_query(query, (model_id, cutoff_time))

            if results:
                stats = results[0]
                self.set_cache(cache_key, stats, ttl=600)
                return stats

            return {}

        except Exception as e:
            self.log_error(f"Error getting model performance stats: {str(e)}")
            return {}

    # ============================================
    # MODEL COMPARISON & VALIDATION
    # ============================================

    def compare_models(self, model_name: str) -> Dict[str, Any]:
        """
        Compare all versions of a model

        Args:
            model_name: Model name

        Returns:
            Comparison dictionary with metrics
        """
        try:
            cache_key = f"model_comparison:{model_name}"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            query = f"""
                SELECT
                    id, version, created_at, is_active,
                    training_samples, metrics
                FROM {self.table_name}
                WHERE model_name = %s
                ORDER BY created_at DESC
                LIMIT 5
            """

            results = self.execute_query(query, (model_name,))

            comparison = {
                'model_name': model_name,
                'versions': results or []
            }

            if comparison['versions']:
                self.set_cache(cache_key, comparison, ttl=3600)

            return comparison

        except Exception as e:
            self.log_error(f"Error comparing models: {str(e)}")
            return {}

    def validate_model(self, model_id: int, validation_metrics: Dict[str, float]) -> bool:
        """
        Validate model and update validation metrics

        Args:
            model_id: Model ID
            validation_metrics: Dictionary with validation scores

        Returns:
            True if successful
        """
        try:
            update_data = {
                'validation_metrics': json.dumps(validation_metrics),
                'validated_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }

            updates = ', '.join([f"{k} = %s" for k in update_data.keys()])
            query = f"UPDATE {self.table_name} SET {updates} WHERE id = %s"

            values = list(update_data.values()) + [model_id]
            affected = self.execute_update(query, tuple(values))

            if affected > 0:
                # Clear cache
                results = self.execute_query(f"SELECT model_name, version FROM {self.table_name} WHERE id = %s", (model_id,))
                if results:
                    model = results[0]
                    self.clear_cache_pattern(f"model:{model['model_name']}:*")

                self.log_info(f"Model {model_id} validated with metrics: {validation_metrics}")
                return True

            return False

        except Exception as e:
            self.log_error(f"Error validating model: {str(e)}")
            return False

    # ============================================
    # MODEL FILE OPERATIONS
    # ============================================

    def get_model_file(self, model_name: str, version: str) -> Optional[bytes]:
        """
        Get model file bytes

        Args:
            model_name: Model name
            version: Model version

        Returns:
            Model bytes or None
        """
        try:
            # Get metadata first
            model = self.get_model_version(model_name, version)
            if not model:
                return None

            model_filepath = os.path.join(self.models_path, model['model_path'])

            if not os.path.exists(model_filepath):
                self.log_warning(f"Model file not found: {model_filepath}")
                return None

            with open(model_filepath, 'rb') as f:
                return f.read()

        except Exception as e:
            self.log_error(f"Error reading model file: {str(e)}")
            return None

    def delete_model_version(self, model_id: int) -> bool:
        """
        Delete a model version (archive it)

        Args:
            model_id: Model ID

        Returns:
            True if successful
        """
        try:
            # Get model info
            results = self.execute_query(f"SELECT * FROM {self.table_name} WHERE id = %s", (model_id,))

            if not results:
                return False

            model = results[0]

            # Delete file
            model_filepath = os.path.join(self.models_path, model['model_path'])
            if os.path.exists(model_filepath):
                os.remove(model_filepath)
                self.log_info(f"Model file deleted: {model_filepath}")

            # Archive in database (soft delete)
            query = f"""
                UPDATE {self.table_name}
                SET is_active = FALSE, deleted_at = %s
                WHERE id = %s
            """

            affected = self.execute_update(query, (datetime.utcnow().isoformat(), model_id))

            if affected > 0:
                self.clear_cache_pattern(f"model:{model['model_name']}:*")
                return True

            return False

        except Exception as e:
            self.log_error(f"Error deleting model version: {str(e)}")
            return False

    # ============================================
    # HELPER METHODS
    # ============================================

    def _generate_model_filename(self, model_name: str, version: str) -> str:
        """
        Generate model filename from name and version

        Args:
            model_name: Model name
            version: Version string

        Returns:
            Filename string
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"{model_name}_v{version}_{timestamp}.pkl"

    def get_all_active_models(self) -> List[Dict]:
        """
        Get all currently active models

        Returns:
            List of active models
        """
        try:
            cache_key = "models:all_active"
            cached = self.get_cache(cache_key)
            if cached:
                return cached

            query = f"""
                SELECT * FROM {self.table_name}
                WHERE is_active = TRUE
                ORDER BY model_name, created_at DESC
            """

            results = self.execute_query(query)

            if results:
                self.set_cache(cache_key, results, ttl=3600)

            return results or []

        except Exception as e:
            self.log_error(f"Error getting all active models: {str(e)}")
            return []
