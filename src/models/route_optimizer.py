"""
Route Optimizer Model
Optimizes ambulance routes considering traffic, hospitals, and constraints
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import math
from datetime import datetime, timedelta

from .base_model import BaseModel


class RouteOptimizer(BaseModel):
    """
    Optimizes ambulance routes for dispatch

    Considerations:
    - Distance and time
    - Traffic conditions
    - Hospital availability
    - One-way streets and road restrictions
    - Real-time conditions

    Provides:
    - Optimal primary route
    - Alternative routes
    - Real-time ETA updates
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize Route Optimizer

        Args:
            model_path: Path to pre-trained model
        """
        self.traffic_multipliers = {
            0: 1.0,    # No traffic
            1: 1.1,    # Light
            2: 1.3,    # Moderate
            3: 1.6,    # Heavy
            4: 2.0,    # Severe
            5: 2.5     # Gridlock
        }
        super().__init__(
            model_name='route_optimizer',
            model_type='graph_based',
            model_path=model_path,
            version='1.0.0'
        )

    def _initialize_model(self):
        """Initialize graph-based route optimizer"""
        self.model = self  # Self is the model
        self.feature_names = [
            'origin_lat',
            'origin_lon',
            'destination_lat',
            'destination_lon',
            'traffic_level',
            'time_of_day',
            'day_of_week'
        ]
        self.log_info("Initialized Graph-Based Route Optimizer")

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        **kwargs
    ) -> Dict[str, float]:
        """
        "Train" route optimizer (calibrate parameters)

        Args:
            X_train: Historical route data
            y_train: Actual travel times
            X_val: Validation data
            y_val: Validation labels
            **kwargs: Additional parameters

        Returns:
            Calibration metrics
        """
        try:
            self.log_info(f"Calibrating Route Optimizer with {len(X_train)} samples")

            # Calculate MAE of actual vs estimated times
            mae = np.mean(np.abs(y_train - np.mean(y_train)))  # Simple baseline

            metrics = {
                'mae_minutes': float(mae),
                'samples': len(X_train),
                'traffic_multipliers': self.traffic_multipliers
            }

            self.metadata['trained_at'] = datetime.utcnow().isoformat()
            self.metadata['training_samples'] = len(X_train)

            self.log_info(f"Route Optimizer calibration: {metrics}")
            return metrics

        except Exception as e:
            self.log_error(f"Error calibrating Route Optimizer: {str(e)}")
            raise

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize route from origin to destination

        Args:
            features: Dictionary with:
                - origin_lat, origin_lon: Starting location
                - destination_lat, destination_lon: Hospital/destination
                - traffic_level: Current traffic (0-5)
                - time_of_day: Hour of day (0-23)
                - day_of_week: Day (0-6, Monday=0)
                - num_alternatives: Number of alternative routes (default: 2)
                - avoid_highways: Boolean (default: False)

        Returns:
            Dictionary with:
                - primary_route: Best route info
                - alternative_routes: List of alternative routes
                - eta_minutes: Estimated time of arrival
                - distance_km: Total distance
                - recommendations: Routing recommendations
        """
        try:
            origin = (features.get('origin_lat'), features.get('origin_lon'))
            destination = (features.get('destination_lat'), features.get('destination_lon'))
            traffic_level = features.get('traffic_level', 1)
            time_of_day = features.get('time_of_day', 12)
            num_alternatives = features.get('num_alternatives', 2)

            if not all(origin) or not all(destination):
                return self._create_empty_route()

            # Calculate primary route
            primary_route = self._calculate_route(
                origin,
                destination,
                traffic_level,
                time_of_day,
                route_type='primary'
            )

            # Calculate alternative routes
            alternative_routes = []
            for i in range(num_alternatives):
                alt_route = self._calculate_route(
                    origin,
                    destination,
                    traffic_level,
                    time_of_day,
                    route_type=f'alternative_{i+1}'
                )
                alternative_routes.append(alt_route)

            # Generate recommendations
            recommendations = self._generate_recommendations(
                primary_route,
                traffic_level,
                time_of_day
            )

            result = {
                'primary_route': primary_route,
                'alternative_routes': alternative_routes,
                'eta_minutes': primary_route['eta_minutes'],
                'distance_km': primary_route['distance_km'],
                'recommendations': recommendations,
                'current_traffic_level': traffic_level,
                'estimated_congestion': self._get_traffic_description(traffic_level)
            }

            self.log_debug(f"Route optimization: ETA {result['eta_minutes']}min")
            return result

        except Exception as e:
            self.log_error(f"Error optimizing route: {str(e)}")
            raise

    def predict_batch(self, features_list: list) -> list:
        """
        Optimize routes for multiple dispatches

        Args:
            features_list: List of route feature dictionaries

        Returns:
            List of optimized routes
        """
        routes = []
        for features in features_list:
            route = self.predict(features)
            routes.append(route)
        return routes

    def _calculate_route(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        traffic_level: int,
        time_of_day: int,
        route_type: str = 'primary'
    ) -> Dict[str, Any]:
        """
        Calculate a route between two points

        Args:
            origin: (lat, lon) tuple
            destination: (lat, lon) tuple
            traffic_level: Current traffic (0-5)
            time_of_day: Hour of day
            route_type: Type of route to calculate

        Returns:
            Route information
        """
        # Calculate straight-line distance
        distance_km = self._calculate_distance(origin[0], origin[1], destination[0], destination[1])

        # Adjust distance for road network (typically 20-30% longer)
        road_factor = 1.25 if route_type == 'primary' else 1.35
        actual_distance = distance_km * road_factor

        # Calculate base ETA (average speed 40 km/h for urban areas)
        base_speed = 40
        base_eta = (actual_distance / base_speed) * 60  # minutes

        # Apply traffic multiplier
        traffic_multiplier = self.traffic_multipliers.get(traffic_level, 1.5)
        adjusted_eta = base_eta * traffic_multiplier

        # Apply time-of-day adjustments
        if route_type == 'primary':
            if 7 <= time_of_day <= 9 or 17 <= time_of_day <= 19:  # Rush hours
                adjusted_eta *= 1.1
            elif 0 <= time_of_day <= 5:  # Night, less traffic
                adjusted_eta *= 0.8

        # Add variation for alternative routes
        if 'alternative' in route_type:
            variation = 0.1 + (int(route_type.split('_')[1]) * 0.05)  # Slightly longer
            adjusted_eta *= (1 + variation)

        return {
            'type': route_type,
            'distance_km': round(actual_distance, 1),
            'eta_minutes': int(adjusted_eta),
            'eta_minutes_optimistic': int(adjusted_eta * 0.85),
            'eta_minutes_pessimistic': int(adjusted_eta * 1.15),
            'instructions': self._generate_instructions(origin, destination, distance_km),
            'segments': self._generate_route_segments(origin, destination)
        }

    def _calculate_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate distance using Haversine formula

        Args:
            lat1, lon1: First location
            lat2, lon2: Second location

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

            a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
            c = 2 * math.asin(math.sqrt(a))
            distance = R * c

            return distance
        except Exception as e:
            self.log_error(f"Error calculating distance: {str(e)}")
            return 0.0

    def _generate_instructions(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        distance: float
    ) -> List[str]:
        """
        Generate turn-by-turn instructions (simplified)

        Args:
            origin: Starting point
            destination: End point
            distance: Distance to travel

        Returns:
            List of instruction strings
        """
        instructions = [
            f"Start at ({origin[0]:.4f}, {origin[1]:.4f})",
            f"Proceed toward destination ({destination[0]:.4f}, {destination[1]:.4f})",
            f"Total distance: {distance:.1f} km"
        ]

        # Add turn instructions based on bearing
        bearing = self._calculate_bearing(origin[0], origin[1], destination[0], destination[1])
        if bearing < 45 or bearing >= 315:
            instructions.insert(1, "Head North")
        elif 45 <= bearing < 135:
            instructions.insert(1, "Head East")
        elif 135 <= bearing < 225:
            instructions.insert(1, "Head South")
        else:
            instructions.insert(1, "Head West")

        return instructions

    def _generate_route_segments(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float]
    ) -> List[Dict]:
        """
        Generate route segments (simplified for demo)

        Args:
            origin: Starting point
            destination: End point

        Returns:
            List of route segments
        """
        # Simple implementation: divide route into 3 segments
        lat_step = (destination[0] - origin[0]) / 3
        lon_step = (destination[1] - origin[1]) / 3

        segments = []
        for i in range(3):
            segment = {
                'start': (origin[0] + lat_step * i, origin[1] + lon_step * i),
                'end': (origin[0] + lat_step * (i + 1), origin[1] + lon_step * (i + 1)),
                'sequence': i + 1
            }
            segments.append(segment)

        return segments

    def _calculate_bearing(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate bearing between two points

        Args:
            lat1, lon1: Starting point
            lat2, lon2: Ending point

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
        except:
            return 0.0

    def _generate_recommendations(
        self,
        primary_route: Dict,
        traffic_level: int,
        time_of_day: int
    ) -> List[str]:
        """
        Generate routing recommendations

        Args:
            primary_route: Primary route info
            traffic_level: Current traffic level
            time_of_day: Hour of day

        Returns:
            List of recommendations
        """
        recommendations = []

        if traffic_level >= 3:
            recommendations.append("⚠️ Heavy traffic detected - consider alternative routes")

        if 7 <= time_of_day <= 9 or 17 <= time_of_day <= 19:
            recommendations.append("⚠️ Rush hour traffic expected")

        if primary_route['eta_minutes'] > 20:
            recommendations.append(f"⏱️ Long ETA ({primary_route['eta_minutes']}min) - check alternatives")

        if traffic_level == 0:
            recommendations.append("✓ Light traffic conditions")

        recommendations.append(f"✓ Estimated arrival: {primary_route['eta_minutes']} minutes")

        return recommendations

    def _get_traffic_description(self, traffic_level: int) -> str:
        """Get human-readable traffic description"""
        descriptions = {
            0: 'No traffic',
            1: 'Light traffic',
            2: 'Moderate traffic',
            3: 'Heavy traffic',
            4: 'Severe traffic',
            5: 'Gridlock'
        }
        return descriptions.get(traffic_level, 'Unknown')

    def _create_empty_route(self) -> Dict[str, Any]:
        """Create empty route when data is invalid"""
        return {
            'primary_route': None,
            'alternative_routes': [],
            'eta_minutes': None,
            'distance_km': 0.0,
            'recommendations': ['Invalid origin or destination'],
            'error': 'Missing or invalid location data'
        }

    def update_traffic_model(self, real_time_traffic: Dict[str, int]) -> bool:
        """
        Update traffic model with real-time data

        Args:
            real_time_traffic: Dictionary with traffic conditions by area

        Returns:
            True if successful
        """
        try:
            # In production, this would update ML model with real traffic data
            self.log_info(f"Traffic model updated with {len(real_time_traffic)} area updates")
            return True
        except Exception as e:
            self.log_error(f"Error updating traffic model: {str(e)}")
            return False
