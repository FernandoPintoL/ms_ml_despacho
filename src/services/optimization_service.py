"""
Optimization Service
Handles route and dispatch optimization
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from ..config.logger import LoggerMixin
from ..repositories import (
    DispatchRepository, AmbulanceRepository, FeatureEngineer, CacheRepository
)
from .prediction_service import PredictionService


class OptimizationService(LoggerMixin):
    """
    Service for optimization operations

    Provides:
    - Route optimization
    - Dispatch optimization
    - Multi-objective optimization
    - Alternative scenario generation
    """

    def __init__(
        self,
        prediction_service: PredictionService,
        dispatch_repo: DispatchRepository,
        ambulance_repo: AmbulanceRepository,
        cache_repo: CacheRepository
    ):
        """
        Initialize Optimization Service

        Args:
            prediction_service: PredictionService instance
            dispatch_repo: DispatchRepository instance
            ambulance_repo: AmbulanceRepository instance
            cache_repo: CacheRepository instance
        """
        self.prediction_service = prediction_service
        self.dispatch_repo = dispatch_repo
        self.ambulance_repo = ambulance_repo
        self.cache_repo = cache_repo
        self.engineer = FeatureEngineer()
        self.log_info("Initialized OptimizationService")

    # ============================================
    # DISPATCH OPTIMIZATION
    # ============================================

    def optimize_dispatch(
        self,
        dispatch_id: int,
        patient_lat: float,
        patient_lon: float,
        description: str,
        severity_level: int,
        destination_lat: Optional[float] = None,
        destination_lon: Optional[float] = None,
        required_ambulance_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Optimize entire dispatch operation

        Args:
            dispatch_id: Dispatch ID
            patient_lat, patient_lon: Patient location
            description: Patient symptoms
            severity_level: Case severity
            destination_lat, destination_lon: Hospital destination
            required_ambulance_type: Required ambulance type

        Returns:
            Optimized dispatch plan
        """
        try:
            self.log_info(f"Optimizing dispatch {dispatch_id}")

            # Get full predictions
            dispatch_pred = self.prediction_service.predict_dispatch(
                patient_lat,
                patient_lon,
                description,
                required_ambulance_type=required_ambulance_type,
                destination_lat=destination_lat,
                destination_lon=destination_lon
            )

            if 'error' in dispatch_pred:
                self.log_error(f"Prediction failed: {dispatch_pred['error']}")
                return {'error': 'Optimization failed'}

            # Extract results
            ambulance_sel = dispatch_pred.get('ambulance_selection', {})
            route_opt = dispatch_pred.get('route', {})
            eta_pred = dispatch_pred.get('eta', {})
            severity_pred = dispatch_pred.get('severity', {})

            # Build optimized plan
            plan = {
                'dispatch_id': dispatch_id,
                'timestamp': datetime.utcnow().isoformat(),
                'patient_location': {
                    'latitude': patient_lat,
                    'longitude': patient_lon
                },
                'severity': {
                    'level': severity_pred.get('level'),
                    'category': severity_pred.get('category'),
                    'confidence': severity_pred.get('confidence')
                },
                'ambulance': {
                    'id': ambulance_sel.get('ambulance_id'),
                    'confidence': ambulance_sel.get('confidence'),
                    'distance_km': ambulance_sel.get('distance_km'),
                    'estimated_arrival': ambulance_sel.get('estimated_arrival')
                },
                'route': {
                    'primary': route_opt.get('primary_route'),
                    'alternatives': route_opt.get('alternative_routes'),
                    'recommendations': route_opt.get('recommendations')
                },
                'eta': {
                    'estimated_minutes': eta_pred.get('estimated_minutes'),
                    'optimistic': eta_pred.get('eta_minutes_optimistic'),
                    'pessimistic': eta_pred.get('eta_minutes_pessimistic'),
                    'confidence': eta_pred.get('confidence')
                },
                'status': 'optimized'
            }

            # Cache the plan
            cache_key = f"dispatch_plan:{dispatch_id}"
            self.cache_repo.set(cache_key, plan, ttl=1800)  # 30 min cache

            self.log_info(f"Dispatch {dispatch_id} optimized successfully")
            return plan

        except Exception as e:
            self.log_error(f"Error optimizing dispatch: {str(e)}")
            return {'error': str(e)}

    # ============================================
    # MULTI-AMBULANCE OPTIMIZATION
    # ============================================

    def optimize_multiple_dispatches(
        self,
        dispatches: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict]]:
        """
        Optimize multiple dispatches simultaneously

        Considers:
        - Ambulance availability
        - Geographic clustering
        - Load balancing

        Args:
            dispatches: List of dispatch dictionaries

        Returns:
            Optimized assignments
        """
        try:
            self.log_info(f"Optimizing {len(dispatches)} dispatches")

            # Get available ambulances
            available = self.ambulance_repo.get_available_ambulances()

            if not available:
                self.log_warning("No available ambulances for optimization")
                return {'error': 'No available ambulances'}

            # Sort dispatches by severity (handle critical first)
            sorted_dispatches = sorted(
                dispatches,
                key=lambda d: d.get('severity_level', 3)
            )

            assignments = []
            used_ambulances = set()

            # Assign ambulances greedily by severity
            for dispatch in sorted_dispatches:
                best_ambulance = None
                best_score = -1

                for ambulance in available:
                    if ambulance['id'] in used_ambulances:
                        continue

                    # Calculate score
                    distance = self.engineer.calculate_distance(
                        dispatch['patient_lat'],
                        dispatch['patient_lon'],
                        ambulance['current_lat'],
                        ambulance['current_lon']
                    )

                    # Inverse of distance (closer is better)
                    distance_score = 1 / (distance + 1)

                    # Type match bonus
                    type_match = 1.0 if ambulance.get('type') == dispatch.get('required_type') else 0.5

                    # Severity adjustment
                    severity_bonus = 1 + (dispatch.get('severity_level', 3) / 5)

                    score = distance_score * type_match * severity_bonus

                    if score > best_score:
                        best_score = score
                        best_ambulance = ambulance

                if best_ambulance:
                    used_ambulances.add(best_ambulance['id'])
                    assignments.append({
                        'dispatch_id': dispatch['id'],
                        'ambulance_id': best_ambulance['id'],
                        'dispatch_severity': dispatch.get('severity_level'),
                        'distance_km': self.engineer.calculate_distance(
                            dispatch['patient_lat'],
                            dispatch['patient_lon'],
                            best_ambulance['current_lat'],
                            best_ambulance['current_lon']
                        )
                    })

            self.log_info(f"Assigned {len(assignments)} of {len(dispatches)} dispatches")
            return {
                'assignments': assignments,
                'unassigned_count': len(dispatches) - len(assignments)
            }

        except Exception as e:
            self.log_error(f"Error optimizing multiple dispatches: {str(e)}")
            return {'error': str(e)}

    # ============================================
    # ALTERNATIVE SCENARIOS
    # ============================================

    def generate_alternatives(
        self,
        dispatch_id: int,
        patient_lat: float,
        patient_lon: float,
        destination_lat: float,
        destination_lon: float,
        num_scenarios: int = 3
    ) -> Dict[str, List[Dict]]:
        """
        Generate alternative dispatch scenarios

        Args:
            dispatch_id: Dispatch ID
            patient_lat, patient_lon: Patient location
            destination_lat, destination_lon: Destination
            num_scenarios: Number of scenarios to generate

        Returns:
            Alternative scenarios
        """
        try:
            self.log_info(f"Generating {num_scenarios} alternative scenarios for dispatch {dispatch_id}")

            scenarios = []

            # Scenario 1: Normal (current traffic)
            normal_route = self.prediction_service.optimize_route(
                patient_lat, patient_lon,
                destination_lat, destination_lon,
                traffic_level=2,  # Moderate traffic
                num_alternatives=0
            )
            scenarios.append({
                'scenario': 'normal_traffic',
                'traffic_level': 2,
                'eta_minutes': normal_route.get('eta_minutes'),
                'route': normal_route.get('primary_route')
            })

            # Scenario 2: Heavy traffic
            if num_scenarios > 1:
                heavy_route = self.prediction_service.optimize_route(
                    patient_lat, patient_lon,
                    destination_lat, destination_lon,
                    traffic_level=4,  # Heavy traffic
                    num_alternatives=0
                )
                scenarios.append({
                    'scenario': 'heavy_traffic',
                    'traffic_level': 4,
                    'eta_minutes': heavy_route.get('eta_minutes'),
                    'route': heavy_route.get('primary_route')
                })

            # Scenario 3: Light traffic
            if num_scenarios > 2:
                light_route = self.prediction_service.optimize_route(
                    patient_lat, patient_lon,
                    destination_lat, destination_lon,
                    traffic_level=1,  # Light traffic
                    num_alternatives=0
                )
                scenarios.append({
                    'scenario': 'light_traffic',
                    'traffic_level': 1,
                    'eta_minutes': light_route.get('eta_minutes'),
                    'route': light_route.get('primary_route')
                })

            # Scenario 4: Optimal path (if available)
            if num_scenarios > 3:
                scenarios.append({
                    'scenario': 'route_A_alternative',
                    'description': 'Use main highway route',
                    'advantages': ['Faster on light traffic', 'Well-known route'],
                    'disadvantages': ['Congestion during peak hours']
                })

            return {
                'dispatch_id': dispatch_id,
                'scenarios': scenarios,
                'recommended': scenarios[0] if scenarios else None
            }

        except Exception as e:
            self.log_error(f"Error generating alternatives: {str(e)}")
            return {'error': str(e)}

    # ============================================
    # REAL-TIME OPTIMIZATION
    # ============================================

    def reoptimize_active_dispatch(
        self,
        dispatch_id: int,
        current_traffic_level: int,
        current_ambulance_lat: Optional[float] = None,
        current_ambulance_lon: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Reoptimize active dispatch with current conditions

        Args:
            dispatch_id: Dispatch ID
            current_traffic_level: Current traffic level (0-5)
            current_ambulance_lat: Current ambulance latitude
            current_ambulance_lon: Current ambulance longitude

        Returns:
            Updated optimization
        """
        try:
            # Get dispatch info
            dispatch = self.dispatch_repo.get_dispatch(dispatch_id)

            if not dispatch:
                self.log_error(f"Dispatch not found: {dispatch_id}")
                return {'error': 'Dispatch not found'}

            # Use current ambulance location if provided
            if current_ambulance_lat is None:
                ambulance_id = dispatch.get('assigned_ambulance_id')
                if ambulance_id:
                    ambulance = self.ambulance_repo.get_ambulance(ambulance_id)
                    current_ambulance_lat = ambulance.get('current_lat')
                    current_ambulance_lon = ambulance.get('current_lon')

            if not current_ambulance_lat:
                return {'error': 'Ambulance location unknown'}

            # Predict new ETA with current traffic
            new_eta = self.prediction_service.predict_eta(
                current_ambulance_lat,
                current_ambulance_lon,
                dispatch.get('destination_lat', 0),
                dispatch.get('destination_lon', 0),
                traffic_level=current_traffic_level,
                time_of_day=datetime.utcnow().hour
            )

            # Optimize new route
            new_route = self.prediction_service.optimize_route(
                current_ambulance_lat,
                current_ambulance_lon,
                dispatch.get('destination_lat', 0),
                dispatch.get('destination_lon', 0),
                traffic_level=current_traffic_level,
                time_of_day=datetime.utcnow().hour
            )

            result = {
                'dispatch_id': dispatch_id,
                'reoptimized_at': datetime.utcnow().isoformat(),
                'current_traffic_level': current_traffic_level,
                'updated_eta': new_eta.get('estimated_minutes'),
                'updated_route': new_route.get('primary_route'),
                'recommendations': new_route.get('recommendations'),
                'status': 'reoptimized'
            }

            # Cache update
            self.cache_repo.set(f"reoptimization:{dispatch_id}", result, ttl=300)

            self.log_info(f"Dispatch {dispatch_id} reoptimized with new ETA: {result['updated_eta']} min")
            return result

        except Exception as e:
            self.log_error(f"Error reoptimizing dispatch: {str(e)}")
            return {'error': str(e)}

    # ============================================
    # PERFORMANCE METRICS
    # ============================================

    def get_optimization_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get optimization service metrics

        Args:
            hours: Look back how many hours

        Returns:
            Performance metrics
        """
        try:
            # Get dispatch statistics
            stats = self.dispatch_repo.get_dispatch_statistics(hours)

            # Get ambulance stats
            fleet_status = self.ambulance_repo.get_fleet_status()

            metrics = {
                'period_hours': hours,
                'timestamp': datetime.utcnow().isoformat(),
                'dispatch_stats': stats,
                'fleet_status': fleet_status,
                'optimization_efficiency': self._calculate_efficiency(stats, fleet_status)
            }

            return metrics

        except Exception as e:
            self.log_error(f"Error getting optimization metrics: {str(e)}")
            return {'error': str(e)}

    def _calculate_efficiency(self, stats: Dict, fleet: Dict) -> float:
        """Calculate optimization efficiency score"""
        try:
            if not stats or not fleet:
                return 0.0

            # Calculate based on multiple factors
            completion_rate = stats.get('completion_rate', 0)  # 0-1
            availability = fleet.get('availability_percent', 0) / 100  # 0-1

            # Weight completion rate more heavily
            efficiency = (completion_rate * 0.7) + (availability * 0.3)

            return round(efficiency, 2)

        except Exception:
            return 0.0
