"""
Feature Engineering
Data preparation and feature extraction utilities for ML models
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import math
import numpy as np

from ..config.logger import LoggerMixin


class FeatureEngineer(LoggerMixin):
    """
    Feature engineering and data preparation utilities

    Provides:
    - Geographic feature extraction
    - Temporal feature engineering
    - Data normalization and scaling
    - Feature validation
    """

    def __init__(self):
        """Initialize Feature Engineer"""
        self.log_info("Initialized FeatureEngineer")

    # ============================================
    # GEOGRAPHIC FEATURES
    # ============================================

    @staticmethod
    def calculate_distance(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate distance between two points using Haversine formula

        Args:
            lat1, lon1: First point (latitude, longitude)
            lat2, lon2: Second point (latitude, longitude)

        Returns:
            Distance in kilometers
        """
        try:
            R = 6371  # Earth radius in km

            lat1_rad = math.radians(lat1)
            lon1_rad = math.radians(lon1)
            lat2_rad = math.radians(lat2)
            lon2_rad = math.radians(lon2)

            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad

            a = (math.sin(dlat / 2) ** 2 +
                 math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
            c = 2 * math.asin(math.sqrt(a))
            distance = R * c

            return distance

        except Exception:
            return 0.0

    @staticmethod
    def calculate_bearing(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate bearing (direction) between two points

        Args:
            lat1, lon1: Starting point
            lat2, lon2: Destination point

        Returns:
            Bearing in degrees (0-360)
        """
        try:
            lat1_rad = math.radians(lat1)
            lon1_rad = math.radians(lon1)
            lat2_rad = math.radians(lat2)
            lon2_rad = math.radians(lon2)

            dlon = lon2_rad - lon1_rad

            x = math.sin(dlon) * math.cos(lat2_rad)
            y = (math.cos(lat1_rad) * math.sin(lat2_rad) -
                 math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon))

            bearing = (math.degrees(math.atan2(x, y)) + 360) % 360
            return bearing

        except Exception:
            return 0.0

    def extract_geographic_features(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float
    ) -> Dict[str, float]:
        """
        Extract geographic features for a route

        Args:
            origin_lat, origin_lon: Starting location
            destination_lat, destination_lon: Destination

        Returns:
            Dictionary with geographic features
        """
        distance = self.calculate_distance(
            origin_lat, origin_lon,
            destination_lat, destination_lon
        )

        bearing = self.calculate_bearing(
            origin_lat, origin_lon,
            destination_lat, destination_lon
        )

        # Cardinal direction
        if bearing < 45 or bearing >= 315:
            direction = "N"
        elif 45 <= bearing < 135:
            direction = "E"
        elif 135 <= bearing < 225:
            direction = "S"
        else:
            direction = "W"

        return {
            'distance_km': distance,
            'bearing_degrees': bearing,
            'cardinal_direction': direction,
            'lat_diff': abs(destination_lat - origin_lat),
            'lon_diff': abs(destination_lon - origin_lon)
        }

    # ============================================
    # TEMPORAL FEATURES
    # ============================================

    @staticmethod
    def extract_datetime_features(timestamp: datetime) -> Dict[str, int]:
        """
        Extract temporal features from datetime

        Args:
            timestamp: DateTime object

        Returns:
            Dictionary with temporal features
        """
        return {
            'hour': timestamp.hour,
            'day_of_week': timestamp.weekday(),  # 0=Monday, 6=Sunday
            'day_of_month': timestamp.day,
            'month': timestamp.month,
            'is_weekend': 1 if timestamp.weekday() >= 5 else 0,
            'is_night': 1 if 0 <= timestamp.hour < 6 else 0,
            'is_early_morning': 1 if 6 <= timestamp.hour < 9 else 0,
            'is_morning': 1 if 9 <= timestamp.hour < 12 else 0,
            'is_afternoon': 1 if 12 <= timestamp.hour < 17 else 0,
            'is_evening': 1 if 17 <= timestamp.hour < 21 else 0,
            'is_late_night': 1 if 21 <= timestamp.hour < 24 else 0,
            'is_rush_hour': 1 if (7 <= timestamp.hour <= 9 or 17 <= timestamp.hour <= 19) else 0,
            'is_holiday': 0  # Would need holiday calendar to determine
        }

    def extract_time_window_features(self, timestamp: datetime) -> Dict[str, int]:
        """
        Extract time window features for dispatch

        Args:
            timestamp: DateTime object

        Returns:
            Dictionary with time window features
        """
        hour = timestamp.hour

        # Define time windows
        windows = {
            'night': 1 if 0 <= hour < 6 else 0,
            'early_morning': 1 if 6 <= hour < 9 else 0,
            'morning_rush': 1 if 7 <= hour < 9 else 0,
            'morning': 1 if 9 <= hour < 12 else 0,
            'lunch': 1 if 12 <= hour < 14 else 0,
            'afternoon': 1 if 14 <= hour < 17 else 0,
            'evening_rush': 1 if 17 <= hour < 19 else 0,
            'evening': 1 if 19 <= hour < 21 else 0,
            'late_night': 1 if 21 <= hour < 24 else 0
        }

        return windows

    # ============================================
    # TRAFFIC & WEATHER FEATURES
    # ============================================

    def encode_traffic_level(self, traffic_level: int) -> Dict[str, float]:
        """
        Encode traffic level as features

        Args:
            traffic_level: Traffic level (0-5)

        Returns:
            Dictionary with traffic features
        """
        # One-hot encoding for traffic levels
        return {
            'traffic_no': 1 if traffic_level == 0 else 0,
            'traffic_light': 1 if traffic_level == 1 else 0,
            'traffic_moderate': 1 if traffic_level == 2 else 0,
            'traffic_heavy': 1 if traffic_level == 3 else 0,
            'traffic_severe': 1 if traffic_level == 4 else 0,
            'traffic_gridlock': 1 if traffic_level == 5 else 0,
            'traffic_numeric': traffic_level / 5.0  # Normalized 0-1
        }

    def encode_weather(self, weather_condition: str) -> Dict[str, float]:
        """
        Encode weather condition as features

        Args:
            weather_condition: Weather code/description

        Returns:
            Dictionary with weather features
        """
        weather_map = {
            'clear': {'clear': 1, 'cloudy': 0, 'rainy': 0, 'snowy': 0},
            'cloudy': {'clear': 0, 'cloudy': 1, 'rainy': 0, 'snowy': 0},
            'rainy': {'clear': 0, 'cloudy': 0, 'rainy': 1, 'snowy': 0},
            'snowy': {'clear': 0, 'cloudy': 0, 'rainy': 0, 'snowy': 1},
            'fog': {'clear': 0, 'cloudy': 1, 'rainy': 0, 'snowy': 0}
        }

        return weather_map.get(weather_condition.lower(), weather_map['cloudy'])

    # ============================================
    # SEVERITY FEATURES
    # ============================================

    def extract_severity_indicators(
        self,
        description: str,
        vital_signs: Optional[Dict[str, Any]] = None,
        age: Optional[int] = None
    ) -> Dict[str, float]:
        """
        Extract severity indicators from patient data

        Args:
            description: Patient symptoms description
            vital_signs: Optional vital signs dictionary
            age: Optional patient age

        Returns:
            Dictionary with severity features
        """
        features = {}

        # Text-based indicators
        critical_keywords = ['cardiac', 'arrest', 'unconscious', 'bleeding', 'severe', 'critical']
        high_keywords = ['chest pain', 'difficulty breathing', 'choking', 'trauma']
        medium_keywords = ['pain', 'fever', 'nausea', 'vomiting', 'injury']

        description_lower = description.lower() if description else ""

        features['has_critical_keywords'] = 1 if any(kw in description_lower for kw in critical_keywords) else 0
        features['has_high_keywords'] = 1 if any(kw in description_lower for kw in high_keywords) else 0
        features['has_medium_keywords'] = 1 if any(kw in description_lower for kw in medium_keywords) else 0
        features['description_length'] = len(description_lower.split()) if description else 0

        # Vital signs features
        if vital_signs:
            features['has_vital_signs'] = 1

            if 'heart_rate' in vital_signs:
                hr = vital_signs['heart_rate']
                features['heart_rate'] = hr
                features['abnormal_heart_rate'] = 1 if hr < 40 or hr > 120 else 0

            if 'blood_pressure' in vital_signs:
                bp = vital_signs['blood_pressure']
                # Assume format "SYS/DIA"
                try:
                    sys, dia = map(int, bp.split('/'))
                    features['systolic'] = sys
                    features['diastolic'] = dia
                    features['abnormal_bp'] = 1 if sys > 180 or sys < 90 or dia > 120 else 0
                except:
                    pass

            if 'temperature' in vital_signs:
                temp = vital_signs['temperature']
                features['temperature'] = temp
                features['abnormal_temp'] = 1 if temp < 36 or temp > 39 else 0

            if 'respiratory_rate' in vital_signs:
                rr = vital_signs['respiratory_rate']
                features['respiratory_rate'] = rr
                features['abnormal_respiration'] = 1 if rr < 12 or rr > 20 else 0
        else:
            features['has_vital_signs'] = 0

        # Age features
        if age:
            features['age'] = age
            features['age_child'] = 1 if age < 18 else 0
            features['age_elderly'] = 1 if age > 65 else 0
            features['age_critical'] = 1 if age < 5 or age > 80 else 0

        return features

    # ============================================
    # AMBULANCE FEATURES
    # ============================================

    def extract_ambulance_features(self, ambulance_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Extract features from ambulance data

        Args:
            ambulance_data: Ambulance information

        Returns:
            Dictionary with ambulance features
        """
        features = {}

        # Type encoding
        type_map = {
            'basic': 1,
            'advanced': 2,
            'mobile_icu': 3
        }
        ambulance_type = ambulance_data.get('type', 'basic')
        features['type_level'] = type_map.get(ambulance_type, 1)

        # Status
        features['is_available'] = 1 if ambulance_data.get('status') == 'available' else 0

        # Equipment level (1-5)
        features['equipment_level'] = ambulance_data.get('equipment_level', 1)

        # Response time history
        avg_response = ambulance_data.get('avg_response_time', 10)
        features['avg_response_time'] = avg_response
        features['fast_responder'] = 1 if avg_response <= 5 else 0
        features['slow_responder'] = 1 if avg_response > 15 else 0

        # Driver experience (estimated from response times)
        features['experienced_driver'] = 1 if avg_response <= 7 else 0

        return features

    # ============================================
    # DATA NORMALIZATION
    # ============================================

    @staticmethod
    def normalize_value(
        value: float,
        min_val: float,
        max_val: float
    ) -> float:
        """
        Normalize value to 0-1 range

        Args:
            value: Value to normalize
            min_val: Minimum expected value
            max_val: Maximum expected value

        Returns:
            Normalized value (0-1)
        """
        if max_val == min_val:
            return 0.0

        normalized = (value - min_val) / (max_val - min_val)
        return max(0.0, min(1.0, normalized))

    @staticmethod
    def standardize_value(
        value: float,
        mean: float,
        std: float
    ) -> float:
        """
        Standardize value using z-score

        Args:
            value: Value to standardize
            mean: Mean of distribution
            std: Standard deviation

        Returns:
            Z-score
        """
        if std == 0:
            return 0.0

        return (value - mean) / std

    # ============================================
    # FEATURE VALIDATION
    # ============================================

    def validate_features(
        self,
        features: Dict[str, float],
        required_fields: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Validate feature dictionary

        Args:
            features: Feature dictionary to validate
            required_fields: List of required field names

        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []

        for field in required_fields:
            if field not in features:
                errors.append(f"Missing required field: {field}")

            elif features[field] is None:
                errors.append(f"Field is None: {field}")

            elif isinstance(features[field], (int, float)):
                if math.isnan(features[field]) or math.isinf(features[field]):
                    errors.append(f"Invalid numeric value for {field}: {features[field]}")

        return len(errors) == 0, errors

    # ============================================
    # BATCH FEATURE EXTRACTION
    # ============================================

    def extract_features_batch(
        self,
        dispatch_list: List[Dict[str, Any]]
    ) -> List[Dict[str, float]]:
        """
        Extract features for multiple dispatches

        Args:
            dispatch_list: List of dispatch dictionaries

        Returns:
            List of feature dictionaries
        """
        features_list = []

        for dispatch in dispatch_list:
            try:
                features = self.extract_geographic_features(
                    dispatch.get('patient_lat', 0),
                    dispatch.get('patient_lon', 0),
                    dispatch.get('hospital_lat', 0),
                    dispatch.get('hospital_lon', 0)
                )

                # Add temporal features
                timestamp = dispatch.get('timestamp', datetime.utcnow())
                temporal = self.extract_datetime_features(timestamp)
                features.update(temporal)

                # Add traffic features
                traffic = self.encode_traffic_level(dispatch.get('traffic_level', 1))
                features.update(traffic)

                features_list.append(features)

            except Exception as e:
                self.log_error(f"Error extracting features for dispatch: {str(e)}")
                continue

        return features_list

    # ============================================
    # FEATURE IMPORTANCE ANALYSIS
    # ============================================

    @staticmethod
    def get_feature_statistics(
        features_list: List[Dict[str, float]]
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate statistics for extracted features

        Args:
            features_list: List of feature dictionaries

        Returns:
            Dictionary with statistics for each feature
        """
        stats = {}

        for feature_name in features_list[0].keys() if features_list else []:
            values = [f.get(feature_name, 0) for f in features_list if feature_name in f]

            if values:
                stats[feature_name] = {
                    'mean': float(np.mean(values)),
                    'std': float(np.std(values)),
                    'min': float(np.min(values)),
                    'max': float(np.max(values)),
                    'median': float(np.median(values))
                }

        return stats
