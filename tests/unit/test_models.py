"""
Unit Tests for ML Models
Tests for severity, ETA, ambulance selector, and route optimizer models
"""

import pytest
import numpy as np
from datetime import datetime


# ============================================
# SEVERITY CLASSIFIER TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.model
class TestSeverityClassifier:
    """Test SeverityClassifier model"""

    def test_severity_prediction_critical(self, severity_model):
        """Test critical severity prediction"""
        features = {
            'description': 'Cardiac arrest, unconscious',
            'age': 60
        }

        result = severity_model.predict(features)

        assert result is not None
        assert 'level' in result
        assert 'confidence' in result
        assert result['level'] in [1, 2, 3, 4, 5]
        assert 0 <= result['confidence'] <= 1

    def test_severity_prediction_high(self, severity_model):
        """Test high severity prediction"""
        features = {
            'description': 'Chest pain and difficulty breathing',
            'age': 55
        }

        result = severity_model.predict(features)

        assert result['level'] in [1, 2, 3, 4, 5]
        assert result['confidence'] > 0

    def test_severity_prediction_medium(self, severity_model):
        """Test medium severity prediction"""
        features = {
            'description': 'Fever and nausea',
            'age': 35
        }

        result = severity_model.predict(features)

        assert result['level'] in [1, 2, 3, 4, 5]

    def test_severity_with_vital_signs(self, severity_model):
        """Test severity with vital signs"""
        features = {
            'description': 'Chest pain',
            'vital_signs': {
                'heart_rate': 120,
                'blood_pressure': '150/95'
            },
            'age': 50
        }

        result = severity_model.predict(features)

        assert result['level'] >= 2  # Should be at least high
        assert result['confidence'] > 0.5

    def test_severity_invalid_input(self, severity_model):
        """Test severity with invalid input"""
        features = {}

        result = severity_model.predict(features)

        # Should return default or safe value
        assert result['level'] in [1, 2, 3, 4, 5]

    def test_severity_batch_prediction(self, severity_model):
        """Test batch severity prediction"""
        features_list = [
            {'description': 'Chest pain'},
            {'description': 'Fever'},
            {'description': 'Cardiac arrest'}
        ]

        results = severity_model.batch_predict(features_list)

        assert len(results) == 3
        assert all('level' in r for r in results)


# ============================================
# ETA MODEL TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.model
class TestETAModel:
    """Test ETAModel"""

    def test_eta_prediction_basic(self, eta_model):
        """Test basic ETA prediction"""
        features = {
            'distance_km': 2.5,
            'hour': 14,
            'day_of_week': 2,
            'traffic_level': 1
        }

        result = eta_model.predict(features)

        assert result is not None
        assert 'estimated_minutes' in result
        assert 'confidence' in result
        assert result['estimated_minutes'] > 0
        assert 0 <= result['confidence'] <= 1

    def test_eta_prediction_with_traffic(self, eta_model):
        """Test ETA with heavy traffic"""
        features_light = {
            'distance_km': 2.5,
            'traffic_level': 0
        }

        features_heavy = {
            'distance_km': 2.5,
            'traffic_level': 4
        }

        eta_light = eta_model.predict(features_light)
        eta_heavy = eta_model.predict(features_heavy)

        # Heavy traffic should have higher ETA
        assert eta_heavy['estimated_minutes'] >= eta_light['estimated_minutes']

    def test_eta_prediction_rush_hour(self, eta_model):
        """Test ETA during rush hour"""
        features_normal = {
            'distance_km': 2.5,
            'hour': 14,
            'traffic_level': 2
        }

        features_rush = {
            'distance_km': 2.5,
            'hour': 8,  # Morning rush
            'traffic_level': 2
        }

        eta_normal = eta_model.predict(features_normal)
        eta_rush = eta_model.predict(features_rush)

        # Rush hour should have higher ETA
        assert eta_rush['estimated_minutes'] >= eta_normal['estimated_minutes']

    def test_eta_prediction_bounds(self, eta_model):
        """Test ETA prediction bounds"""
        features = {
            'distance_km': 5.0,
            'traffic_level': 2
        }

        result = eta_model.predict(features)

        assert 'lower_bound' in result
        assert 'upper_bound' in result
        assert result['lower_bound'] <= result['estimated_minutes']
        assert result['estimated_minutes'] <= result['upper_bound']

    def test_eta_batch_prediction(self, eta_model):
        """Test batch ETA prediction"""
        features_list = [
            {'distance_km': 1.0, 'traffic_level': 1},
            {'distance_km': 2.5, 'traffic_level': 2},
            {'distance_km': 5.0, 'traffic_level': 3}
        ]

        results = eta_model.batch_predict(features_list)

        assert len(results) == 3
        assert all('estimated_minutes' in r for r in results)
        # Longer distance should have higher ETA
        assert results[0]['estimated_minutes'] <= results[1]['estimated_minutes']
        assert results[1]['estimated_minutes'] <= results[2]['estimated_minutes']


# ============================================
# AMBULANCE SELECTOR TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.model
class TestAmbulanceSelector:
    """Test AmbulanceSelector model"""

    def test_ambulance_selection_basic(self, ambulance_selector_model):
        """Test basic ambulance selection"""
        features = {
            'patient_lat': 4.7110,
            'patient_lon': -74.0721,
            'available_ambulances': [
                {
                    'id': 1,
                    'lat': 4.7120,
                    'lon': -74.0720,
                    'type': 'advanced',
                    'available': True,
                    'avg_response_time': 8
                }
            ],
            'severity_level': 2
        }

        result = ambulance_selector_model.predict(features)

        assert result is not None
        assert 'ambulance_id' in result
        assert 'confidence' in result
        assert 0 <= result['confidence'] <= 1

    def test_ambulance_selection_ranking(self, ambulance_selector_model):
        """Test ambulance ranking"""
        features = {
            'patient_lat': 4.7110,
            'patient_lon': -74.0721,
            'available_ambulances': [
                {'id': 1, 'lat': 4.7120, 'lon': -74.0720, 'type': 'basic', 'available': True, 'avg_response_time': 10},
                {'id': 2, 'lat': 4.7115, 'lon': -74.0715, 'type': 'advanced', 'available': True, 'avg_response_time': 7},
                {'id': 3, 'lat': 4.7200, 'lon': -74.0800, 'type': 'basic', 'available': True, 'avg_response_time': 15}
            ],
            'severity_level': 2
        }

        result = ambulance_selector_model.predict(features)

        # Should select closest or best one
        assert result['ambulance_id'] in [1, 2, 3]
        assert 'ranking' in result
        assert len(result['ranking']) <= 3

    def test_ambulance_selection_type_match(self, ambulance_selector_model):
        """Test ambulance type matching"""
        features = {
            'patient_lat': 4.7110,
            'patient_lon': -74.0721,
            'available_ambulances': [
                {'id': 1, 'lat': 4.7120, 'lon': -74.0720, 'type': 'basic', 'available': True, 'avg_response_time': 8},
                {'id': 2, 'lat': 4.7120, 'lon': -74.0720, 'type': 'advanced', 'available': True, 'avg_response_time': 8}
            ],
            'severity_level': 3,
            'required_type': 'advanced'
        }

        result = ambulance_selector_model.predict(features)

        # Should prefer advanced type when required
        assert result['ambulance_id'] == 2

    def test_ambulance_no_available(self, ambulance_selector_model):
        """Test when no ambulances available"""
        features = {
            'patient_lat': 4.7110,
            'patient_lon': -74.0721,
            'available_ambulances': [],
            'severity_level': 2
        }

        result = ambulance_selector_model.predict(features)

        assert result['ambulance_id'] is None
        assert result['confidence'] == 0.0

    def test_ambulance_batch_selection(self, ambulance_selector_model):
        """Test batch ambulance selection"""
        features_list = [
            {
                'patient_lat': 4.71,
                'patient_lon': -74.07,
                'available_ambulances': [{'id': 1, 'lat': 4.71, 'lon': -74.07, 'type': 'basic', 'available': True, 'avg_response_time': 8}],
                'severity_level': 2
            },
            {
                'patient_lat': 4.72,
                'patient_lon': -74.08,
                'available_ambulances': [{'id': 2, 'lat': 4.72, 'lon': -74.08, 'type': 'advanced', 'available': True, 'avg_response_time': 7}],
                'severity_level': 2
            }
        ]

        results = ambulance_selector_model.batch_predict(features_list)

        assert len(results) == 2


# ============================================
# ROUTE OPTIMIZER TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.model
class TestRouteOptimizer:
    """Test RouteOptimizer model"""

    def test_route_optimization_basic(self, route_optimizer_model):
        """Test basic route optimization"""
        features = {
            'origin_lat': 4.7110,
            'origin_lon': -74.0721,
            'destination_lat': 4.7200,
            'destination_lon': -74.0800,
            'traffic_level': 1
        }

        result = route_optimizer_model.predict(features)

        assert result is not None
        assert 'primary_route' in result
        assert 'eta_minutes' in result
        assert 'distance_km' in result
        assert result['eta_minutes'] > 0

    def test_route_with_traffic(self, route_optimizer_model):
        """Test route with different traffic levels"""
        features_light = {
            'origin_lat': 4.7110,
            'origin_lon': -74.0721,
            'destination_lat': 4.7200,
            'destination_lon': -74.0800,
            'traffic_level': 0
        }

        features_heavy = {
            'origin_lat': 4.7110,
            'origin_lon': -74.0721,
            'destination_lat': 4.7200,
            'destination_lon': -74.0800,
            'traffic_level': 4
        }

        eta_light = route_optimizer_model.predict(features_light)
        eta_heavy = route_optimizer_model.predict(features_heavy)

        # Heavy traffic should have higher ETA
        assert eta_heavy['eta_minutes'] >= eta_light['eta_minutes']

    def test_route_alternatives(self, route_optimizer_model):
        """Test alternative routes"""
        features = {
            'origin_lat': 4.7110,
            'origin_lon': -74.0721,
            'destination_lat': 4.7200,
            'destination_lon': -74.0800,
            'traffic_level': 2,
            'num_alternatives': 2
        }

        result = route_optimizer_model.predict(features)

        assert 'alternative_routes' in result
        assert len(result['alternative_routes']) >= 0

    def test_route_recommendations(self, route_optimizer_model):
        """Test route recommendations"""
        features = {
            'origin_lat': 4.7110,
            'origin_lon': -74.0721,
            'destination_lat': 4.7200,
            'destination_lon': -74.0800,
            'traffic_level': 4  # Heavy traffic
        }

        result = route_optimizer_model.predict(features)

        assert 'recommendations' in result
        assert len(result['recommendations']) > 0
        # Should have traffic warning
        assert any('traffic' in r.lower() for r in result['recommendations'])

    def test_route_time_of_day_adjustment(self, route_optimizer_model):
        """Test time-of-day adjustments"""
        features_night = {
            'origin_lat': 4.7110,
            'origin_lon': -74.0721,
            'destination_lat': 4.7200,
            'destination_lon': -74.0800,
            'traffic_level': 1,
            'time_of_day': 2  # Night
        }

        features_rush = {
            'origin_lat': 4.7110,
            'origin_lon': -74.0721,
            'destination_lat': 4.7200,
            'destination_lon': -74.0800,
            'traffic_level': 1,
            'time_of_day': 8  # Morning rush
        }

        eta_night = route_optimizer_model.predict(features_night)
        eta_rush = route_optimizer_model.predict(features_rush)

        # Rush hour should have higher ETA
        assert eta_rush['eta_minutes'] >= eta_night['eta_minutes']

    def test_route_batch_optimization(self, route_optimizer_model):
        """Test batch route optimization"""
        features_list = [
            {'origin_lat': 4.71, 'origin_lon': -74.07, 'destination_lat': 4.72, 'destination_lon': -74.08, 'traffic_level': 1},
            {'origin_lat': 4.72, 'origin_lon': -74.08, 'destination_lat': 4.73, 'destination_lon': -74.09, 'traffic_level': 2}
        ]

        results = route_optimizer_model.batch_predict(features_list)

        assert len(results) == 2
        assert all('eta_minutes' in r for r in results)


# ============================================
# MODEL PERSISTENCE TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.model
class TestModelPersistence:
    """Test model save/load functionality"""

    def test_severity_model_save_load(self, severity_model, tmp_path):
        """Test severity model persistence"""
        model_path = tmp_path / "severity_model.pkl"

        # Save model
        success = severity_model.save_model(str(model_path))
        assert success

        # Load model
        loaded_model = severity_model.load_model(str(model_path))
        assert loaded_model is not None

    def test_eta_model_save_load(self, eta_model, tmp_path):
        """Test ETA model persistence"""
        model_path = tmp_path / "eta_model.pkl"

        success = eta_model.save_model(str(model_path))
        assert success

        loaded_model = eta_model.load_model(str(model_path))
        assert loaded_model is not None

    def test_model_get_feature_importance(self, severity_model):
        """Test model feature importance"""
        importance = severity_model.get_feature_importance()

        assert importance is not None
        assert isinstance(importance, dict)


# ============================================
# MODEL TRAINING TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.model
class TestModelTraining:
    """Test model training functionality"""

    def test_severity_model_train(self, severity_model):
        """Test severity model training"""
        X_train = np.array([
            [1, 0, 0, 10, 110, 1, 55, 1],
            [0, 1, 0, 15, 100, 0, 40, 0],
            [0, 0, 1, 20, 95, 0, 30, 0]
        ])
        y_train = np.array([1, 2, 3])

        metrics = severity_model.train(X_train, y_train)

        assert metrics is not None
        assert 'accuracy' in metrics or 'samples' in metrics

    def test_eta_model_train(self, eta_model):
        """Test ETA model training"""
        X_train = np.array([
            [2.5, 14, 2, 1],
            [3.5, 8, 1, 2],
            [1.5, 20, 4, 1]
        ])
        y_train = np.array([8, 12, 6])

        metrics = eta_model.train(X_train, y_train)

        assert metrics is not None

    def test_model_evaluate(self, severity_model):
        """Test model evaluation"""
        X_test = np.array([
            [1, 0, 0, 10, 110, 1, 55, 1],
            [0, 1, 0, 15, 100, 0, 40, 0]
        ])
        y_test = np.array([1, 2])

        metrics = severity_model.evaluate(X_test, y_test)

        assert metrics is not None
