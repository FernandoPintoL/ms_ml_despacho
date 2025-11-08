"""
GraphQL Resolvers
Implementation of GraphQL queries, mutations, and subscriptions
"""

from typing import List, Optional
from datetime import datetime
import strawberry

from ..services import (
    ModelManager, PredictionService, TrainingService,
    OptimizationService, HealthService
)
from ..repositories import DispatchRepository, AmbulanceRepository, ModelRepository
from .schema import (
    Query, Mutation, Subscription,
    Dispatch, Ambulance, DispatchPrediction, DispatchStatistics,
    AmbulanceStats, FleetStatus, ModelStatus, AllModelsStatus, ModelVersion,
    ModelPerformance, SystemHealth, DiagnosticReport, SeverityPrediction,
    ETAPrediction, RouteOptimizationResult, AmbulanceSelectionResult,
    DispatchFeedback, Location, ComponentHealth, SystemAlert
)


class ResolversContext:
    """Context containing all service dependencies"""

    def __init__(
        self,
        model_manager: ModelManager,
        prediction_service: PredictionService,
        training_service: TrainingService,
        optimization_service: OptimizationService,
        health_service: HealthService,
        dispatch_repo: DispatchRepository,
        ambulance_repo: AmbulanceRepository,
        model_repo: ModelRepository
    ):
        self.model_manager = model_manager
        self.prediction_service = prediction_service
        self.training_service = training_service
        self.optimization_service = optimization_service
        self.health_service = health_service
        self.dispatch_repo = dispatch_repo
        self.ambulance_repo = ambulance_repo
        self.model_repo = model_repo


# ============================================
# QUERY RESOLVERS
# ============================================

def get_dispatch_resolver(ctx: ResolversContext, dispatch_id: int) -> Optional[Dispatch]:
    """Resolver for get_dispatch query"""
    try:
        dispatch_data = ctx.dispatch_repo.get_dispatch(dispatch_id)

        if not dispatch_data:
            return None

        return Dispatch(
            id=dispatch_data['id'],
            patient_name=dispatch_data['patient_name'],
            patient_age=dispatch_data['patient_age'],
            patient_location=Location(
                latitude=dispatch_data['patient_lat'],
                longitude=dispatch_data['patient_lon']
            ),
            description=dispatch_data['description'],
            severity_level=dispatch_data['severity_level'],
            status=dispatch_data['status'],
            assigned_ambulance_id=dispatch_data.get('assigned_ambulance_id'),
            hospital_id=dispatch_data.get('hospital_id'),
            created_at=str(dispatch_data.get('created_at', '')),
            updated_at=str(dispatch_data.get('updated_at', ''))
        )

    except Exception as e:
        print(f"Error getting dispatch: {str(e)}")
        return None


def list_dispatches_resolver(
    ctx: ResolversContext,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dispatch]:
    """Resolver for list_dispatches query"""
    try:
        if status:
            dispatches_data = ctx.dispatch_repo.get_dispatches_by_status(status, limit)
        else:
            dispatches_data = ctx.dispatch_repo.find_all('dispatches', limit, offset)

        result = []
        for d in dispatches_data:
            result.append(Dispatch(
                id=d['id'],
                patient_name=d['patient_name'],
                patient_age=d['patient_age'],
                patient_location=Location(
                    latitude=d['patient_lat'],
                    longitude=d['patient_lon']
                ),
                description=d['description'],
                severity_level=d['severity_level'],
                status=d['status'],
                assigned_ambulance_id=d.get('assigned_ambulance_id'),
                hospital_id=d.get('hospital_id'),
                created_at=str(d.get('created_at', '')),
                updated_at=str(d.get('updated_at', ''))
            ))

        return result

    except Exception as e:
        print(f"Error listing dispatches: {str(e)}")
        return []


def get_recent_dispatches_resolver(
    ctx: ResolversContext,
    hours: int = 24,
    limit: int = 20
) -> List[Dispatch]:
    """Resolver for get_recent_dispatches query"""
    try:
        dispatches_data = ctx.dispatch_repo.get_recent_dispatches(limit, hours)

        result = []
        for d in dispatches_data:
            result.append(Dispatch(
                id=d['id'],
                patient_name=d['patient_name'],
                patient_age=d['patient_age'],
                patient_location=Location(
                    latitude=d['patient_lat'],
                    longitude=d['patient_lon']
                ),
                description=d['description'],
                severity_level=d['severity_level'],
                status=d['status'],
                assigned_ambulance_id=d.get('assigned_ambulance_id'),
                hospital_id=d.get('hospital_id'),
                created_at=str(d.get('created_at', '')),
                updated_at=str(d.get('updated_at', ''))
            ))

        return result

    except Exception as e:
        print(f"Error getting recent dispatches: {str(e)}")
        return []


def dispatch_statistics_resolver(
    ctx: ResolversContext,
    hours: int = 24
) -> DispatchStatistics:
    """Resolver for dispatch_statistics query"""
    try:
        stats = ctx.dispatch_repo.get_dispatch_statistics(hours)

        return DispatchStatistics(
            total=int(stats.get('total', 0)),
            completion_rate=float(stats.get('completion_rate', 0)),
            critical_count=int(stats.get('critical_count', 0)),
            high_count=int(stats.get('high_count', 0)),
            medium_count=int(stats.get('medium_count', 0)),
            pending_count=int(stats.get('pending_count', 0)),
            in_transit_count=int(stats.get('in_transit_count', 0))
        )

    except Exception as e:
        print(f"Error getting dispatch statistics: {str(e)}")
        return DispatchStatistics(
            total=0, completion_rate=0, critical_count=0, high_count=0,
            medium_count=0, pending_count=0, in_transit_count=0
        )


def get_ambulance_resolver(ctx: ResolversContext, ambulance_id: int) -> Optional[Ambulance]:
    """Resolver for get_ambulance query"""
    try:
        amb_data = ctx.ambulance_repo.get_ambulance(ambulance_id)

        if not amb_data:
            return None

        return Ambulance(
            id=amb_data['id'],
            code=amb_data['code'],
            type=amb_data['type'],
            status=amb_data['status'],
            driver_name=amb_data['driver_name'],
            driver_phone=amb_data['driver_phone'],
            equipment_level=amb_data['equipment_level'],
            current_location=Location(
                latitude=amb_data['current_lat'],
                longitude=amb_data['current_lon']
            ),
            last_location_update=str(amb_data.get('last_location_update', '')),
            gps_accuracy=amb_data.get('gps_accuracy'),
            created_at=str(amb_data.get('created_at', '')),
            updated_at=str(amb_data.get('updated_at', ''))
        )

    except Exception as e:
        print(f"Error getting ambulance: {str(e)}")
        return None


def list_ambulances_resolver(
    ctx: ResolversContext,
    ambulance_type: Optional[str] = None,
    status: Optional[str] = None
) -> List[Ambulance]:
    """Resolver for list_ambulances query"""
    try:
        if ambulance_type:
            ambulances_data = ctx.ambulance_repo.get_available_ambulances(ambulance_type)
        else:
            ambulances_data = ctx.ambulance_repo.find_all('ambulances')

        # Filter by status if provided
        if status:
            ambulances_data = [a for a in ambulances_data if a['status'] == status]

        result = []
        for a in ambulances_data:
            result.append(Ambulance(
                id=a['id'],
                code=a['code'],
                type=a['type'],
                status=a['status'],
                driver_name=a['driver_name'],
                driver_phone=a['driver_phone'],
                equipment_level=a['equipment_level'],
                current_location=Location(
                    latitude=a['current_lat'],
                    longitude=a['current_lon']
                ),
                last_location_update=str(a.get('last_location_update', '')),
                gps_accuracy=a.get('gps_accuracy'),
                created_at=str(a.get('created_at', '')),
                updated_at=str(a.get('updated_at', ''))
            ))

        return result

    except Exception as e:
        print(f"Error listing ambulances: {str(e)}")
        return []


def get_available_ambulances_resolver(
    ctx: ResolversContext,
    latitude: float,
    longitude: float,
    radius_km: float = 10
) -> List[Ambulance]:
    """Resolver for get_available_ambulances query"""
    try:
        ambulances_data = ctx.ambulance_repo.get_available_ambulances_near(
            latitude, longitude, radius_km
        )

        result = []
        for a in ambulances_data:
            result.append(Ambulance(
                id=a['id'],
                code=a['code'],
                type=a['type'],
                status=a['status'],
                driver_name=a['driver_name'],
                driver_phone=a['driver_phone'],
                equipment_level=a['equipment_level'],
                current_location=Location(
                    latitude=a['current_lat'],
                    longitude=a['current_lon']
                ),
                last_location_update=str(a.get('last_location_update', '')),
                gps_accuracy=a.get('gps_accuracy'),
                created_at=str(a.get('created_at', '')),
                updated_at=str(a.get('updated_at', ''))
            ))

        return result

    except Exception as e:
        print(f"Error getting available ambulances: {str(e)}")
        return []


def fleet_status_resolver(ctx: ResolversContext) -> FleetStatus:
    """Resolver for fleet_status query"""
    try:
        status = ctx.ambulance_repo.get_fleet_status()

        return FleetStatus(
            total_ambulances=int(status.get('total_ambulances', 0)),
            available=int(status.get('available', 0)),
            in_transit=int(status.get('in_transit', 0)),
            at_hospital=int(status.get('at_hospital', 0)),
            maintenance=int(status.get('maintenance', 0)),
            availability_percent=float(status.get('availability_percent', 0))
        )

    except Exception as e:
        print(f"Error getting fleet status: {str(e)}")
        return FleetStatus(
            total_ambulances=0, available=0, in_transit=0,
            at_hospital=0, maintenance=0, availability_percent=0
        )


def ambulance_stats_resolver(
    ctx: ResolversContext,
    ambulance_id: int,
    days: int = 30
) -> AmbulanceStats:
    """Resolver for ambulance_stats query"""
    try:
        stats = ctx.ambulance_repo.get_ambulance_stats(ambulance_id, days)

        return AmbulanceStats(
            ambulance_id=ambulance_id,
            total_dispatches=int(stats.get('total_dispatches', 0)),
            completed_dispatches=int(stats.get('completed_dispatches', 0)),
            avg_rating=float(stats.get('avg_rating', 0)) if stats.get('avg_rating') else None,
            avg_response_time=float(stats.get('avg_response_time', 0)) if stats.get('avg_response_time') else None,
            high_ratings=int(stats.get('high_ratings', 0)),
            low_ratings=int(stats.get('low_ratings', 0))
        )

    except Exception as e:
        print(f"Error getting ambulance stats: {str(e)}")
        return AmbulanceStats(
            ambulance_id=ambulance_id, total_dispatches=0, completed_dispatches=0,
            avg_rating=None, avg_response_time=None, high_ratings=0, low_ratings=0
        )


def get_model_status_resolver(ctx: ResolversContext, model_name: str) -> ModelStatus:
    """Resolver for get_model_status query"""
    try:
        status_dict = ctx.model_manager.get_all_models_status()

        if model_name not in status_dict:
            return ModelStatus(
                model_name=model_name, is_loaded=False, version="",
                prediction_count=0, model_type="", training_samples=0
            )

        m = status_dict[model_name]
        return ModelStatus(
            model_name=model_name,
            is_loaded=m.get('is_loaded', False),
            version=m.get('version', ''),
            prediction_count=int(m.get('prediction_count', 0)),
            model_type=m.get('model_type', ''),
            training_samples=int(m.get('training_samples', 0))
        )

    except Exception as e:
        print(f"Error getting model status: {str(e)}")
        return ModelStatus(
            model_name=model_name, is_loaded=False, version="",
            prediction_count=0, model_type="", training_samples=0
        )


def all_models_status_resolver(ctx: ResolversContext) -> AllModelsStatus:
    """Resolver for all_models_status query"""
    try:
        status_dict = ctx.model_manager.get_all_models_status()

        def get_status(name):
            if name in status_dict:
                m = status_dict[name]
                return ModelStatus(
                    model_name=name,
                    is_loaded=m.get('is_loaded', False),
                    version=m.get('version', ''),
                    prediction_count=int(m.get('prediction_count', 0)),
                    model_type=m.get('model_type', ''),
                    training_samples=int(m.get('training_samples', 0))
                )
            return ModelStatus(
                model_name=name, is_loaded=False, version="",
                prediction_count=0, model_type="", training_samples=0
            )

        return AllModelsStatus(
            eta=get_status('eta'),
            severity=get_status('severity'),
            ambulance=get_status('ambulance'),
            route=get_status('route')
        )

    except Exception as e:
        print(f"Error getting all models status: {str(e)}")
        return AllModelsStatus(
            eta=ModelStatus("eta", False, "", 0, "", 0),
            severity=ModelStatus("severity", False, "", 0, "", 0),
            ambulance=ModelStatus("ambulance", False, "", 0, "", 0),
            route=ModelStatus("route", False, "", 0, "", 0)
        )


def model_versions_resolver(
    ctx: ResolversContext,
    model_name: str,
    limit: int = 10
) -> List[ModelVersion]:
    """Resolver for model_versions query"""
    try:
        versions = ctx.model_repo.get_model_versions(model_name, limit)

        result = []
        for v in versions:
            result.append(ModelVersion(
                id=v['id'],
                model_name=v['model_name'],
                version=v['version'],
                model_type=v['model_type'],
                training_samples=int(v.get('training_samples', 0)),
                is_active=bool(v.get('is_active', False)),
                created_at=str(v.get('created_at', '')),
                trained_at=str(v.get('training_date', ''))
            ))

        return result

    except Exception as e:
        print(f"Error getting model versions: {str(e)}")
        return []


def model_performance_resolver(
    ctx: ResolversContext,
    model_name: str,
    hours: int = 1
) -> ModelPerformance:
    """Resolver for model_performance query"""
    try:
        perf = ctx.model_manager.get_model_performance(model_name, hours)

        return ModelPerformance(
            model_name=model_name,
            total_predictions=int(perf.get('total_predictions', 0)),
            avg_prediction_time=float(perf.get('avg_prediction_time', 0)),
            avg_confidence=float(perf.get('avg_confidence', 0)),
            mae=float(perf.get('mae', 0)) if perf.get('mae') else None,
            rmse=float(perf.get('rmse', 0)) if perf.get('rmse') else None,
            accuracy=float(perf.get('accuracy', 0)) if perf.get('accuracy') else None
        )

    except Exception as e:
        print(f"Error getting model performance: {str(e)}")
        return ModelPerformance(
            model_name=model_name, total_predictions=0, avg_prediction_time=0,
            avg_confidence=0, mae=None, rmse=None, accuracy=None
        )


def predict_dispatch_resolver(
    ctx: ResolversContext,
    patient_lat: float,
    patient_lon: float,
    description: str,
    severity_level: int,
    destination_lat: Optional[float] = None,
    destination_lon: Optional[float] = None
) -> DispatchPrediction:
    """Resolver for predict_dispatch query"""
    try:
        prediction = ctx.prediction_service.predict_dispatch(
            patient_lat=patient_lat,
            patient_lon=patient_lon,
            description=description,
            severity_level=severity_level,
            destination_lat=destination_lat,
            destination_lon=destination_lon
        )

        # Build response (simplified)
        return DispatchPrediction(
            dispatch_id=None,
            timestamp=prediction.get('timestamp', datetime.utcnow().isoformat()),
            severity=SeverityPrediction(
                level=prediction.get('severity', {}).get('level', 3),
                category=prediction.get('severity', {}).get('category', 'Unknown'),
                confidence=prediction.get('severity', {}).get('confidence', 0),
                keywords_found=prediction.get('severity', {}).get('keywords_found', []),
                recommendation=prediction.get('severity', {}).get('recommendation', ''),
                severity_score=prediction.get('severity', {}).get('severity_score', 0)
            ),
            ambulance_selection=AmbulanceSelectionResult(
                ambulance_id=prediction.get('ambulance_selection', {}).get('ambulance_id'),
                confidence=prediction.get('ambulance_selection', {}).get('confidence', 0),
                distance_km=prediction.get('ambulance_selection', {}).get('distance_km', 0),
                estimated_arrival=prediction.get('ambulance_selection', {}).get('estimated_arrival'),
                total_score=prediction.get('ambulance_selection', {}).get('total_score', 0),
                ranking=[]
            ),
            route=None,  # Simplified
            eta=None,    # Simplified
            pipeline_time_ms=prediction.get('pipeline_time_ms', 0)
        )

    except Exception as e:
        print(f"Error predicting dispatch: {str(e)}")
        return DispatchPrediction(
            dispatch_id=None, timestamp=datetime.utcnow().isoformat(),
            severity=SeverityPrediction("", "", 0, [], "", 0),
            ambulance_selection=AmbulanceSelectionResult(None, 0, 0, None, 0, []),
            route=None, eta=None, pipeline_time_ms=0
        )


def system_health_resolver(ctx: ResolversContext) -> SystemHealth:
    """Resolver for system_health query"""
    try:
        health = ctx.health_service.check_system_health()

        components = health.get('components', {})

        return SystemHealth(
            status=health.get('status', 'unknown'),
            timestamp=health.get('timestamp', datetime.utcnow().isoformat()),
            models=ComponentHealth(
                component='models',
                healthy=components.get('models', {}).get('healthy', False),
                details=str(components.get('models', {}))
            ),
            cache=ComponentHealth(
                component='cache',
                healthy=components.get('cache', {}).get('healthy', False),
                details=str(components.get('cache', {}))
            ),
            database=ComponentHealth(
                component='database',
                healthy=components.get('database', {}).get('healthy', False),
                details=str(components.get('database', {}))
            ),
            services=ComponentHealth(
                component='services',
                healthy=components.get('services', {}).get('healthy', False),
                details=str(components.get('services', {}))
            )
        )

    except Exception as e:
        print(f"Error checking system health: {str(e)}")
        return SystemHealth(
            status='error', timestamp=datetime.utcnow().isoformat(),
            models=ComponentHealth('models', False, str(e)),
            cache=ComponentHealth('cache', False, str(e)),
            database=ComponentHealth('database', False, str(e)),
            services=ComponentHealth('services', False, str(e))
        )


def diagnostic_report_resolver(ctx: ResolversContext) -> DiagnosticReport:
    """Resolver for diagnostic_report query"""
    try:
        report = ctx.health_service.generate_diagnostic_report()

        health = report.get('system_health', {})

        return DiagnosticReport(
            generated_at=report.get('generated_at', datetime.utcnow().isoformat()),
            system_health=system_health_resolver(ctx),
            model_statuses=all_models_status_resolver(ctx),
            alerts=[],  # Simplified
            recent_dispatches=0,
            pending_dispatches=0
        )

    except Exception as e:
        print(f"Error generating diagnostic report: {str(e)}")
        return DiagnosticReport(
            generated_at=datetime.utcnow().isoformat(),
            system_health=SystemHealth(
                'error', datetime.utcnow().isoformat(),
                ComponentHealth('models', False, str(e)),
                ComponentHealth('cache', False, str(e)),
                ComponentHealth('database', False, str(e)),
                ComponentHealth('services', False, str(e))
            ),
            model_statuses=all_models_status_resolver(ctx),
            alerts=[],
            recent_dispatches=0,
            pending_dispatches=0
        )


# ============================================
# MUTATION RESOLVERS
# ============================================

def create_dispatch_resolver(
    ctx: ResolversContext,
    patient_name: str,
    patient_age: int,
    patient_lat: float,
    patient_lon: float,
    description: str,
    severity_level: int
) -> Dispatch:
    """Resolver for create_dispatch mutation"""
    try:
        dispatch_id = ctx.dispatch_repo.create_dispatch({
            'patient_name': patient_name,
            'patient_age': patient_age,
            'patient_lat': patient_lat,
            'patient_lon': patient_lon,
            'description': description,
            'severity_level': severity_level,
            'status': 'pending'
        })

        if dispatch_id:
            dispatch_data = ctx.dispatch_repo.get_dispatch(dispatch_id)
            return Dispatch(
                id=dispatch_data['id'],
                patient_name=dispatch_data['patient_name'],
                patient_age=dispatch_data['patient_age'],
                patient_location=Location(
                    latitude=dispatch_data['patient_lat'],
                    longitude=dispatch_data['patient_lon']
                ),
                description=dispatch_data['description'],
                severity_level=dispatch_data['severity_level'],
                status=dispatch_data['status'],
                assigned_ambulance_id=dispatch_data.get('assigned_ambulance_id'),
                hospital_id=dispatch_data.get('hospital_id'),
                created_at=str(dispatch_data.get('created_at', '')),
                updated_at=str(dispatch_data.get('updated_at', ''))
            )

        raise Exception("Failed to create dispatch")

    except Exception as e:
        print(f"Error creating dispatch: {str(e)}")
        raise


def update_dispatch_status_resolver(
    ctx: ResolversContext,
    dispatch_id: int,
    status: str
) -> Dispatch:
    """Resolver for update_dispatch_status mutation"""
    try:
        ctx.dispatch_repo.update_dispatch_status(dispatch_id, status)
        dispatch_data = ctx.dispatch_repo.get_dispatch(dispatch_id)

        return Dispatch(
            id=dispatch_data['id'],
            patient_name=dispatch_data['patient_name'],
            patient_age=dispatch_data['patient_age'],
            patient_location=Location(
                latitude=dispatch_data['patient_lat'],
                longitude=dispatch_data['patient_lon']
            ),
            description=dispatch_data['description'],
            severity_level=dispatch_data['severity_level'],
            status=dispatch_data['status'],
            assigned_ambulance_id=dispatch_data.get('assigned_ambulance_id'),
            hospital_id=dispatch_data.get('hospital_id'),
            created_at=str(dispatch_data.get('created_at', '')),
            updated_at=str(dispatch_data.get('updated_at', ''))
        )

    except Exception as e:
        print(f"Error updating dispatch status: {str(e)}")
        raise


def retrain_models_resolver(
    ctx: ResolversContext,
    days: int = 30,
    auto_activate: bool = False
) -> str:
    """Resolver for retrain_models mutation"""
    try:
        results = ctx.training_service.retrain_all_models(days, auto_activate)
        return f"Retraining completed: {len([r for r in results.values() if r.get('success')])} models trained"

    except Exception as e:
        print(f"Error retraining models: {str(e)}")
        raise


# Mapping of resolver functions to schema fields
QUERY_RESOLVERS = {
    'get_dispatch': get_dispatch_resolver,
    'list_dispatches': list_dispatches_resolver,
    'get_recent_dispatches': get_recent_dispatches_resolver,
    'dispatch_statistics': dispatch_statistics_resolver,
    'get_ambulance': get_ambulance_resolver,
    'list_ambulances': list_ambulances_resolver,
    'get_available_ambulances': get_available_ambulances_resolver,
    'fleet_status': fleet_status_resolver,
    'ambulance_stats': ambulance_stats_resolver,
    'get_model_status': get_model_status_resolver,
    'all_models_status': all_models_status_resolver,
    'model_versions': model_versions_resolver,
    'model_performance': model_performance_resolver,
    'predict_dispatch': predict_dispatch_resolver,
    'system_health': system_health_resolver,
    'diagnostic_report': diagnostic_report_resolver,
}

MUTATION_RESOLVERS = {
    'create_dispatch': create_dispatch_resolver,
    'update_dispatch_status': update_dispatch_status_resolver,
    'retrain_models': retrain_models_resolver,
}
