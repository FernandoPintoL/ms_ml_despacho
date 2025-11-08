"""
Pytest Configuration and Fixtures
Shared fixtures and configuration for all tests
"""

import pytest
import sys
import os
from datetime import datetime
from unittest.mock import Mock, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config.settings import TestingConfig
from src.main import create_app


# ============================================
# APP & CONFIG FIXTURES
# ============================================

@pytest.fixture(scope='session')
def app_config():
    """Get testing configuration"""
    return TestingConfig()


@pytest.fixture(scope='session')
def app(app_config):
    """Create Flask app for testing"""
    app = create_app(app_config)
    return app


@pytest.fixture
def client(app):
    """Get Flask test client"""
    return app.test_client()


@pytest.fixture
def app_context(app):
    """Get app context"""
    with app.app_context():
        yield app


# ============================================
# DATABASE & CACHE FIXTURES
# ============================================

@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    mock_conn = MagicMock()
    mock_conn.execute = MagicMock(return_value=[])
    return mock_conn


@pytest.fixture
def mock_redis_client():
    """Mock Redis client"""
    mock_redis = MagicMock()
    mock_redis.get = MagicMock(return_value=None)
    mock_redis.set = MagicMock(return_value=True)
    mock_redis.delete = MagicMock(return_value=1)
    mock_redis.scan = MagicMock(return_value=(0, []))
    return mock_redis


# ============================================
# REPOSITORY FIXTURES
# ============================================

@pytest.fixture
def dispatch_repo(mock_db_connection, mock_redis_client):
    """Get DispatchRepository"""
    from src.repositories import DispatchRepository
    return DispatchRepository(mock_db_connection, mock_redis_client)


@pytest.fixture
def ambulance_repo(mock_db_connection, mock_redis_client):
    """Get AmbulanceRepository"""
    from src.repositories import AmbulanceRepository
    return AmbulanceRepository(mock_db_connection, mock_redis_client)


@pytest.fixture
def model_repo(mock_db_connection, mock_redis_client, tmp_path):
    """Get ModelRepository"""
    from src.repositories import ModelRepository
    return ModelRepository(mock_db_connection, mock_redis_client, str(tmp_path))


@pytest.fixture
def cache_repo(mock_redis_client):
    """Get CacheRepository"""
    from src.repositories import CacheRepository
    return CacheRepository(mock_redis_client)


@pytest.fixture
def feature_engineer():
    """Get FeatureEngineer"""
    from src.repositories import FeatureEngineer
    return FeatureEngineer()


# ============================================
# SERVICE FIXTURES
# ============================================

@pytest.fixture
def model_manager(model_repo):
    """Get ModelManager"""
    from src.services import ModelManager
    return ModelManager(model_repo)


@pytest.fixture
def prediction_service(model_manager, dispatch_repo, ambulance_repo, model_repo, cache_repo):
    """Get PredictionService"""
    from src.services import PredictionService
    return PredictionService(model_manager, dispatch_repo, ambulance_repo, model_repo, cache_repo)


@pytest.fixture
def training_service(model_manager, dispatch_repo, model_repo, cache_repo):
    """Get TrainingService"""
    from src.services import TrainingService
    return TrainingService(model_manager, dispatch_repo, model_repo, cache_repo)


@pytest.fixture
def optimization_service(prediction_service, dispatch_repo, ambulance_repo, cache_repo):
    """Get OptimizationService"""
    from src.services import OptimizationService
    return OptimizationService(prediction_service, dispatch_repo, ambulance_repo, cache_repo)


@pytest.fixture
def health_service(model_manager, model_repo, cache_repo, dispatch_repo, ambulance_repo):
    """Get HealthService"""
    from src.services import HealthService
    return HealthService(model_manager, model_repo, cache_repo, dispatch_repo, ambulance_repo)


# ============================================
# MODEL FIXTURES
# ============================================

@pytest.fixture
def severity_model():
    """Get SeverityClassifier"""
    from src.models import SeverityClassifier
    return SeverityClassifier()


@pytest.fixture
def eta_model():
    """Get ETAModel"""
    from src.models import ETAModel
    return ETAModel()


@pytest.fixture
def ambulance_selector_model():
    """Get AmbulanceSelector"""
    from src.models import AmbulanceSelector
    return AmbulanceSelector()


@pytest.fixture
def route_optimizer_model():
    """Get RouteOptimizer"""
    from src.models import RouteOptimizer
    return RouteOptimizer()


# ============================================
# TEST DATA FIXTURES
# ============================================

@pytest.fixture
def sample_dispatch_data():
    """Sample dispatch data"""
    return {
        'id': 1,
        'patient_name': 'John Doe',
        'patient_age': 45,
        'patient_lat': 4.7110,
        'patient_lon': -74.0721,
        'description': 'Chest pain',
        'severity_level': 2,
        'status': 'pending',
        'assigned_ambulance_id': None,
        'hospital_id': None,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_ambulance_data():
    """Sample ambulance data"""
    return {
        'id': 5,
        'code': 'AMB-001',
        'type': 'advanced',
        'status': 'available',
        'driver_name': 'Carlos Martinez',
        'driver_phone': '3001234567',
        'equipment_level': 4,
        'current_lat': 4.7120,
        'current_lon': -74.0720,
        'last_location_update': datetime.utcnow().isoformat(),
        'gps_accuracy': 10.5,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_severity_features():
    """Sample features for severity prediction"""
    return {
        'has_critical_keywords': 1,
        'has_high_keywords': 0,
        'has_medium_keywords': 0,
        'description_length': 15,
        'heart_rate': 110,
        'abnormal_heart_rate': 1,
        'age': 55,
        'age_elderly': 1
    }


@pytest.fixture
def sample_eta_features():
    """Sample features for ETA prediction"""
    return {
        'distance_km': 2.5,
        'hour': 14,
        'day_of_week': 2,
        'is_weekend': 0,
        'is_rush_hour': 1,
        'traffic_level': 2,
        'traffic_numeric': 0.4
    }


@pytest.fixture
def sample_ambulance_features():
    """Sample features for ambulance selection"""
    return {
        'type_level': 2,
        'is_available': 1,
        'equipment_level': 4,
        'avg_response_time': 8,
        'experienced_driver': 1
    }


@pytest.fixture
def sample_route_features():
    """Sample features for route optimization"""
    return {
        'distance_km': 3.2,
        'bearing_degrees': 45,
        'hour': 14,
        'traffic_numeric': 0.4
    }


# ============================================
# CLEANUP FIXTURES
# ============================================

@pytest.fixture(autouse=True)
def cleanup():
    """Cleanup after each test"""
    yield
    # Cleanup code here if needed


# ============================================
# MARKERS
# ============================================

def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "e2e: mark test as end-to-end test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "api: mark test as API test")
    config.addinivalue_line("markers", "model: mark test as ML model test")
    config.addinivalue_line("markers", "repo: mark test as repository test")
    config.addinivalue_line("markers", "service: mark test as service test")
