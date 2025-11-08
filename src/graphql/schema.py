"""
GraphQL Schema Definition
Complete GraphQL API schema with queries, mutations, and subscriptions
"""

import strawberry
from typing import List, Optional, Dict, Any
from datetime import datetime


# ============================================
# SCALAR TYPES
# ============================================

@strawberry.type
class Location:
    """Geographic location"""
    latitude: float
    longitude: float


@strawberry.type
class SeverityPrediction:
    """Severity prediction result"""
    level: int
    category: str
    confidence: float
    keywords_found: List[str]
    recommendation: str
    severity_score: int


@strawberry.type
class ETAPrediction:
    """ETA prediction result"""
    estimated_minutes: int
    confidence: float
    lower_bound: int
    upper_bound: int
    traffic_level: int
    distance_km: float


@strawberry.type
class AmbulanceRanking:
    """Ambulance ranking in selection"""
    rank: int
    ambulance_id: int
    score: float
    distance_km: float


@strawberry.type
class AmbulanceSelectionResult:
    """Ambulance selection result"""
    ambulance_id: Optional[int]
    confidence: float
    distance_km: float
    estimated_arrival: Optional[int]
    total_score: float
    ranking: List[AmbulanceRanking]
    error: Optional[str] = None


@strawberry.type
class RouteSegment:
    """Route segment"""
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    sequence: int


@strawberry.type
class RouteInfo:
    """Route information"""
    type: str
    distance_km: float
    eta_minutes: int
    eta_optimistic: int
    eta_pessimistic: int
    instructions: List[str]
    segments: List[RouteSegment]


@strawberry.type
class RouteOptimizationResult:
    """Route optimization result"""
    primary_route: Optional[RouteInfo]
    alternative_routes: List[RouteInfo]
    eta_minutes: Optional[int]
    distance_km: float
    recommendations: List[str]
    estimated_congestion: str


@strawberry.type
class DispatchPrediction:
    """Complete dispatch prediction"""
    dispatch_id: Optional[int]
    timestamp: str
    severity: SeverityPrediction
    ambulance_selection: AmbulanceSelectionResult
    route: Optional[RouteOptimizationResult]
    eta: Optional[ETAPrediction]
    pipeline_time_ms: float


# ============================================
# DISPATCH TYPES
# ============================================

@strawberry.type
class Dispatch:
    """Dispatch record"""
    id: int
    patient_name: str
    patient_age: int
    patient_location: Location
    description: str
    severity_level: int
    status: str  # pending, assigned, in_transit, arrived, completed, cancelled
    assigned_ambulance_id: Optional[int]
    hospital_id: Optional[int]
    created_at: str
    updated_at: str


@strawberry.type
class DispatchWithPrediction:
    """Dispatch with prediction results"""
    dispatch: Dispatch
    prediction: DispatchPrediction


@strawberry.type
class DispatchStatistics:
    """Dispatch statistics"""
    total: int
    completion_rate: float
    critical_count: int
    high_count: int
    medium_count: int
    pending_count: int
    in_transit_count: int


@strawberry.type
class DispatchFeedback:
    """Dispatch feedback/rating"""
    dispatch_id: int
    rating: int  # 1-5
    comment: Optional[str]
    response_time_minutes: int
    patient_outcome: str


# ============================================
# AMBULANCE TYPES
# ============================================

@strawberry.type
class Ambulance:
    """Ambulance record"""
    id: int
    code: str
    type: str  # basic, advanced, mobile_icu
    status: str  # available, in_transit, at_hospital, maintenance
    driver_name: str
    driver_phone: str
    equipment_level: int  # 1-5
    current_location: Location
    last_location_update: str
    gps_accuracy: Optional[float]
    created_at: str
    updated_at: str


@strawberry.type
class AmbulanceStats:
    """Ambulance performance statistics"""
    ambulance_id: int
    total_dispatches: int
    completed_dispatches: int
    avg_rating: Optional[float]
    avg_response_time: Optional[float]
    high_ratings: int
    low_ratings: int


@strawberry.type
class AmbulanceLocationHistory:
    """Ambulance location history"""
    latitude: float
    longitude: float
    timestamp: str


@strawberry.type
class FleetStatus:
    """Fleet overall status"""
    total_ambulances: int
    available: int
    in_transit: int
    at_hospital: int
    maintenance: int
    availability_percent: float


# ============================================
# MODEL TYPES
# ============================================

@strawberry.type
class ModelVersion:
    """ML model version"""
    id: int
    model_name: str
    version: str
    model_type: str
    training_samples: int
    is_active: bool
    created_at: str
    trained_at: str


@strawberry.type
class ModelPerformance:
    """Model performance metrics"""
    model_name: str
    total_predictions: int
    avg_prediction_time: float
    avg_confidence: float
    mae: Optional[float]
    rmse: Optional[float]
    accuracy: Optional[float]


@strawberry.type
class ModelStatus:
    """ML model status"""
    model_name: str
    is_loaded: bool
    version: str
    prediction_count: int
    model_type: str
    training_samples: int


@strawberry.type
class AllModelsStatus:
    """Status of all ML models"""
    eta: ModelStatus
    severity: ModelStatus
    ambulance: ModelStatus
    route: ModelStatus


# ============================================
# HEALTH & MONITORING TYPES
# ============================================

@strawberry.type
class ComponentHealth:
    """Health status of a component"""
    component: str
    healthy: bool
    details: Optional[str]


@strawberry.type
class SystemHealth:
    """System health status"""
    status: str  # healthy, degraded, warning, unhealthy
    timestamp: str
    models: ComponentHealth
    cache: ComponentHealth
    database: ComponentHealth
    services: ComponentHealth


@strawberry.type
class SystemAlert:
    """System alert"""
    severity: str  # info, warning, error, critical
    type: str
    message: str
    timestamp: str


@strawberry.type
class DiagnosticReport:
    """Comprehensive diagnostic report"""
    generated_at: str
    system_health: SystemHealth
    model_statuses: AllModelsStatus
    alerts: List[SystemAlert]
    recent_dispatches: int
    pending_dispatches: int


# ============================================
# QUERIES
# ============================================

@strawberry.type
class Query:
    """GraphQL Queries"""

    @strawberry.field
    def get_dispatch(self, dispatch_id: int) -> Optional[Dispatch]:
        """Get dispatch by ID"""
        pass

    @strawberry.field
    def list_dispatches(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dispatch]:
        """List dispatches with optional filtering"""
        pass

    @strawberry.field
    def get_recent_dispatches(self, hours: int = 24, limit: int = 20) -> List[Dispatch]:
        """Get recent dispatches within specified hours"""
        pass

    @strawberry.field
    def dispatch_statistics(self, hours: int = 24) -> DispatchStatistics:
        """Get dispatch statistics for time period"""
        pass

    @strawberry.field
    def get_ambulance(self, ambulance_id: int) -> Optional[Ambulance]:
        """Get ambulance by ID"""
        pass

    @strawberry.field
    def list_ambulances(
        self,
        ambulance_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Ambulance]:
        """List ambulances with optional filtering"""
        pass

    @strawberry.field
    def get_available_ambulances(self, latitude: float, longitude: float, radius_km: float = 10) -> List[Ambulance]:
        """Get available ambulances near location"""
        pass

    @strawberry.field
    def fleet_status(self) -> FleetStatus:
        """Get overall fleet status"""
        pass

    @strawberry.field
    def ambulance_stats(self, ambulance_id: int, days: int = 30) -> AmbulanceStats:
        """Get ambulance performance statistics"""
        pass

    @strawberry.field
    def get_model_status(self, model_name: str) -> ModelStatus:
        """Get status of specific model"""
        pass

    @strawberry.field
    def all_models_status(self) -> AllModelsStatus:
        """Get status of all ML models"""
        pass

    @strawberry.field
    def model_versions(self, model_name: str, limit: int = 10) -> List[ModelVersion]:
        """Get versions of a model"""
        pass

    @strawberry.field
    def model_performance(self, model_name: str, hours: int = 1) -> ModelPerformance:
        """Get model performance metrics"""
        pass

    @strawberry.field
    def predict_dispatch(
        self,
        patient_lat: float,
        patient_lon: float,
        description: str,
        severity_level: int,
        destination_lat: Optional[float] = None,
        destination_lon: Optional[float] = None
    ) -> DispatchPrediction:
        """Get predictions for dispatch"""
        pass

    @strawberry.field
    def predict_severity(
        self,
        description: str,
        age: Optional[int] = None
    ) -> SeverityPrediction:
        """Predict severity level from symptoms"""
        pass

    @strawberry.field
    def predict_eta(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
        traffic_level: int = 1
    ) -> ETAPrediction:
        """Predict ETA for route"""
        pass

    @strawberry.field
    def system_health(self) -> SystemHealth:
        """Get system health status"""
        pass

    @strawberry.field
    def diagnostic_report(self) -> DiagnosticReport:
        """Get comprehensive diagnostic report"""
        pass


# ============================================
# MUTATIONS
# ============================================

@strawberry.type
class Mutation:
    """GraphQL Mutations"""

    @strawberry.mutation
    def create_dispatch(
        self,
        patient_name: str,
        patient_age: int,
        patient_lat: float,
        patient_lon: float,
        description: str,
        severity_level: int
    ) -> Dispatch:
        """Create new dispatch"""
        pass

    @strawberry.mutation
    def update_dispatch_status(
        self,
        dispatch_id: int,
        status: str
    ) -> Dispatch:
        """Update dispatch status"""
        pass

    @strawberry.mutation
    def assign_ambulance(
        self,
        dispatch_id: int,
        ambulance_id: int
    ) -> Dispatch:
        """Assign ambulance to dispatch"""
        pass

    @strawberry.mutation
    def optimize_dispatch(self, dispatch_id: int) -> DispatchPrediction:
        """Optimize dispatch with predictions"""
        pass

    @strawberry.mutation
    def add_dispatch_feedback(
        self,
        dispatch_id: int,
        rating: int,
        comment: Optional[str] = None,
        response_time_minutes: int = 0,
        patient_outcome: str = "stable"
    ) -> DispatchFeedback:
        """Add feedback for completed dispatch"""
        pass

    @strawberry.mutation
    def update_ambulance_location(
        self,
        ambulance_id: int,
        latitude: float,
        longitude: float,
        accuracy: Optional[float] = None
    ) -> Ambulance:
        """Update ambulance GPS location"""
        pass

    @strawberry.mutation
    def set_ambulance_status(
        self,
        ambulance_id: int,
        status: str
    ) -> Ambulance:
        """Set ambulance status"""
        pass

    @strawberry.mutation
    def retrain_models(
        self,
        days: int = 30,
        auto_activate: bool = False
    ) -> str:
        """Trigger model retraining"""
        pass

    @strawberry.mutation
    def activate_model_version(
        self,
        model_name: str,
        version: str
    ) -> ModelVersion:
        """Activate specific model version"""
        pass


# ============================================
# SUBSCRIPTIONS
# ============================================

@strawberry.type
class Subscription:
    """GraphQL Subscriptions"""

    @strawberry.subscription
    async def dispatch_updates(self, dispatch_id: int):
        """Subscribe to dispatch status updates"""
        pass

    @strawberry.subscription
    async def ambulance_location_updates(self, ambulance_id: int):
        """Subscribe to ambulance location updates"""
        pass

    @strawberry.subscription
    async def system_health_updates(self):
        """Subscribe to system health updates"""
        pass


# ============================================
# SCHEMA
# ============================================

schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)
