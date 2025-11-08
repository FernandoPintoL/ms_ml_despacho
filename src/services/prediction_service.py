"""
Prediction Service
Orchestrates predictions across all ML models
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import time

from ..config.logger import LoggerMixin
from ..repositories import (
    FeatureEngineer, DispatchRepository, AmbulanceRepository,
    ModelRepository, CacheRepository
)
from .model_manager import ModelManager


class PredictionService(LoggerMixin):
    """
    Service for orchestrating ML model predictions

    Provides:
    - Dispatch severity prediction
    - ETA prediction
    - Ambulance selection
    - Route optimization
    - Batch predictions
    - Result caching
    """

    def __init__(
        self,
        model_manager: ModelManager,
        dispatch_repo: DispatchRepository,
        ambulance_repo: AmbulanceRepository,
        model_repo: ModelRepository,
        cache_repo: CacheRepository
    ):
        """
        Initialize Prediction Service

        Args:
            model_manager: ModelManager instance
            dispatch_repo: DispatchRepository instance
            ambulance_repo: AmbulanceRepository instance
            model_repo: ModelRepository instance
            cache_repo: CacheRepository instance
        """
        self.model_manager = model_manager
        self.dispatch_repo = dispatch_repo
        self.ambulance_repo = ambulance_repo
        self.model_repo = model_repo
        self.cache_repo = cache_repo
        self.engineer = FeatureEngineer()
        self.log_info("Initialized PredictionService")

    # ============================================
    # SEVERITY PREDICTION
    # ============================================

    def predict_severity(
        self,
        description: str,
        vital_signs: Optional[Dict] = None,
        age: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Predict case severity level

        Args:
            description: Patient symptoms description
            vital_signs: Optional vital signs (heart_rate, blood_pressure, temperature)
            age: Optional patient age

        Returns:
            Severity prediction with confidence
        """
        try:
            start_time = time.time()

            # Extract features
            features = self.engineer.extract_severity_indicators(description, vital_signs, age)

            # Get model
            model = self.model_manager.get_model('severity')
            if not model:
                self.log_error("Severity model not loaded")
                return self._empty_severity_prediction()

            # Predict
            prediction = model.predict(features)

            # Record prediction
            elapsed_ms = (time.time() - start_time) * 1000
            self.model_manager.record_prediction(
                'severity',
                prediction_time_ms=elapsed_ms,
                input_features=len(features),
                output_value=float(prediction.get('level', 0)),
                confidence=prediction.get('confidence', 0)
            )

            self.log_debug(f"Severity prediction: level {prediction.get('level')}, confidence {prediction.get('confidence')}")

            return prediction

        except Exception as e:
            self.log_error(f"Error predicting severity: {str(e)}")
            return self._empty_severity_prediction()

    def _empty_severity_prediction(self) -> Dict[str, Any]:
        """Create empty severity prediction on error"""
        return {
            'level': 3,  # Default to medium
            'category': 'Unknown',
            'confidence': 0.0,
            'error': 'Prediction failed'
        }

    # ============================================
    # ETA PREDICTION
    # ============================================

    def predict_eta(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
        traffic_level: int = 1,
        time_of_day: Optional[int] = None,
        day_of_week: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Predict ambulance arrival time

        Args:
            origin_lat, origin_lon: Starting location
            destination_lat, destination_lon: Destination
            traffic_level: Current traffic (0-5)
            time_of_day: Hour of day (0-23)
            day_of_week: Day of week (0-6, Monday=0)

        Returns:
            ETA prediction with bounds
        """
        try:
            start_time = time.time()

            # Default time values
            now = datetime.utcnow()
            time_of_day = time_of_day or now.hour
            day_of_week = day_of_week or now.weekday()

            # Extract features
            geo_features = self.engineer.extract_geographic_features(
                origin_lat, origin_lon,
                destination_lat, destination_lon
            )

            temporal_features = self.engineer.extract_datetime_features(now)

            traffic_features = self.engineer.encode_traffic_level(traffic_level)

            # Combine features
            features = {
                **geo_features,
                'hour_of_day': time_of_day,
                'day_of_week': day_of_week,
                'traffic_level': traffic_level,
                **traffic_features
            }

            # Get model
            model = self.model_manager.get_model('eta')
            if not model:
                self.log_error("ETA model not loaded")
                return self._empty_eta_prediction()

            # Predict
            prediction = model.predict(features)

            # Record prediction
            elapsed_ms = (time.time() - start_time) * 1000
            self.model_manager.record_prediction(
                'eta',
                prediction_time_ms=elapsed_ms,
                input_features=len(features),
                output_value=float(prediction.get('estimated_minutes', 0)),
                confidence=prediction.get('confidence', 0)
            )

            self.log_debug(f"ETA prediction: {prediction.get('estimated_minutes')} ± {prediction.get('confidence')}")

            return prediction

        except Exception as e:
            self.log_error(f"Error predicting ETA: {str(e)}")
            return self._empty_eta_prediction()

    def _empty_eta_prediction(self) -> Dict[str, Any]:
        """Create empty ETA prediction on error"""
        return {
            'estimated_minutes': 15,  # Default estimate
            'confidence': 0.0,
            'error': 'Prediction failed'
        }

    # ============================================
    # AMBULANCE SELECTION
    # ============================================

    def select_ambulance(
        self,
        patient_lat: float,
        patient_lon: float,
        severity_level: int,
        required_type: Optional[str] = None,
        exclude_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Select optimal ambulance for dispatch

        Args:
            patient_lat, patient_lon: Patient location
            severity_level: Case severity (1-5)
            required_type: Required ambulance type (optional)
            exclude_ids: Ambulance IDs to exclude (optional)

        Returns:
            Selected ambulance with ranking
        """
        try:
            start_time = time.time()

            # Get available ambulances
            ambulances = self.ambulance_repo.get_available_ambulances_near(
                patient_lat,
                patient_lon,
                radius_km=15,  # Search within 15km
                limit=20
            )

            # Filter out excluded
            if exclude_ids:
                ambulances = [a for a in ambulances if a['id'] not in exclude_ids]

            if not ambulances:
                self.log_warning("No available ambulances found")
                return self._empty_ambulance_selection()

            # Prepare features for model
            features = {
                'patient_lat': patient_lat,
                'patient_lon': patient_lon,
                'available_ambulances': ambulances,
                'severity_level': severity_level,
                'required_type': required_type or 'basic'
            }

            # Get model
            model = self.model_manager.get_model('ambulance')
            if not model:
                self.log_error("Ambulance selector model not loaded")
                return self._empty_ambulance_selection()

            # Predict
            prediction = model.predict(features)

            # Record prediction
            elapsed_ms = (time.time() - start_time) * 1000
            selected_id = prediction.get('ambulance_id')
            confidence = prediction.get('confidence', 0)

            self.model_manager.record_prediction(
                'ambulance',
                prediction_time_ms=elapsed_ms,
                input_features=len(ambulances),
                output_value=float(selected_id or 0),
                confidence=float(confidence)
            )

            self.log_debug(f"Ambulance selected: {selected_id}, confidence: {confidence}")

            return prediction

        except Exception as e:
            self.log_error(f"Error selecting ambulance: {str(e)}")
            return self._empty_ambulance_selection()

    def _empty_ambulance_selection(self) -> Dict[str, Any]:
        """Create empty ambulance selection on error"""
        return {
            'ambulance_id': None,
            'confidence': 0.0,
            'ranking': [],
            'error': 'Selection failed'
        }

    # ============================================
    # ROUTE OPTIMIZATION
    # ============================================

    def optimize_route(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
        traffic_level: int = 1,
        time_of_day: Optional[int] = None,
        num_alternatives: int = 2
    ) -> Dict[str, Any]:
        """
        Optimize ambulance route

        Args:
            origin_lat, origin_lon: Starting location
            destination_lat, destination_lon: Hospital/destination
            traffic_level: Current traffic (0-5)
            time_of_day: Hour of day (optional)
            num_alternatives: Number of alternative routes

        Returns:
            Optimized route with alternatives
        """
        try:
            start_time = time.time()

            # Default time
            time_of_day = time_of_day or datetime.utcnow().hour

            # Prepare features
            features = {
                'origin_lat': origin_lat,
                'origin_lon': origin_lon,
                'destination_lat': destination_lat,
                'destination_lon': destination_lon,
                'traffic_level': traffic_level,
                'time_of_day': time_of_day,
                'day_of_week': datetime.utcnow().weekday(),
                'num_alternatives': num_alternatives
            }

            # Get model
            model = self.model_manager.get_model('route')
            if not model:
                self.log_error("Route optimizer model not loaded")
                return self._empty_route_optimization()

            # Predict
            prediction = model.predict(features)

            # Record prediction
            elapsed_ms = (time.time() - start_time) * 1000
            eta = prediction.get('eta_minutes', 0)

            self.model_manager.record_prediction(
                'route',
                prediction_time_ms=elapsed_ms,
                input_features=len(features),
                output_value=float(eta),
                confidence=0.85  # Default confidence for route
            )

            self.log_debug(f"Route optimized: ETA {eta} minutes")

            return prediction

        except Exception as e:
            self.log_error(f"Error optimizing route: {str(e)}")
            return self._empty_route_optimization()

    def _empty_route_optimization(self) -> Dict[str, Any]:
        """Create empty route optimization on error"""
        return {
            'primary_route': None,
            'alternative_routes': [],
            'eta_minutes': None,
            'recommendations': ['Route optimization failed'],
            'error': 'Optimization failed'
        }

    # ============================================
    # FULL DISPATCH PREDICTION PIPELINE
    # ============================================

    def predict_dispatch(
        self,
        patient_lat: float,
        patient_lon: float,
        description: str,
        vital_signs: Optional[Dict] = None,
        age: Optional[int] = None,
        required_ambulance_type: Optional[str] = None,
        destination_lat: Optional[float] = None,
        destination_lon: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Full dispatch prediction pipeline

        Orchestrates:
        1. Severity prediction
        2. Ambulance selection
        3. Route optimization
        4. ETA prediction

        Args:
            patient_lat, patient_lon: Patient location
            description: Patient symptoms
            vital_signs: Optional vital signs
            age: Optional age
            required_ambulance_type: Optional ambulance type requirement
            destination_lat, destination_lon: Optional hospital destination

        Returns:
            Complete dispatch prediction
        """
        try:
            pipeline_start = time.time()

            result = {
                'timestamp': datetime.utcnow().isoformat(),
                'patient_location': {
                    'latitude': patient_lat,
                    'longitude': patient_lon
                }
            }

            # Step 1: Predict severity
            severity_pred = self.predict_severity(description, vital_signs, age)
            result['severity'] = severity_pred
            severity_level = severity_pred.get('level', 3)

            # Step 2: Select ambulance
            ambulance_sel = self.select_ambulance(
                patient_lat,
                patient_lon,
                severity_level,
                required_ambulance_type
            )
            result['ambulance_selection'] = ambulance_sel

            # Step 3: Optimize route (if we have ambulance and destination)
            if ambulance_sel.get('ambulance_id') and destination_lat and destination_lon:
                route_opt = self.optimize_route(
                    patient_lat,
                    patient_lon,
                    destination_lat,
                    destination_lon
                )
                result['route'] = route_opt

                # Step 4: ETA prediction
                eta_pred = self.predict_eta(
                    patient_lat,
                    patient_lon,
                    destination_lat,
                    destination_lon
                )
                result['eta'] = eta_pred

            # Calculate total pipeline time
            total_ms = (time.time() - pipeline_start) * 1000
            result['pipeline_time_ms'] = round(total_ms, 2)

            self.log_info(f"Dispatch prediction completed in {total_ms:.2f}ms")

            return result

        except Exception as e:
            self.log_error(f"Error in dispatch prediction pipeline: {str(e)}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    # ============================================
    # BATCH PREDICTIONS
    # ============================================

    def predict_severity_batch(
        self,
        descriptions: List[str],
        vital_signs_list: Optional[List[Dict]] = None,
        ages: Optional[List[int]] = None
    ) -> List[Dict]:
        """
        Predict severity for multiple cases

        Args:
            descriptions: List of descriptions
            vital_signs_list: List of vital signs dicts
            ages: List of ages

        Returns:
            List of predictions
        """
        try:
            predictions = []

            for i, description in enumerate(descriptions):
                vital_signs = vital_signs_list[i] if vital_signs_list and i < len(vital_signs_list) else None
                age = ages[i] if ages and i < len(ages) else None

                pred = self.predict_severity(description, vital_signs, age)
                predictions.append(pred)

            self.log_info(f"Batch severity prediction: {len(predictions)} cases")
            return predictions

        except Exception as e:
            self.log_error(f"Error in batch severity prediction: {str(e)}")
            return []

    def predict_eta_batch(
        self,
        routes: List[Dict[str, float]]
    ) -> List[Dict]:
        """
        Predict ETA for multiple routes

        Args:
            routes: List of route dictionaries with:
                - origin_lat, origin_lon
                - destination_lat, destination_lon
                - traffic_level (optional)
                - time_of_day (optional)

        Returns:
            List of ETA predictions
        """
        try:
            predictions = []

            for route in routes:
                pred = self.predict_eta(
                    route['origin_lat'],
                    route['origin_lon'],
                    route['destination_lat'],
                    route['destination_lon'],
                    traffic_level=route.get('traffic_level', 1),
                    time_of_day=route.get('time_of_day')
                )
                predictions.append(pred)

            self.log_info(f"Batch ETA prediction: {len(predictions)} routes")
            return predictions

        except Exception as e:
            self.log_error(f"Error in batch ETA prediction: {str(e)}")
            return []

    # ============================================
    # RESULT CACHING
    # ============================================

    def get_cached_prediction(self, cache_key: str) -> Optional[Dict]:
        """
        Get cached prediction

        Args:
            cache_key: Cache key

        Returns:
            Cached prediction or None
        """
        try:
            return self.cache_repo.get(f"prediction:{cache_key}")

        except Exception as e:
            self.log_warning(f"Cache get error: {str(e)}")
            return None

    def cache_prediction(
        self,
        cache_key: str,
        prediction: Dict,
        ttl: int = 300
    ) -> bool:
        """
        Cache prediction result

        Args:
            cache_key: Cache key
            prediction: Prediction result
            ttl: Time to live in seconds

        Returns:
            True if cached
        """
        try:
            return self.cache_repo.set(
                f"prediction:{cache_key}",
                prediction,
                ttl=ttl
            )

        except Exception as e:
            self.log_warning(f"Cache set error: {str(e)}")
            return False
