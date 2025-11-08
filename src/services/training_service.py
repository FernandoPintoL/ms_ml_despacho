"""
Training Service
Manages ML model training and retraining workflows
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import numpy as np
import pickle

from ..config.logger import LoggerMixin
from ..repositories import (
    DispatchRepository, ModelRepository, FeatureEngineer, CacheRepository
)
from .model_manager import ModelManager


class TrainingService(LoggerMixin):
    """
    Service for model training and retraining

    Provides:
    - Data preparation from historical dispatches
    - Model training orchestration
    - Performance evaluation
    - Model versioning
    - Retraining workflows
    """

    def __init__(
        self,
        model_manager: ModelManager,
        dispatch_repo: DispatchRepository,
        model_repo: ModelRepository,
        cache_repo: CacheRepository
    ):
        """
        Initialize Training Service

        Args:
            model_manager: ModelManager instance
            dispatch_repo: DispatchRepository instance
            model_repo: ModelRepository instance
            cache_repo: CacheRepository instance
        """
        self.model_manager = model_manager
        self.dispatch_repo = dispatch_repo
        self.model_repo = model_repo
        self.cache_repo = cache_repo
        self.engineer = FeatureEngineer()
        self.log_info("Initialized TrainingService")

    # ============================================
    # DATA PREPARATION
    # ============================================

    def prepare_training_data(
        self,
        model_name: str,
        days: int = 30,
        min_samples: int = 100
    ) -> Tuple[List[Dict], List[Any]]:
        """
        Prepare training data from historical dispatches

        Args:
            model_name: Model to train
            days: Days of history to use
            min_samples: Minimum samples required

        Returns:
            Tuple of (features_list, labels_list)
        """
        try:
            self.log_info(f"Preparing training data for {model_name}")

            # Get historical dispatches
            dispatches = self.dispatch_repo.get_recent_dispatches(limit=10000, hours=days*24)

            if len(dispatches) < min_samples:
                self.log_error(f"Insufficient data: {len(dispatches)} < {min_samples}")
                return [], []

            features_list = []
            labels_list = []

            for dispatch in dispatches:
                try:
                    # Extract features based on model type
                    if model_name == 'severity':
                        features = self._extract_severity_features(dispatch)
                        label = dispatch.get('severity_level', 3)

                    elif model_name == 'eta':
                        features = self._extract_eta_features(dispatch)
                        # Calculate actual response time in minutes
                        label = self._calculate_response_time(dispatch)
                        if label is None:
                            continue

                    elif model_name == 'ambulance':
                        features = self._extract_ambulance_features(dispatch)
                        label = dispatch.get('assigned_ambulance_id')
                        if label is None:
                            continue

                    elif model_name == 'route':
                        features = self._extract_route_features(dispatch)
                        # Use ETA from route info
                        route_info = dispatch.get('route_info', {})
                        label = route_info.get('eta_minutes', 15)

                    else:
                        continue

                    # Validate features
                    is_valid, errors = self.engineer.validate_features(
                        features,
                        required_fields=list(features.keys())
                    )

                    if is_valid:
                        features_list.append(features)
                        labels_list.append(label)

                except Exception as e:
                    self.log_debug(f"Error extracting features: {str(e)}")
                    continue

            self.log_info(f"Prepared {len(features_list)} training samples for {model_name}")
            return features_list, labels_list

        except Exception as e:
            self.log_error(f"Error preparing training data: {str(e)}")
            return [], []

    def _extract_severity_features(self, dispatch: Dict) -> Dict:
        """Extract features for severity training"""
        return self.engineer.extract_severity_indicators(
            dispatch.get('description', ''),
            vital_signs=dispatch.get('vital_signs'),
            age=dispatch.get('patient_age')
        )

    def _extract_eta_features(self, dispatch: Dict) -> Dict:
        """Extract features for ETA training"""
        features = self.engineer.extract_geographic_features(
            dispatch.get('patient_lat', 0),
            dispatch.get('patient_lon', 0),
            dispatch.get('destination_lat', 0),
            dispatch.get('destination_lon', 0)
        )

        timestamp = dispatch.get('timestamp', datetime.utcnow())
        temporal = self.engineer.extract_datetime_features(timestamp)
        features.update(temporal)

        traffic = self.engineer.encode_traffic_level(dispatch.get('traffic_level', 1))
        features.update(traffic)

        return features

    def _extract_ambulance_features(self, dispatch: Dict) -> Dict:
        """Extract features for ambulance selection training"""
        ambulance = dispatch.get('assigned_ambulance', {})
        return self.engineer.extract_ambulance_features(ambulance)

    def _extract_route_features(self, dispatch: Dict) -> Dict:
        """Extract features for route optimization training"""
        features = self.engineer.extract_geographic_features(
            dispatch.get('patient_lat', 0),
            dispatch.get('patient_lon', 0),
            dispatch.get('destination_lat', 0),
            dispatch.get('destination_lon', 0)
        )

        timestamp = dispatch.get('timestamp', datetime.utcnow())
        temporal = self.engineer.extract_datetime_features(timestamp)
        features.update(temporal)

        return features

    def _calculate_response_time(self, dispatch: Dict) -> Optional[float]:
        """Calculate actual response time from dispatch"""
        try:
            created_at = dispatch.get('created_at')
            completed_at = dispatch.get('updated_at')

            if created_at and completed_at:
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at)
                if isinstance(completed_at, str):
                    completed_at = datetime.fromisoformat(completed_at)

                delta = (completed_at - created_at).total_seconds() / 60  # minutes
                return max(0, delta)  # Ensure non-negative

            return None

        except Exception:
            return None

    # ============================================
    # MODEL TRAINING
    # ============================================

    def train_model(
        self,
        model_name: str,
        days: int = 30,
        test_split: float = 0.2,
        hyperparameters: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Train a model

        Args:
            model_name: Model to train
            days: Days of history to use
            test_split: Train/test split ratio
            hyperparameters: Optional hyperparameters to use

        Returns:
            Training results with metrics
        """
        try:
            self.log_info(f"Starting training for {model_name}")

            # Prepare data
            features_list, labels = self.prepare_training_data(model_name, days)

            if not features_list:
                self.log_error(f"No training data available for {model_name}")
                return {'success': False, 'error': 'No training data'}

            # Convert to numpy arrays
            X_train = np.array([list(f.values()) for f in features_list])
            y_train = np.array(labels)

            # Split data
            split_idx = int(len(X_train) * (1 - test_split))
            X_test = X_train[split_idx:]
            y_test = y_train[split_idx:]
            X_train = X_train[:split_idx]
            y_train = y_train[:split_idx]

            # Get model
            model = self.model_manager.get_model(model_name)
            if not model:
                self.log_error(f"Model not found: {model_name}")
                return {'success': False, 'error': 'Model not found'}

            # Train
            kwargs = hyperparameters or {}
            train_metrics = model.train(X_train, y_train, X_test, y_test, **kwargs)

            # Evaluate
            eval_metrics = model.evaluate(X_test, y_test)

            result = {
                'success': True,
                'model_name': model_name,
                'training_samples': len(X_train),
                'test_samples': len(X_test),
                'train_metrics': train_metrics,
                'eval_metrics': eval_metrics,
                'trained_at': datetime.utcnow().isoformat()
            }

            self.log_info(f"Training complete for {model_name}: {eval_metrics}")
            return result

        except Exception as e:
            self.log_error(f"Error training model: {str(e)}")
            return {'success': False, 'error': str(e)}

    # ============================================
    # MODEL VERSIONING & PERSISTENCE
    # ============================================

    def save_trained_model(
        self,
        model_name: str,
        version: str,
        metrics: Dict[str, Any],
        hyperparameters: Optional[Dict] = None,
        description: Optional[str] = None
    ) -> Optional[int]:
        """
        Save trained model to repository

        Args:
            model_name: Model name
            version: Version string
            metrics: Training/evaluation metrics
            hyperparameters: Hyperparameters used
            description: Model description

        Returns:
            Model ID if successful, None otherwise
        """
        try:
            model = self.model_manager.get_model(model_name)
            if not model:
                self.log_error(f"Model not found: {model_name}")
                return None

            # Serialize model
            model_bytes = pickle.dumps(model)

            # Get feature names
            feature_names = getattr(model, 'feature_names', [])

            # Prepare model info
            model_info = {
                'model_name': model_name,
                'version': version,
                'model_type': getattr(model, 'model_type', 'unknown'),
                'training_date': datetime.utcnow(),
                'training_samples': metrics.get('samples', 0),
                'metrics': metrics,
                'feature_names': feature_names,
                'hyperparameters': hyperparameters or {},
                'description': description or f'{model_name} v{version}'
            }

            # Save
            model_id = self.model_repo.save_model_version(model_info, model_bytes)

            if model_id:
                self.log_info(f"Saved {model_name} v{version} with ID {model_id}")

            return model_id

        except Exception as e:
            self.log_error(f"Error saving model: {str(e)}")
            return None

    # ============================================
    # RETRAINING WORKFLOWS
    # ============================================

    def retrain_all_models(
        self,
        days: int = 30,
        auto_activate: bool = False
    ) -> Dict[str, Dict]:
        """
        Retrain all models

        Args:
            days: Days of history to use
            auto_activate: Auto-activate if better performance

        Returns:
            Dictionary with results for each model
        """
        try:
            results = {}
            models = ['severity', 'eta', 'ambulance', 'route']

            for model_name in models:
                self.log_info(f"Retraining {model_name}...")

                # Train
                train_result = self.train_model(model_name, days)

                if train_result['success']:
                    # Save
                    version = f"retrain-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                    model_id = self.save_trained_model(
                        model_name,
                        version,
                        train_result.get('eval_metrics', {}),
                        description=f"Auto-retrained on {days} days of data"
                    )

                    train_result['saved_model_id'] = model_id

                    # Check if should activate
                    if auto_activate and model_id:
                        if self._should_activate_model(model_name, train_result):
                            self.model_manager.activate_model_version(model_name, version)
                            self.log_info(f"Auto-activated {model_name} v{version}")

                results[model_name] = train_result

            self.log_info(f"Retraining complete: {results}")
            return results

        except Exception as e:
            self.log_error(f"Error in retraining workflow: {str(e)}")
            return {}

    def _should_activate_model(self, model_name: str, train_result: Dict) -> bool:
        """
        Determine if model should be activated based on performance

        Args:
            model_name: Model name
            train_result: Training result

        Returns:
            True if should activate
        """
        try:
            eval_metrics = train_result.get('eval_metrics', {})

            # Get current model performance
            current_model = self.model_manager.get_model(model_name)
            if not current_model:
                return True  # No current model, activate new one

            current_perf = self.model_manager.get_model_performance(model_name)

            # Compare metrics based on model type
            if model_name == 'eta':
                # Lower is better for MAE
                new_mae = eval_metrics.get('mae', float('inf'))
                current_mae = current_perf.get('mae', 0)
                return new_mae < current_mae * 0.95  # 5% improvement threshold

            elif model_name == 'severity':
                # Higher is better for accuracy
                new_acc = eval_metrics.get('accuracy', 0)
                current_acc = current_perf.get('accuracy', 0)
                return new_acc > current_acc * 1.05  # 5% improvement threshold

            else:
                # Conservative: require 3% improvement
                return True

        except Exception as e:
            self.log_warning(f"Error comparing model performance: {str(e)}")
            return False

    # ============================================
    # PERFORMANCE ANALYSIS
    # ============================================

    def analyze_model_performance(self, model_name: str, days: int = 7) -> Dict[str, Any]:
        """
        Analyze model performance from historical data

        Args:
            model_name: Model to analyze
            days: Days of history to analyze

        Returns:
            Performance analysis
        """
        try:
            self.log_info(f"Analyzing performance for {model_name}")

            # Get test data
            features_list, labels = self.prepare_training_data(model_name, days, min_samples=1)

            if not features_list:
                return {'error': 'No data available'}

            X_test = np.array([list(f.values()) for f in features_list])
            y_test = np.array(labels)

            # Get model and evaluate
            model = self.model_manager.get_model(model_name)
            if not model:
                return {'error': 'Model not found'}

            metrics = model.evaluate(X_test, y_test)

            return {
                'model_name': model_name,
                'analysis_period_days': days,
                'sample_count': len(X_test),
                'metrics': metrics,
                'analyzed_at': datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.log_error(f"Error analyzing model performance: {str(e)}")
            return {'error': str(e)}

    # ============================================
    # TRAINING STATISTICS
    # ============================================

    def get_training_history(self, model_name: str, limit: int = 10) -> List[Dict]:
        """
        Get training history for a model

        Args:
            model_name: Model name
            limit: Maximum records

        Returns:
            List of training records
        """
        try:
            versions = self.model_repo.get_model_versions(model_name, limit)

            history = []
            for version in versions:
                history.append({
                    'version': version.get('version'),
                    'trained_at': version.get('training_date'),
                    'training_samples': version.get('training_samples'),
                    'metrics': version.get('metrics'),
                    'is_active': version.get('is_active')
                })

            return history

        except Exception as e:
            self.log_error(f"Error getting training history: {str(e)}")
            return []

    def compare_training_results(
        self,
        model_name: str,
        version1: str,
        version2: str
    ) -> Dict[str, Any]:
        """
        Compare two model versions

        Args:
            model_name: Model name
            version1: First version
            version2: Second version

        Returns:
            Comparison results
        """
        try:
            model1 = self.model_repo.get_model_version(model_name, version1)
            model2 = self.model_repo.get_model_version(model_name, version2)

            if not model1 or not model2:
                return {'error': 'One or both versions not found'}

            return {
                'model_name': model_name,
                'version1': {
                    'version': version1,
                    'metrics': model1.get('metrics'),
                    'training_samples': model1.get('training_samples')
                },
                'version2': {
                    'version': version2,
                    'metrics': model2.get('metrics'),
                    'training_samples': model2.get('training_samples')
                }
            }

        except Exception as e:
            self.log_error(f"Error comparing versions: {str(e)}")
            return {'error': str(e)}
