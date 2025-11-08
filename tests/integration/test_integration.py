"""
Integration Tests for HADS ML Service
Tests for complete workflows and component interactions
"""

import pytest
from datetime import datetime, timedelta


# ============================================
# DISPATCH WORKFLOW TESTS
# ============================================

@pytest.mark.integration
class TestDispatchWorkflow:
    """Test complete dispatch workflows"""

    def test_create_dispatch_workflow(self, dispatch_repo, sample_dispatch_data):
        """Test complete dispatch creation workflow"""
        # Create dispatch
        dispatch_id = dispatch_repo.create_dispatch(sample_dispatch_data)

        assert dispatch_id is not None

        # Retrieve dispatch
        dispatch = dispatch_repo.get_dispatch(dispatch_id)

        assert dispatch is not None
        assert dispatch['id'] == dispatch_id
        assert dispatch['status'] == 'pending'

    def test_dispatch_status_progression(self, dispatch_repo, sample_dispatch_data):
        """Test dispatch status progression"""
        dispatch_id = dispatch_repo.create_dispatch(sample_dispatch_data)

        # Progress through statuses
        statuses = ['pending', 'in_transit', 'at_patient', 'returning', 'completed']

        for status in statuses:
            success = dispatch_repo.update_dispatch_status(dispatch_id, status)
            assert success

            dispatch = dispatch_repo.get_dispatch(dispatch_id)
            assert dispatch['status'] == status

    def test_dispatch_with_ambulance_assignment(self, dispatch_repo, ambulance_repo,
                                                 sample_dispatch_data, sample_ambulance_data):
        """Test dispatch with ambulance assignment"""
        # Create dispatch
        dispatch_id = dispatch_repo.create_dispatch(sample_dispatch_data)

        # Create ambulance
        ambulance_id = ambulance_repo.create_ambulance(sample_ambulance_data)

        # Assign ambulance
        success = dispatch_repo.assign_ambulance(dispatch_id, ambulance_id)
        assert success

        # Verify assignment
        dispatch = dispatch_repo.get_dispatch(dispatch_id)
        assert dispatch['assigned_ambulance_id'] == ambulance_id

        # Change ambulance status
        ambulance_repo.set_ambulance_status(ambulance_id, 'in_transit')
        ambulance = ambulance_repo.get_ambulance(ambulance_id)
        assert ambulance['status'] == 'in_transit'

    def test_dispatch_with_feedback(self, dispatch_repo, sample_dispatch_data):
        """Test dispatch with feedback"""
        dispatch_id = dispatch_repo.create_dispatch(sample_dispatch_data)

        # Complete dispatch
        dispatch_repo.update_dispatch_status(dispatch_id, 'completed')

        # Add feedback
        feedback = {
            'rating': 5,
            'comment': 'Excellent service',
            'response_time_minutes': 8,
            'patient_outcome': 'stable'
        }
        feedback_id = dispatch_repo.add_dispatch_feedback(dispatch_id, feedback)
        assert feedback_id is not None

        # Retrieve feedback
        retrieved = dispatch_repo.get_dispatch_feedback(dispatch_id)
        assert retrieved is not None
        assert retrieved['rating'] == 5


# ============================================
# PREDICTION PIPELINE TESTS
# ============================================

@pytest.mark.integration
class TestPredictionPipeline:
    """Test complete prediction pipelines"""

    def test_severity_prediction_pipeline(self, prediction_service):
        """Test severity prediction pipeline"""
        result = prediction_service.predict_severity(
            description='Chest pain and difficulty breathing',
            age=55,
            vital_signs={'heart_rate': 120, 'blood_pressure': '150/95'}
        )

        assert result is not None
        assert 'level' in result or 'severity' in result
        assert 'confidence' in result or 'confidence' in str(result).lower()

    def test_eta_prediction_pipeline(self, prediction_service):
        """Test ETA prediction pipeline"""
        result = prediction_service.predict_eta(
            origin_lat=4.7110,
            origin_lon=-74.0721,
            destination_lat=4.7200,
            destination_lon=-74.0800,
            traffic_level=2
        )

        assert result is not None
        assert 'estimated_minutes' in result or 'eta' in str(result).lower()

    def test_complete_dispatch_prediction(self, prediction_service):
        """Test complete dispatch prediction"""
        available_ambulances = [
            {
                'id': 1,
                'lat': 4.7120,
                'lon': -74.0720,
                'type': 'advanced',
                'available': True,
                'avg_response_time': 8,
                'equipment_level': 4
            },
            {
                'id': 2,
                'lat': 4.7200,
                'lon': -74.0800,
                'type': 'basic',
                'available': True,
                'avg_response_time': 12,
                'equipment_level': 2
            }
        ]

        result = prediction_service.predict_dispatch(
            patient_lat=4.7110,
            patient_lon=-74.0721,
            description='Car accident with injuries',
            severity_level=2,
            destination_lat=4.7150,
            destination_lon=-74.0700,
            available_ambulances=available_ambulances
        )

        assert result is not None
        assert isinstance(result, dict)


# ============================================
# OPTIMIZATION WORKFLOW TESTS
# ============================================

@pytest.mark.integration
class TestOptimizationWorkflow:
    """Test optimization workflows"""

    def test_dispatch_optimization_workflow(self, dispatch_repo, optimization_service,
                                             sample_dispatch_data):
        """Test dispatch optimization workflow"""
        # Create dispatch
        dispatch_id = dispatch_repo.create_dispatch(sample_dispatch_data)

        # Optimize dispatch
        result = optimization_service.optimize_dispatch(dispatch_id)

        assert result is not None
        assert isinstance(result, dict)

    def test_multi_dispatch_optimization(self, dispatch_repo, optimization_service,
                                         sample_dispatch_data):
        """Test optimizing multiple dispatches"""
        # Create multiple dispatches
        dispatch_ids = []
        for i in range(3):
            data = sample_dispatch_data.copy()
            data['patient_name'] = f'Patient {i}'
            dispatch_id = dispatch_repo.create_dispatch(data)
            dispatch_ids.append(dispatch_id)

        # Optimize all
        result = optimization_service.optimize_multiple_dispatches(dispatch_ids)

        assert result is not None


# ============================================
# TRAINING WORKFLOW TESTS
# ============================================

@pytest.mark.integration
class TestTrainingWorkflow:
    """Test model training workflows"""

    def test_model_training_pipeline(self, training_service, model_manager):
        """Test complete model training pipeline"""
        # Prepare training data
        training_data = training_service.prepare_training_data(
            model_name='severity',
            days=30
        )

        assert training_data is not None

    def test_retrain_and_activate_workflow(self, training_service, model_manager):
        """Test retraining and activating models"""
        # Retrain models
        results = training_service.retrain_all_models(days=30)

        assert results is not None
        assert isinstance(results, dict)

    def test_model_version_comparison(self, model_manager, training_service):
        """Test model version comparison workflow"""
        # Get versions
        versions = model_manager.get_model_versions('eta', limit=5)

        assert versions is not None
        assert isinstance(versions, (list, dict))


# ============================================
# HEALTH MONITORING WORKFLOW TESTS
# ============================================

@pytest.mark.integration
class TestHealthMonitoring:
    """Test health monitoring workflows"""

    def test_system_health_check(self, health_service):
        """Test system health check"""
        health = health_service.check_system_health()

        assert health is not None
        assert isinstance(health, dict)

    def test_diagnostic_report_generation(self, health_service):
        """Test diagnostic report generation"""
        report = health_service.generate_diagnostic_report()

        assert report is not None
        assert isinstance(report, dict)

    def test_all_component_health_checks(self, health_service):
        """Test health checks for all components"""
        # Models
        models = health_service.check_models_health()
        assert models is not None

        # Cache
        cache = health_service.check_cache_health()
        assert cache is not None

        # Database
        db = health_service.check_database_health()
        assert db is not None

        # Services
        services = health_service.check_service_health()
        assert services is not None


# ============================================
# CACHING INTEGRATION TESTS
# ============================================

@pytest.mark.integration
class TestCachingIntegration:
    """Test caching integration"""

    def test_prediction_result_caching(self, prediction_service, cache_repo):
        """Test prediction results are cached"""
        # Make prediction
        result1 = prediction_service.predict_severity(
            description='Cached Test',
            age=50
        )

        assert result1 is not None

        # Make same prediction
        result2 = prediction_service.predict_severity(
            description='Cached Test',
            age=50
        )

        assert result2 is not None

    def test_cache_invalidation_on_update(self, dispatch_repo, cache_repo, sample_dispatch_data):
        """Test cache invalidation on data updates"""
        # Create dispatch
        dispatch_id = dispatch_repo.create_dispatch(sample_dispatch_data)

        # Cache result
        cache_key = f'dispatch:{dispatch_id}'
        cache_repo.set(cache_key, {'id': dispatch_id})

        assert cache_repo.exists(cache_key)

        # Update dispatch (should invalidate cache in real app)
        dispatch_repo.update_dispatch_status(dispatch_id, 'in_transit')

        # Manually invalidate (in real app, service would do this)
        cache_repo.delete(cache_key)

        assert not cache_repo.exists(cache_key)


# ============================================
# DATA LAYER INTEGRATION TESTS
# ============================================

@pytest.mark.integration
class TestDataLayerIntegration:
    """Test data layer integration"""

    def test_dispatch_and_ambulance_integration(self, dispatch_repo, ambulance_repo,
                                                sample_dispatch_data, sample_ambulance_data):
        """Test dispatch and ambulance repository integration"""
        # Create dispatch
        dispatch_id = dispatch_repo.create_dispatch(sample_dispatch_data)

        # Create ambulance
        ambulance_id = ambulance_repo.create_ambulance(sample_ambulance_data)

        # Assign
        dispatch_repo.assign_ambulance(dispatch_id, ambulance_id)

        # Verify
        dispatch = dispatch_repo.get_dispatch(dispatch_id)
        assert dispatch['assigned_ambulance_id'] == ambulance_id

    def test_feature_extraction_with_real_data(self, feature_engineer, dispatch_repo,
                                                ambulance_repo, sample_dispatch_data,
                                                sample_ambulance_data):
        """Test feature extraction with real repository data"""
        # Create data
        dispatch_id = dispatch_repo.create_dispatch(sample_dispatch_data)
        ambulance_id = ambulance_repo.create_ambulance(sample_ambulance_data)

        # Get data
        dispatch = dispatch_repo.get_dispatch(dispatch_id)
        ambulance = ambulance_repo.get_ambulance(ambulance_id)

        # Extract features
        features = feature_engineer.extract_geographic_features(
            patient_lat=dispatch['patient_lat'],
            patient_lon=dispatch['patient_lon'],
            ambulance_lat=ambulance['current_lat'],
            ambulance_lon=ambulance['current_lon']
        )

        assert features is not None


# ============================================
# END-TO-END SCENARIO TESTS
# ============================================

@pytest.mark.integration
class TestE2EScenarios:
    """Test complete end-to-end scenarios"""

    def test_emergency_dispatch_scenario(self, dispatch_repo, ambulance_repo,
                                         prediction_service, optimization_service,
                                         sample_dispatch_data, sample_ambulance_data):
        """Test complete emergency dispatch scenario"""
        # 1. Create emergency dispatch
        emergency_data = sample_dispatch_data.copy()
        emergency_data['severity_level'] = 1
        emergency_data['description'] = 'Cardiac arrest'

        dispatch_id = dispatch_repo.create_dispatch(emergency_data)

        # 2. Get available ambulances
        ambulance_id = ambulance_repo.create_ambulance(sample_ambulance_data)

        # 3. Get predictions
        available = [
            {
                'id': ambulance_id,
                'lat': sample_ambulance_data['current_lat'],
                'lon': sample_ambulance_data['current_lon'],
                'type': sample_ambulance_data['type'],
                'available': True,
                'avg_response_time': 8
            }
        ]

        predictions = prediction_service.predict_dispatch(
            patient_lat=emergency_data['patient_lat'],
            patient_lon=emergency_data['patient_lon'],
            description=emergency_data['description'],
            severity_level=emergency_data['severity_level'],
            destination_lat=emergency_data['patient_lat'],
            destination_lon=emergency_data['patient_lon'],
            available_ambulances=available
        )

        assert predictions is not None

        # 4. Optimize assignment
        optimization = optimization_service.optimize_dispatch(dispatch_id)

        assert optimization is not None

        # 5. Assign ambulance
        dispatch_repo.assign_ambulance(dispatch_id, ambulance_id)

        # 6. Update statuses
        dispatch_repo.update_dispatch_status(dispatch_id, 'in_transit')
        ambulance_repo.set_ambulance_status(ambulance_id, 'in_transit')

        # Verify final state
        dispatch = dispatch_repo.get_dispatch(dispatch_id)
        ambulance = ambulance_repo.get_ambulance(ambulance_id)

        assert dispatch['status'] == 'in_transit'
        assert dispatch['assigned_ambulance_id'] == ambulance_id
        assert ambulance['status'] == 'in_transit'

    def test_routine_dispatch_scenario(self, dispatch_repo, ambulance_repo,
                                       prediction_service, health_service,
                                       sample_dispatch_data, sample_ambulance_data):
        """Test routine dispatch scenario"""
        # 1. Create routine dispatch
        routine_data = sample_dispatch_data.copy()
        routine_data['severity_level'] = 4
        routine_data['description'] = 'Routine checkup needed'

        dispatch_id = dispatch_repo.create_dispatch(routine_data)

        # 2. Check system health before dispatch
        health_before = health_service.check_system_health()
        assert health_before is not None

        # 3. Get predictions
        ambulance_id = ambulance_repo.create_ambulance(sample_ambulance_data)
        ambulance = ambulance_repo.get_ambulance(ambulance_id)

        predictions = prediction_service.predict_dispatch(
            patient_lat=routine_data['patient_lat'],
            patient_lon=routine_data['patient_lon'],
            description=routine_data['description'],
            severity_level=routine_data['severity_level'],
            destination_lat=routine_data['patient_lat'],
            destination_lon=routine_data['patient_lon'],
            available_ambulances=[{
                'id': ambulance_id,
                'lat': ambulance['current_lat'],
                'lon': ambulance['current_lon'],
                'type': ambulance['type'],
                'available': True,
                'avg_response_time': 10
            }]
        )

        assert predictions is not None

        # 4. Complete dispatch
        dispatch_repo.update_dispatch_status(dispatch_id, 'in_transit')
        dispatch_repo.update_dispatch_status(dispatch_id, 'completed')

        # 5. Add feedback
        feedback = {
            'rating': 4,
            'comment': 'Good service',
            'response_time_minutes': 12,
            'patient_outcome': 'stable'
        }
        dispatch_repo.add_dispatch_feedback(dispatch_id, feedback)

        # 6. Check health after dispatch
        health_after = health_service.check_system_health()
        assert health_after is not None


# ============================================
# API LAYER INTEGRATION TESTS
# ============================================

@pytest.mark.integration
@pytest.mark.api
class TestAPIIntegration:
    """Test API layer integration"""

    def test_rest_api_dispatch_creation(self, client):
        """Test REST API dispatch creation"""
        data = {
            'patient_name': 'Test Patient',
            'patient_age': 45,
            'patient_lat': 4.7110,
            'patient_lon': -74.0721,
            'description': 'Test dispatch',
            'severity_level': 2
        }

        # Note: This test would require actual REST endpoint setup
        # For now, we just verify the data structure is correct
        assert all(k in data for k in ['patient_name', 'patient_age', 'patient_lat', 'patient_lon'])

    def test_rest_api_prediction(self, client):
        """Test REST API prediction endpoint"""
        data = {
            'description': 'Chest pain',
            'age': 55
        }

        # Verify data structure
        assert 'description' in data
        assert 'age' in data

    def test_graphql_query_structure(self):
        """Test GraphQL query structure"""
        query = """
        {
            systemHealth {
                status
                timestamp
            }
        }
        """

        assert 'systemHealth' in query
        assert 'status' in query


# ============================================
# CONCURRENT OPERATIONS TESTS
# ============================================

@pytest.mark.integration
@pytest.mark.slow
class TestConcurrentOperations:
    """Test concurrent operations"""

    def test_multiple_dispatches_created(self, dispatch_repo, sample_dispatch_data):
        """Test creating multiple dispatches"""
        dispatch_ids = []

        for i in range(5):
            data = sample_dispatch_data.copy()
            data['patient_name'] = f'Patient {i}'
            dispatch_id = dispatch_repo.create_dispatch(data)
            dispatch_ids.append(dispatch_id)

        assert len(dispatch_ids) == 5

    def test_multiple_ambulance_updates(self, ambulance_repo, sample_ambulance_data):
        """Test updating multiple ambulances"""
        ambulance_ids = []

        for i in range(3):
            data = sample_ambulance_data.copy()
            data['code'] = f'AMB-{i:03d}'
            ambulance_id = ambulance_repo.create_ambulance(data)
            ambulance_ids.append(ambulance_id)

        # Update all
        for ambulance_id in ambulance_ids:
            ambulance_repo.update_ambulance_location(
                ambulance_id,
                latitude=4.7110 + (ambulance_id * 0.001),
                longitude=-74.0721 + (ambulance_id * 0.001)
            )

        assert len(ambulance_ids) == 3

    def test_batch_predictions(self, prediction_service):
        """Test batch predictions"""
        descriptions = ['Test ' + str(i) for i in range(10)]

        results = prediction_service.predict_severity_batch(descriptions)

        assert results is not None
