"""
Base Model Class for ML Models
Provides common functionality for all ML models
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd
from datetime import datetime
import joblib
from pathlib import Path

from ..config.logger import LoggerMixin


class BaseModel(ABC, LoggerMixin):
    """
    Abstract base class for all ML models

    Provides:
    - Common training/prediction interface
    - Model versioning
    - Persistence (save/load)
    - Metrics tracking
    - Feature management
    """

    def __init__(
        self,
        model_name: str,
        model_type: str,
        model_path: Optional[str] = None,
        version: str = '1.0.0'
    ):
        """
        Initialize base model

        Args:
            model_name: Name of the model (eta, severity, ambulance, route)
            model_type: Type of underlying algorithm
            model_path: Path to pre-trained model
            version: Model version
        """
        self.model_name = model_name
        self.model_type = model_type
        self.version = version
        self.model = None
        self.scaler = None
        self.feature_names = []
        self.metadata = {
            'name': model_name,
            'type': model_type,
            'version': version,
            'created_at': datetime.utcnow().isoformat(),
            'trained_at': None,
            'training_samples': 0
        }

        if model_path:
            self.load_model(model_path)
        else:
            self._initialize_model()

        self.log_info(f"Initialized {model_name} model (type: {model_type})")

    @abstractmethod
    def _initialize_model(self):
        """
        Initialize untrained model
        Must be implemented by subclasses
        """
        pass

    @abstractmethod
    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        **kwargs
    ) -> Dict[str, float]:
        """
        Train the model

        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features (optional)
            y_val: Validation labels (optional)
            **kwargs: Additional training parameters

        Returns:
            Dictionary with training metrics
        """
        pass

    @abstractmethod
    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make prediction for single sample

        Args:
            features: Feature dictionary

        Returns:
            Prediction result
        """
        pass

    def batch_predict(self, features_list: list) -> list:
        """
        Make predictions for multiple samples

        Args:
            features_list: List of feature dictionaries

        Returns:
            List of predictions
        """
        try:
            predictions = []
            for features in features_list:
                pred = self.predict(features)
                predictions.append(pred)

            self.log_info(f"Batch prediction for {len(predictions)} items")
            return predictions

        except Exception as e:
            self.log_error(f"Error in batch prediction: {str(e)}")
            raise

    def save_model(self, path: str) -> bool:
        """
        Save model to disk

        Args:
            path: Path to save model

        Returns:
            True if successful
        """
        try:
            Path(path).mkdir(parents=True, exist_ok=True)

            # Save model
            joblib.dump(self.model, f"{path}/{self.model_name}_model.pkl")

            # Save scaler if it exists
            if self.scaler is not None:
                joblib.dump(self.scaler, f"{path}/{self.model_name}_scaler.pkl")

            # Save metadata
            self.metadata['saved_at'] = datetime.utcnow().isoformat()
            with open(f"{path}/{self.model_name}_metadata.json", 'w') as f:
                import json
                json.dump(self.metadata, f, indent=2)

            self.log_info(f"Model saved to {path}")
            return True

        except Exception as e:
            self.log_error(f"Error saving model: {str(e)}")
            return False

    def load_model(self, path: str) -> bool:
        """
        Load model from disk

        Args:
            path: Path to load model from

        Returns:
            True if successful
        """
        try:
            # Load model
            self.model = joblib.load(f"{path}/{self.model_name}_model.pkl")

            # Load scaler if it exists
            scaler_path = f"{path}/{self.model_name}_scaler.pkl"
            if Path(scaler_path).exists():
                self.scaler = joblib.load(scaler_path)

            # Load metadata
            metadata_path = f"{path}/{self.model_name}_metadata.json"
            if Path(metadata_path).exists():
                import json
                with open(metadata_path, 'r') as f:
                    self.metadata = json.load(f)

            self.log_info(f"Model loaded from {path}")
            return True

        except Exception as e:
            self.log_error(f"Error loading model: {str(e)}")
            return False

    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance from tree-based models

        Returns:
            Dictionary mapping feature names to importance scores
        """
        if hasattr(self.model, 'feature_importances_'):
            importances = self.model.feature_importances_
            return {
                name: float(importance)
                for name, importance in zip(self.feature_names, importances)
            }
        return {}

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get model information

        Returns:
            Dictionary with model metadata
        """
        return {
            'name': self.model_name,
            'type': self.model_type,
            'version': self.version,
            'metadata': self.metadata,
            'feature_count': len(self.feature_names),
            'feature_names': self.feature_names
        }

    def validate_features(self, features: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate input features

        Args:
            features: Feature dictionary to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        required_keys = set(self.feature_names)
        provided_keys = set(features.keys())

        missing_keys = required_keys - provided_keys
        if missing_keys:
            return False, f"Missing features: {missing_keys}"

        return True, None

    def evaluate(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray,
        metrics: Optional[list] = None
    ) -> Dict[str, float]:
        """
        Evaluate model on test data

        Args:
            X_test: Test features
            y_test: Test labels
            metrics: List of metric names to compute

        Returns:
            Dictionary with evaluation metrics
        """
        try:
            if X_test.shape[0] == 0:
                return {}

            # Make predictions
            y_pred = self.model.predict(X_test)

            results = {}

            # If metrics not specified, compute basic ones
            if metrics is None:
                from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

                results['mae'] = float(mean_absolute_error(y_test, y_pred))
                results['rmse'] = float(np.sqrt(mean_squared_error(y_test, y_pred)))
                results['r2'] = float(r2_score(y_test, y_pred))
            else:
                # Compute specified metrics
                from sklearn import metrics as sklearn_metrics

                for metric_name in metrics:
                    if hasattr(sklearn_metrics, metric_name):
                        metric_fn = getattr(sklearn_metrics, metric_name)
                        results[metric_name] = float(metric_fn(y_test, y_pred))

            self.log_info(f"Model evaluation results: {results}")
            return results

        except Exception as e:
            self.log_error(f"Error evaluating model: {str(e)}")
            return {}

    def update_metadata(self, **kwargs):
        """
        Update model metadata

        Args:
            **kwargs: Key-value pairs to update in metadata
        """
        self.metadata.update(kwargs)
        self.log_info(f"Metadata updated: {kwargs}")

    def get_model_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive model statistics

        Returns:
            Dictionary with model statistics
        """
        return {
            'model_info': self.get_model_info(),
            'feature_importance': self.get_feature_importance(),
            'metadata': self.metadata
        }

    def __repr__(self) -> str:
        """String representation of model"""
        return f"{self.__class__.__name__}(name={self.model_name}, type={self.model_type}, version={self.version})"
