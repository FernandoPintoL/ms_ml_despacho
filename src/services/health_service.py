"""
Health Service
System health monitoring and diagnostics
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from ..config.logger import LoggerMixin
from ..repositories import ModelRepository, CacheRepository, DispatchRepository, AmbulanceRepository
from .model_manager import ModelManager


class HealthService(LoggerMixin):
    """
    Service for system health monitoring

    Provides:
    - System health checks
    - Component diagnostics
    - Performance metrics
    - Alert detection
    """

    def __init__(
        self,
        model_manager: ModelManager,
        model_repo: ModelRepository,
        cache_repo: CacheRepository,
        dispatch_repo: DispatchRepository,
        ambulance_repo: AmbulanceRepository
    ):
        """
        Initialize Health Service

        Args:
            model_manager: ModelManager instance
            model_repo: ModelRepository instance
            cache_repo: CacheRepository instance
            dispatch_repo: DispatchRepository instance
            ambulance_repo: AmbulanceRepository instance
        """
        self.model_manager = model_manager
        self.model_repo = model_repo
        self.cache_repo = cache_repo
        self.dispatch_repo = dispatch_repo
        self.ambulance_repo = ambulance_repo
        self.last_check = None
        self.health_status = 'unknown'
        self.log_info("Initialized HealthService")

    # ============================================
    # COMPREHENSIVE HEALTH CHECKS
    # ============================================

    def check_system_health(self) -> Dict[str, Any]:
        """
        Comprehensive system health check

        Returns:
            Health status with component details
        """
        try:
            self.log_debug("Running system health check")

            health = {
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'healthy',
                'components': {}
            }

            # Check each component
            model_health = self.check_models_health()
            health['components']['models'] = model_health
            if not model_health['healthy']:
                health['status'] = 'degraded'

            cache_health = self.check_cache_health()
            health['components']['cache'] = cache_health
            if not cache_health['healthy']:
                health['status'] = 'degraded'

            database_health = self.check_database_health()
            health['components']['database'] = database_health
            if not database_health['healthy']:
                health['status'] = 'degraded'

            service_health = self.check_service_health()
            health['components']['services'] = service_health
            if not service_health['healthy']:
                health['status'] = 'degraded'

            # Store for tracking
            self.last_check = datetime.utcnow()
            self.health_status = health['status']

            self.log_info(f"Health check complete: {health['status']}")
            return health

        except Exception as e:
            self.log_error(f"Error checking health: {str(e)}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'unhealthy',
                'error': str(e)
            }

    # ============================================
    # COMPONENT HEALTH CHECKS
    # ============================================

    def check_models_health(self) -> Dict[str, Any]:
        """
        Check ML models health

        Returns:
            Model health status
        """
        try:
            status = self.model_manager.health_check()

            models_loaded = sum(1 for v in status.get('models', {}).values() if v.get('status') == 'loaded')
            total_models = len(status.get('models', {}))

            health = {
                'healthy': models_loaded == total_models,
                'models_loaded': models_loaded,
                'models_total': total_models,
                'models': status.get('models', {}),
                'timestamp': datetime.utcnow().isoformat()
            }

            # Check model performance
            for model_name in ['eta', 'severity', 'ambulance', 'route']:
                perf = self.model_manager.get_model_performance(model_name, hours=1)
                if perf:
                    avg_latency = perf.get('avg_prediction_time', 0)
                    if avg_latency > 500:  # > 500ms is slow
                        health['healthy'] = False
                        health['warning'] = f"{model_name} latency high: {avg_latency}ms"

            return health

        except Exception as e:
            self.log_error(f"Error checking models health: {str(e)}")
            return {
                'healthy': False,
                'error': str(e)
            }

    def check_cache_health(self) -> Dict[str, Any]:
        """
        Check Redis cache health

        Returns:
            Cache health status
        """
        try:
            stats = self.cache_repo.get_cache_stats()

            healthy = (
                stats.get('used_memory_bytes', 0) < 1e10 and  # < 10GB
                stats.get('evicted_keys', 0) < 1000  # < 1000 evicted keys
            )

            return {
                'healthy': healthy,
                'used_memory': stats.get('used_memory', 'N/A'),
                'peak_memory': stats.get('peak_memory', 'N/A'),
                'fragmentation_ratio': stats.get('memory_fragmentation', 0),
                'total_keys': stats.get('total_keys', 0),
                'evicted_keys': stats.get('evicted_keys', 0),
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.log_error(f"Error checking cache health: {str(e)}")
            return {
                'healthy': False,
                'error': str(e)
            }

    def check_database_health(self) -> Dict[str, Any]:
        """
        Check database health

        Returns:
            Database health status
        """
        try:
            # Try to get basic stats
            dispatch_count = self.dispatch_repo.count('dispatches')
            ambulance_count = self.ambulance_repo.count('ambulances')

            healthy = dispatch_count >= 0 and ambulance_count >= 0

            return {
                'healthy': healthy,
                'dispatches': dispatch_count,
                'ambulances': ambulance_count,
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.log_error(f"Error checking database health: {str(e)}")
            return {
                'healthy': False,
                'error': str(e)
            }

    def check_service_health(self) -> Dict[str, Any]:
        """
        Check service operations health

        Returns:
            Service health status
        """
        try:
            # Check recent dispatch statistics
            stats = self.dispatch_repo.get_dispatch_statistics(hours=1)

            # Check if system is processing dispatches
            total_dispatches = stats.get('total', 0)
            completion_rate = stats.get('completion_rate', 0)

            # System is healthy if processing dispatches and completing them
            healthy = total_dispatches > 0 and completion_rate > 0.5  # > 50% completion

            return {
                'healthy': healthy,
                'dispatches_last_hour': total_dispatches,
                'completion_rate': completion_rate,
                'pending_count': stats.get('pending_count', 0),
                'in_transit_count': stats.get('in_transit_count', 0),
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.log_error(f"Error checking service health: {str(e)}")
            return {
                'healthy': False,
                'error': str(e)
            }

    # ============================================
    # DIAGNOSTIC REPORTS
    # ============================================

    def generate_diagnostic_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive diagnostic report

        Returns:
            Full diagnostic information
        """
        try:
            report = {
                'generated_at': datetime.utcnow().isoformat(),
                'system_health': self.check_system_health(),
                'model_status': self.model_manager.get_all_models_status(),
                'recent_performance': self._get_recent_performance(),
                'resource_usage': self.cache_repo.get_cache_stats(),
                'system_alerts': self._check_for_alerts()
            }

            return report

        except Exception as e:
            self.log_error(f"Error generating diagnostic report: {str(e)}")
            return {'error': str(e)}

    def _get_recent_performance(self) -> Dict[str, Any]:
        """Get recent performance metrics"""
        try:
            performance = {}

            for model_name in ['eta', 'severity', 'ambulance', 'route']:
                perf = self.model_manager.get_model_performance(model_name, hours=1)
                if perf:
                    performance[model_name] = {
                        'total_predictions': perf.get('total_predictions', 0),
                        'avg_latency_ms': perf.get('avg_prediction_time', 0),
                        'avg_confidence': perf.get('avg_confidence', 0)
                    }

            return performance

        except Exception:
            return {}

    def _check_for_alerts(self) -> list:
        """Check for system alerts"""
        try:
            alerts = []

            # Check for slow models
            for model_name in ['eta', 'severity', 'ambulance', 'route']:
                perf = self.model_manager.get_model_performance(model_name, hours=1)
                if perf and perf.get('avg_prediction_time', 0) > 500:
                    alerts.append({
                        'severity': 'warning',
                        'type': 'slow_model',
                        'message': f"{model_name} model latency: {perf.get('avg_prediction_time')}ms"
                    })

            # Check for low cache efficiency
            cache_stats = self.cache_repo.get_cache_stats()
            if cache_stats.get('evicted_keys', 0) > 500:
                alerts.append({
                    'severity': 'warning',
                    'type': 'cache_eviction',
                    'message': f"High cache eviction: {cache_stats.get('evicted_keys')} keys"
                })

            # Check for pending dispatches
            dispatch_stats = self.dispatch_repo.get_dispatch_statistics(hours=1)
            if dispatch_stats.get('pending_count', 0) > 100:
                alerts.append({
                    'severity': 'warning',
                    'type': 'pending_dispatches',
                    'message': f"High pending dispatches: {dispatch_stats.get('pending_count')}"
                })

            return alerts

        except Exception as e:
            self.log_warning(f"Error checking for alerts: {str(e)}")
            return []

    # ============================================
    # STATUS TRACKING
    # ============================================

    def get_uptime(self) -> Dict[str, Any]:
        """
        Get service uptime information

        Returns:
            Uptime information
        """
        try:
            # This would track actual uptime if implemented with persistent storage
            return {
                'last_health_check': self.last_check.isoformat() if self.last_check else None,
                'current_status': self.health_status,
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.log_error(f"Error getting uptime: {str(e)}")
            return {'error': str(e)}

    def get_quick_status(self) -> Dict[str, Any]:
        """
        Get quick status summary

        Returns:
            Quick status
        """
        try:
            # Quick health without detailed checks
            models_ok = self.model_manager.health_check()['healthy']
            dispatch_stats = self.dispatch_repo.get_dispatch_statistics(hours=1)

            return {
                'status': 'healthy' if models_ok else 'degraded',
                'models': 'ok' if models_ok else 'degraded',
                'active_dispatches': dispatch_stats.get('in_transit_count', 0),
                'pending_dispatches': dispatch_stats.get('pending_count', 0),
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.log_error(f"Error getting quick status: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
