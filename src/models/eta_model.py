"""
ETA (Estimated Time of Arrival) Model
Predicts how long it will take for an ambulance to arrive
"""

import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any
from datetime import datetime, timedelta
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import joblib

from ..config.logger import LoggerMixin


class ETAModel(LoggerMixin):
    """
    ETA Model for predicting ambulance arrival time

    Features:
    - Distance (km)
    - Hour of day
    - Day of week
    - Traffic level (0-5)
    - Weather conditions
    - Time of day category (rush hour, night, etc)
    """

    def __init__(self, model_type: str = 'gradient_boosting', model_path: str = None):
        """
        Initialize ETA model

        Args:
            model_type: Type of model ('linear', 'gradient_boosting')
            model_path: Path to pre-trained model
        """
        self.model_type = model_type
        self.model = None
        self.scaler = None
        self.feature_names = [
            'distance_km',
            'hour_of_day',
            'day_of_week',
            'traffic_level',
            'weather_code',
            'is_rush_hour',
            'is_night_time'
        ]

        if model_path:
            self.load_model(model_path)
        else:
            self._initialize_model()

    def _initialize_model(self):
        """Initialize a new untrained model"""
        if self.model_type == 'linear':
            self.model = LinearRegression()
        elif self.model_type == 'gradient_boosting':
            self.model = GradientBoostingRegressor(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42,
                verbose=0
            )
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

        self.scaler = StandardScaler()
        self.log_info(f"Initialized {self.model_type} ETA model")

    def train(self, X_train: np.ndarray, y_train: np.ndarray) -> Dict[str, float]:
        """
        Train the ETA model

        Args:
            X_train: Training features
            y_train: Training labels (ETA in minutes)

        Returns:
            Training metrics
        """
        try:
            self.log_info("Starting ETA model training")

            # Fit scaler on training data
            X_scaled = self.scaler.fit_transform(X_train)

            # Train model
            self.model.fit(X_scaled, y_train)

            # Evaluate on training data
            y_pred = self.model.predict(X_scaled)
            mae = np.mean(np.abs(y_pred - y_train))
            rmse = np.sqrt(np.mean((y_pred - y_train) ** 2))
            r2 = self.model.score(X_scaled, y_train)

            metrics = {
                'mae': float(mae),
                'rmse': float(rmse),
                'r2': float(r2),
                'samples': len(y_train)
            }

            self.log_info(f"ETA model training completed: {metrics}")
            return metrics

        except Exception as e:
            self.log_error(f"Error training ETA model: {str(e)}")
            raise

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict ETA for a dispatch

        Args:
            features: Dictionary with:
                - distance_km: Distance in kilometers
                - hour_of_day: Hour (0-23)
                - day_of_week: Day (0-6, Monday=0)
                - traffic_level: Traffic level (0-5)
                - weather_code: Weather code (clear, rain, fog, etc)

        Returns:
            Dictionary with:
                - estimated_minutes: Predicted ETA in minutes
                - confidence: Confidence score (0-1)
                - lower_bound: Lower bound (5th percentile)
                - upper_bound: Upper bound (95th percentile)
        """
        try:
            # Prepare features
            X = self._prepare_features(features)

            # Make prediction
            X_scaled = self.scaler.transform(X)
            eta_minutes = float(self.model.predict(X_scaled)[0])

            # Calculate confidence based on input validity
            confidence = self._calculate_confidence(features, eta_minutes)

            # Add bounds
            std_dev = eta_minutes * 0.15  # 15% std dev
            lower_bound = max(1, eta_minutes - (1.96 * std_dev))
            upper_bound = eta_minutes + (1.96 * std_dev)

            result = {
                'estimated_minutes': round(eta_minutes, 1),
                'confidence': round(confidence, 2),
                'lower_bound': round(lower_bound, 1),
                'upper_bound': round(upper_bound, 1),
                'traffic_level': features.get('traffic_level', 2),
                'distance_km': features.get('distance_km', 0)
            }

            self.log_debug(f"ETA prediction: {result}")
            return result

        except Exception as e:
            self.log_error(f"Error predicting ETA: {str(e)}")
            raise

    def predict_batch(self, features_list: list) -> list:
        """
        Batch predict ETA for multiple dispatches

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

            self.log_info(f"Batch ETA prediction for {len(predictions)} items")
            return predictions

        except Exception as e:
            self.log_error(f"Error in batch prediction: {str(e)}")
            raise

    def _prepare_features(self, features: Dict[str, Any]) -> np.ndarray:
        """
        Prepare and validate features for model

        Args:
            features: Raw features dictionary

        Returns:
            Numpy array with features in correct order
        """
        distance = features.get('distance_km', 5)
        hour = features.get('hour_of_day', 12)
        day_of_week = features.get('day_of_week', 0)
        traffic = features.get('traffic_level', 2)
        weather = features.get('weather_code', 0)

        is_rush_hour = 1 if hour in [7, 8, 9, 17, 18, 19] else 0
        is_night_time = 1 if hour in [0, 1, 2, 3, 4, 5, 22, 23] else 0

        X = np.array([[
            distance,
            hour,
            day_of_week,
            traffic,
            weather,
            is_rush_hour,
            is_night_time
        ]])

        return X

    def _calculate_confidence(self, features: Dict[str, Any], eta: float) -> float:
        """
        Calculate confidence score for prediction

        Args:
            features: Features used
            eta: Predicted ETA

        Returns:
            Confidence score 0-1
        """
        confidence = 0.9  # Base confidence

        # Reduce confidence for very large distances
        distance = features.get('distance_km', 0)
        if distance > 20:
            confidence -= 0.1

        # Reduce confidence for traffic extremes
        traffic = features.get('traffic_level', 2)
        if traffic >= 4:
            confidence -= 0.05

        return max(0.5, min(1.0, confidence))

    def save_model(self, path: str):
        """
        Save model to disk

        Args:
            path: Path to save model
        """
        try:
            joblib.dump(self.model, f"{path}/eta_model.pkl")
            joblib.dump(self.scaler, f"{path}/eta_scaler.pkl")
            self.log_info(f"ETA model saved to {path}")
        except Exception as e:
            self.log_error(f"Error saving ETA model: {str(e)}")
            raise

    def load_model(self, path: str):
        """
        Load model from disk

        Args:
            path: Path to load model from
        """
        try:
            self.model = joblib.load(f"{path}/eta_model.pkl")
            self.scaler = joblib.load(f"{path}/eta_scaler.pkl")
            self.log_info(f"ETA model loaded from {path}")
        except Exception as e:
            self.log_error(f"Error loading ETA model: {str(e)}")
            raise

    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance from tree-based models

        Returns:
            Dictionary with feature importances
        """
        if hasattr(self.model, 'feature_importances_'):
            importances = self.model.feature_importances_
            return {
                name: float(importance)
                for name, importance in zip(self.feature_names, importances)
            }
        return {}
