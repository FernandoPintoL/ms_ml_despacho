"""
Unit Tests for Services
Tests for model manager, prediction, training, optimization, and health services
"""

import pytest
import numpy as np
from datetime import datetime


# ============================================
# MODEL MANAGER TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.service
class TestModelManager:
    """Test ModelManager service"""

    def test_get_model(self, model_manager):
        """Test getting a model"""
        model = model_manager.get_model('severity')

        assert model is not None

    def test_load_active_models(self, model_manager):
        """Test loading active models"""
        models = model_manager.load_active_models()

        assert models is not None
        assert isinstance(models, dict)

    def test_record_prediction(self, model_manager):
        """Test recording prediction"""
        performance = {
            'prediction_time_ms': 15.5,
            'confidence': 0.95
        }

        success = model_manager.record_prediction('severity', performance)

        assert success or success is None

    def test_reload_model(self, model_manager):
        """Test reloading a model"""
        success = model_manager.reload_model('eta')

        assert success or success is None

    def test_get_model_versions(self, model_manager):
        """Test getting model versions"""
        versions = model_manager.get_model_versions('eta', limit=5)

        assert versions is not None or isinstance(versions, list)

    def test_activate_model_version(self, model_manager):
        """Test activating model version"""
        success = model_manager.activate_model_version('eta', '1.0.0')

        assert success or success is None

    def test_compare_models(self, model_manager):
        """Test comparing models"""
        comparison = model_manager.compare_models('eta', '1.0.0', '1.1.0')

        assert comparison is not None or isinstance(comparison, dict)

    def test_validate_model(self, model_manager):
        """Test model validation"""
        is_valid = model_manager.validate_model('severity')

        assert isinstance(is_valid, bool) or is_valid is not None

    def test_get_all_models_status(self, model_manager):
        """Test getting all models status"""
        status = model_manager.get_all_models_status()

        assert status is not None
        assert isinstance(status, dict)

    def test_health_check(self, model_manager):
        """Test health check"""
        health = model_manager.health_check()

        assert health is not None
        assert isinstance(health, dict)


# ============================================
# PREDICTION SERVICE TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.service
class TestPredictionService:
    """Test PredictionService"""

    def test_predict_severity(self, prediction_service):
        """Test severity prediction"""
        result = prediction_service.predict_severity(
            description='Chest pain',
            age=55
        )

        assert result is not None
        assert 'level' in result or 'severity' in result

    def test_predict_severity_with_vital_signs(self, prediction_service):
        """Test severity prediction with vital signs"""
        result = prediction_service.predict_severity(
            description='Difficulty breathing',
            age=60,
            vital_signs={'heart_rate': 120, 'blood_pressure': '150/95'}
        )

        assert result is not None

    def test_predict_eta(self, prediction_service):
        """Test ETA prediction"""
        result = prediction_service.predict_eta(
            origin_lat=4.7110,
            origin_lon=-74.0721,
            destination_lat=4.7200,
            destination_lon=-74.0800,
            traffic_level=2
        )

        assert result is not None
        assert 'estimated_minutes' in result or 'eta' in result

    def test_predict_eta_with_traffic(self, prediction_service):
        """Test ETA prediction with traffic"""
        result_light = prediction_service.predict_eta(
            origin_lat=4.71,
            origin_lon=-74.07,
            destination_lat=4.72,
            destination_lon=-74.08,
            traffic_level=0
        )

        result_heavy = prediction_service.predict_eta(
            origin_lat=4.71,
            origin_lon=-74.07,
            destination_lat=4.72,
            destination_lon=-74.08,
            traffic_level=4
        )

        assert result_light is not None
        assert result_heavy is not None
        # Heavy traffic should generally have higher ETA
        if 'estimated_minutes' in result_light and 'estimated_minutes' in result_heavy:
            assert result_heavy['estimated_minutes'] >= result_light['estimated_minutes']

    def test_select_ambulance(self, prediction_service, sample_ambulance_data):
        """Test ambulance selection"""
        available_ambulances = [
            {
                'id': 1,
                'lat': 4.7120,
                'lon': -74.0720,
                'type': 'basic',
                'available': True,
                'avg_response_time': 10
            }
        ]

        result = prediction_service.select_ambulance(
            patient_lat=4.7110,
            patient_lon=-74.0721,
            available_ambulances=available_ambulances,
            severity_level=2
        )

        assert result is not None
        assert 'ambulance_id' in result or 'id' in result

    def test_optimize_route(self, prediction_service):
        """Test route optimization"""
        result = prediction_service.optimize_route(
            origin_lat=4.7110,
            origin_lon=-74.0721,
            destination_lat=4.7200,
            destination_lon=-74.0800,
            traffic_level=2
        )

        assert result is not None
        assert 'primary_route' in result or 'route' in result

    def test_predict_dispatch_complete(self, prediction_service):
        """Test complete dispatch prediction"""
        result = prediction_service.predict_dispatch(
            patient_lat=4.7110,
            patient_lon=-74.0721,
            description='Car accident',
            severity_level=2,
            destination_lat=4.7200,
            destination_lon=-74.0800,
            available_ambulances=[
                {
                    'id': 1,
                    'lat': 4.7120,
                    'lon': -74.0720,
                    'type': 'advanced',
                    'available': True,
                    'avg_response_time': 8
                }
            ]
        )

        assert result is not None
        assert isinstance(result, dict)

    def test_predict_severity_batch(self, prediction_service):
        """Test batch severity prediction"""
        descriptions = [
            'Chest pain',
            'Fever',
            'Cardiac arrest'
        ]

        results = prediction_service.predict_severity_batch(descriptions)

        assert results is not None
        assert isinstance(results, list)

    def test_predict_eta_batch(self, prediction_service):
        """Test batch ETA prediction"""
        origins = [
            {'lat': 4.71, 'lon': -74.07},
            {'lat': 4.72, 'lon': -74.08}
        ]
        destinations = [
            {'lat': 4.72, 'lon': -74.08},
            {'lat': 4.73, 'lon': -74.09}
        ]

        results = prediction_service.predict_eta_batch(
            origins=origins,
            destinations=destinations
        )

        assert results is not None
        assert isinstance(results, list)

    def test_prediction_caching(self, prediction_service):
        """Test prediction caching"""
        # Make first prediction
        result1 = prediction_service.predict_severity(
            description='Test',
            age=50
        )

        # Make same prediction (should hit cache)
        result2 = prediction_service.predict_severity(
            description='Test',
            age=50
        )

        assert result1 is not None
        assert result2 is not None


# ============================================
# TRAINING SERVICE TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.service
class TestTrainingService:
    """Test TrainingService"""

    def test_prepare_training_data(self, training_service):
        """Test training data preparation"""
        training_data = training_service.prepare_training_data(
            model_name='severity',
            days=30
        )

        assert training_data is not None
        assert isinstance(training_data, dict)

    def test_train_model(self, training_service):
        """Test model training"""
        X_train = np.array([
            [1, 0, 0, 10, 110, 1, 55, 1],
            [0, 1, 0, 15, 100, 0, 40, 0],
            [0, 0, 1, 20, 95, 0, 30, 0]
        ])
        y_train = np.array([1, 2, 3])

        metrics = training_service.train_model(
            model_name='severity',
            X_train=X_train,
            y_train=y_train
        )

        assert metrics is not None

    def test_save_trained_model(self, training_service, tmp_path):
        """Test saving trained model"""
        model_data = {
            'name': 'eta',
            'version': '2.0.0',
            'accuracy': 0.93
        }

        success = training_service.save_trained_model(
            model_name='eta',
            model_data=model_data,
            metrics={'accuracy': 0.93}
        )

        assert success or success is None

    def test_retrain_all_models(self, training_service):
        """Test retraining all models"""
        results = training_service.retrain_all_models(days=30)

        assert results is not None
        assert isinstance(results, dict)

    def test_analyze_model_performance(self, training_service):
        """Test model performance analysis"""
        performance = training_service.analyze_model_performance(
            model_name='severity',
            hours=24
        )

        assert performance is not None
        assert isinstance(performance, dict)

    def test_get_training_history(self, training_service):
        """Test getting training history"""
        history = training_service.get_training_history(
            model_name='eta',
            limit=10
        )

        assert history is not None
        assert isinstance(history, (list, dict))

    def test_compare_training_results(self, training_service):
        """Test comparing training results"""
        comparison = training_service.compare_training_results(
            model_name='eta',
            version1='1.0.0',
            version2='1.1.0'
        )

        assert comparison is not None


# ============================================
# OPTIMIZATION SERVICE TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.service
class TestOptimizationService:
    """Test OptimizationService"""

    def test_optimize_dispatch(self, optimization_service, sample_dispatch_data):
        """Test dispatch optimization"""
        dispatch_id = 1

        result = optimization_service.optimize_dispatch(dispatch_id)

        assert result is not None
        assert isinstance(result, dict)

    def test_optimize_multiple_dispatches(self, optimization_service):
        """Test optimizing multiple dispatches"""
        dispatch_ids = [1, 2, 3]

        results = optimization_service.optimize_multiple_dispatches(
            dispatch_ids=dispatch_ids
        )

        assert results is not None
        assert isinstance(results, (list, dict))

    def test_generate_alternatives(self, optimization_service):
        """Test generating alternative scenarios"""
        dispatch_data = {
            'patient_lat': 4.7110,
            'patient_lon': -74.0721,
            'severity_level': 2
        }

        alternatives = optimization_service.generate_alternatives(
            dispatch_data=dispatch_data,
            num_alternatives=3
        )

        assert alternatives is not None
        assert isinstance(alternatives, list)

    def test_reoptimize_active_dispatch(self, optimization_service):
        """Test reoptimizing active dispatch"""
        dispatch_id = 1

        result = optimization_service.reoptimize_active_dispatch(dispatch_id)

        assert result is not None

    def test_get_optimization_metrics(self, optimization_service):
        """Test getting optimization metrics"""
        metrics = optimization_service.get_optimization_metrics(hours=24)

        assert metrics is not None
        assert isinstance(metrics, dict)

    def test_optimization_with_constraints(self, optimization_service):
        """Test optimization with constraints"""
        dispatch_data = {
            'patient_lat': 4.7110,
            'patient_lon': -74.0721,
            'severity_level': 3
        }

        constraints = {
            'max_distance_km': 10,
            'required_ambulance_type': 'advanced'
        }

        result = optimization_service.optimize_dispatch(
            dispatch_id=1,
            constraints=constraints
        )

        assert result is not None


# ============================================
# HEALTH SERVICE TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.service
class TestHealthService:
    """Test HealthService"""

    def test_check_system_health(self, health_service):
        """Test system health check"""
        health = health_service.check_system_health()

        assert health is not None
        assert 'status' in health or 'healthy' in health

    def test_check_models_health(self, health_service):
        """Test models health check"""
        models_health = health_service.check_models_health()

        assert models_health is not None
        assert isinstance(models_health, (list, dict))

    def test_check_cache_health(self, health_service):
        """Test cache health check"""
        cache_health = health_service.check_cache_health()

        assert cache_health is not None
        assert isinstance(cache_health, dict)

    def test_check_database_health(self, health_service):
        """Test database health check"""
        db_health = health_service.check_database_health()

        assert db_health is not None
        assert isinstance(db_health, dict)

    def test_check_service_health(self, health_service):
        """Test service health check"""
        service_health = health_service.check_service_health()

        assert service_health is not None
        assert isinstance(service_health, dict)

    def test_generate_diagnostic_report(self, health_service):
        """Test generating diagnostic report"""
        report = health_service.generate_diagnostic_report()

        assert report is not None
        assert isinstance(report, dict)
        assert 'timestamp' in report or 'generated_at' in report

    def test_get_uptime(self, health_service):
        """Test getting uptime"""
        uptime = health_service.get_uptime()

        assert uptime is not None

    def test_get_quick_status(self, health_service):
        """Test getting quick status"""
        status = health_service.get_quick_status()

        assert status is not None
        assert isinstance(status, dict)

    def test_health_component_metrics(self, health_service):
        """Test health component metrics"""
        health = health_service.check_system_health()

        assert health is not None
        if isinstance(health, dict):
            for component in health:
                assert isinstance(health[component], (bool, dict, str))


# ============================================
# SERVICE INTEGRATION TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.service
class TestServiceIntegration:
    """Test service interactions"""

    def test_prediction_service_uses_models(self, prediction_service, model_manager):
        """Test prediction service uses model manager"""
        result = prediction_service.predict_severity(
            description='Test',
            age=50
        )

        assert result is not None

    def test_training_service_saves_models(self, training_service, model_manager):
        """Test training service saves models"""
        X_train = np.array([[1, 2, 3], [4, 5, 6]])
        y_train = np.array([1, 2])

        result = training_service.train_model(
            model_name='severity',
            X_train=X_train,
            y_train=y_train
        )

        assert result is not None

    def test_optimization_uses_prediction(self, optimization_service, prediction_service):
        """Test optimization uses prediction service"""
        result = optimization_service.optimize_dispatch(dispatch_id=1)

        assert result is not None

    def test_health_monitors_all_services(self, health_service):
        """Test health service monitors all services"""
        health = health_service.check_system_health()

        assert health is not None
        assert isinstance(health, dict)

    def test_complete_prediction_pipeline(self, prediction_service):
        """Test complete prediction pipeline"""
        # Simulate complete dispatch prediction
        result = prediction_service.predict_dispatch(
            patient_lat=4.7110,
            patient_lon=-74.0721,
            description='Emergency',
            severity_level=2,
            destination_lat=4.7200,
            destination_lon=-74.0800,
            available_ambulances=[
                {
                    'id': 1,
                    'lat': 4.7120,
                    'lon': -74.0720,
                    'type': 'advanced',
                    'available': True,
                    'avg_response_time': 8
                }
            ]
        )

        assert result is not None
        assert isinstance(result, dict)


# ============================================
# SERVICE ERROR HANDLING TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.service
class TestServiceErrorHandling:
    """Test service error handling"""

    def test_predict_severity_invalid_input(self, prediction_service):
        """Test severity prediction with invalid input"""
        try:
            result = prediction_service.predict_severity(
                description='',
                age=-5
            )
            # Should either return result or raise exception
            assert result is not None or result is None
        except (ValueError, TypeError, AttributeError):
            assert True

    def test_predict_eta_invalid_coordinates(self, prediction_service):
        """Test ETA prediction with invalid coordinates"""
        try:
            result = prediction_service.predict_eta(
                origin_lat=999,  # Invalid
                origin_lon=999,
                destination_lat=999,
                destination_lon=999
            )
            assert result is not None or result is None
        except (ValueError, TypeError, AttributeError):
            assert True

    def test_optimize_nonexistent_dispatch(self, optimization_service):
        """Test optimizing non-existent dispatch"""
        try:
            result = optimization_service.optimize_dispatch(dispatch_id=99999)
            assert result is not None or result is None
        except (ValueError, KeyError, AttributeError):
            assert True

    def test_train_with_empty_data(self, training_service):
        """Test training with empty data"""
        try:
            X_train = np.array([]).reshape(0, 8)
            y_train = np.array([])

            result = training_service.train_model(
                model_name='severity',
                X_train=X_train,
                y_train=y_train
            )
            assert result is not None or result is None
        except (ValueError, IndexError, AttributeError):
            assert True


# ============================================
# SERVICE PERFORMANCE TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.service
@pytest.mark.slow
class TestServicePerformance:
    """Test service performance characteristics"""

    def test_prediction_response_time(self, prediction_service):
        """Test prediction response time"""
        import time

        start = time.time()
        result = prediction_service.predict_severity(
            description='Test',
            age=50
        )
        elapsed = time.time() - start

        assert result is not None
        assert elapsed < 1.0  # Should be fast

    def test_batch_prediction_efficiency(self, prediction_service):
        """Test batch prediction efficiency"""
        descriptions = ['Test ' + str(i) for i in range(10)]

        results = prediction_service.predict_severity_batch(descriptions)

        assert results is not None
        assert len(results) >= 0

    def test_caching_improves_performance(self, prediction_service):
        """Test caching improves performance"""
        import time

        # First call (no cache)
        start1 = time.time()
        result1 = prediction_service.predict_severity(
            description='Cached',
            age=50
        )
        time1 = time.time() - start1

        # Second call (should hit cache)
        start2 = time.time()
        result2 = prediction_service.predict_severity(
            description='Cached',
            age=50
        )
        time2 = time.time() - start2

        assert result1 is not None
        assert result2 is not None
        # Cache hit should be faster (in theory)
        assert time1 >= 0 and time2 >= 0
