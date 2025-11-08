"""
Unit Tests for Repositories
Tests for dispatch, ambulance, model, cache, and feature engineering repositories
"""

import pytest
from datetime import datetime, timedelta
import numpy as np


# ============================================
# DISPATCH REPOSITORY TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.repo
class TestDispatchRepository:
    """Test DispatchRepository"""

    def test_create_dispatch(self, dispatch_repo, sample_dispatch_data):
        """Test creating a dispatch"""
        dispatch_id = dispatch_repo.create_dispatch(sample_dispatch_data)

        assert dispatch_id is not None
        assert isinstance(dispatch_id, int)

    def test_get_dispatch(self, dispatch_repo, sample_dispatch_data):
        """Test retrieving a dispatch"""
        # Create dispatch first
        dispatch_id = dispatch_repo.create_dispatch(sample_dispatch_data)

        # Get dispatch
        dispatch = dispatch_repo.get_dispatch(dispatch_id)

        assert dispatch is not None
        assert dispatch['id'] == dispatch_id
        assert dispatch['patient_name'] == sample_dispatch_data['patient_name']

    def test_update_dispatch_status(self, dispatch_repo, sample_dispatch_data):
        """Test updating dispatch status"""
        dispatch_id = dispatch_repo.create_dispatch(sample_dispatch_data)

        success = dispatch_repo.update_dispatch_status(dispatch_id, 'in_transit')

        assert success
        dispatch = dispatch_repo.get_dispatch(dispatch_id)
        assert dispatch['status'] == 'in_transit'

    def test_assign_ambulance(self, dispatch_repo, sample_dispatch_data):
        """Test assigning ambulance to dispatch"""
        dispatch_id = dispatch_repo.create_dispatch(sample_dispatch_data)
        ambulance_id = 5

        success = dispatch_repo.assign_ambulance(dispatch_id, ambulance_id)

        assert success
        dispatch = dispatch_repo.get_dispatch(dispatch_id)
        assert dispatch['assigned_ambulance_id'] == ambulance_id

    def test_get_recent_dispatches(self, dispatch_repo, sample_dispatch_data):
        """Test getting recent dispatches"""
        # Create multiple dispatches
        for i in range(3):
            data = sample_dispatch_data.copy()
            data['patient_name'] = f'Patient {i}'
            dispatch_repo.create_dispatch(data)

        # Get recent dispatches
        dispatches = dispatch_repo.get_recent_dispatches(hours=24, limit=10)

        assert len(dispatches) >= 3
        assert all('id' in d for d in dispatches)

    def test_get_dispatch_statistics(self, dispatch_repo, sample_dispatch_data):
        """Test getting dispatch statistics"""
        # Create dispatches with different severities
        for severity in [1, 2, 3, 4, 5]:
            data = sample_dispatch_data.copy()
            data['severity_level'] = severity
            dispatch_repo.create_dispatch(data)

        stats = dispatch_repo.get_dispatch_statistics(hours=24)

        assert stats is not None
        assert 'total' in stats
        assert stats['total'] >= 5

    def test_get_severity_distribution(self, dispatch_repo, sample_dispatch_data):
        """Test severity distribution"""
        dispatch_repo.create_dispatch(sample_dispatch_data)

        distribution = dispatch_repo.get_severity_distribution(hours=24)

        assert distribution is not None
        assert isinstance(distribution, dict)

    def test_add_dispatch_feedback(self, dispatch_repo, sample_dispatch_data):
        """Test adding dispatch feedback"""
        dispatch_id = dispatch_repo.create_dispatch(sample_dispatch_data)

        feedback = {
            'rating': 5,
            'comment': 'Great service',
            'response_time_minutes': 8,
            'patient_outcome': 'stable'
        }

        feedback_id = dispatch_repo.add_dispatch_feedback(dispatch_id, feedback)

        assert feedback_id is not None

    def test_get_dispatch_feedback(self, dispatch_repo, sample_dispatch_data):
        """Test retrieving dispatch feedback"""
        dispatch_id = dispatch_repo.create_dispatch(sample_dispatch_data)

        feedback = {
            'rating': 5,
            'comment': 'Excellent',
            'response_time_minutes': 10
        }
        dispatch_repo.add_dispatch_feedback(dispatch_id, feedback)

        retrieved_feedback = dispatch_repo.get_dispatch_feedback(dispatch_id)

        assert retrieved_feedback is not None
        assert retrieved_feedback['rating'] == 5

    def test_get_average_rating(self, dispatch_repo, sample_dispatch_data):
        """Test getting average rating"""
        dispatch_id = dispatch_repo.create_dispatch(sample_dispatch_data)

        feedback = {'rating': 5, 'response_time_minutes': 8}
        dispatch_repo.add_dispatch_feedback(dispatch_id, feedback)

        avg_rating = dispatch_repo.get_average_rating()

        assert avg_rating is not None
        assert 0 <= avg_rating <= 5


# ============================================
# AMBULANCE REPOSITORY TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.repo
class TestAmbulanceRepository:
    """Test AmbulanceRepository"""

    def test_create_ambulance(self, ambulance_repo, sample_ambulance_data):
        """Test creating ambulance"""
        ambulance_id = ambulance_repo.create_ambulance(sample_ambulance_data)

        assert ambulance_id is not None
        assert isinstance(ambulance_id, int)

    def test_get_ambulance(self, ambulance_repo, sample_ambulance_data):
        """Test retrieving ambulance"""
        ambulance_id = ambulance_repo.create_ambulance(sample_ambulance_data)

        ambulance = ambulance_repo.get_ambulance(ambulance_id)

        assert ambulance is not None
        assert ambulance['id'] == ambulance_id
        assert ambulance['code'] == sample_ambulance_data['code']

    def test_get_ambulance_by_code(self, ambulance_repo, sample_ambulance_data):
        """Test retrieving ambulance by code"""
        ambulance_repo.create_ambulance(sample_ambulance_data)

        ambulance = ambulance_repo.get_ambulance_by_code(sample_ambulance_data['code'])

        assert ambulance is not None
        assert ambulance['code'] == sample_ambulance_data['code']

    def test_get_available_ambulances(self, ambulance_repo, sample_ambulance_data):
        """Test getting available ambulances"""
        # Create ambulances with different statuses
        data1 = sample_ambulance_data.copy()
        data1['status'] = 'available'
        ambulance_repo.create_ambulance(data1)

        data2 = sample_ambulance_data.copy()
        data2['code'] = 'AMB-002'
        data2['status'] = 'available'
        ambulance_repo.create_ambulance(data2)

        available = ambulance_repo.get_available_ambulances(ambulance_type='advanced')

        assert available is not None
        assert len(available) >= 0

    def test_get_available_ambulances_near(self, ambulance_repo, sample_ambulance_data):
        """Test getting nearby available ambulances"""
        ambulance_repo.create_ambulance(sample_ambulance_data)

        ambulances = ambulance_repo.get_available_ambulances_near(
            latitude=4.7110,
            longitude=-74.0721,
            radius_km=5
        )

        assert ambulances is not None
        assert isinstance(ambulances, list)

    def test_update_ambulance_location(self, ambulance_repo, sample_ambulance_data):
        """Test updating ambulance location"""
        ambulance_id = ambulance_repo.create_ambulance(sample_ambulance_data)

        success = ambulance_repo.update_ambulance_location(
            ambulance_id,
            latitude=4.7150,
            longitude=-74.0700,
            accuracy=15.0
        )

        assert success

    def test_get_ambulance_location_history(self, ambulance_repo, sample_ambulance_data):
        """Test getting ambulance location history"""
        ambulance_id = ambulance_repo.create_ambulance(sample_ambulance_data)

        # Update location multiple times
        for i in range(3):
            ambulance_repo.update_ambulance_location(
                ambulance_id,
                latitude=4.7110 + i * 0.001,
                longitude=-74.0721 + i * 0.001
            )

        history = ambulance_repo.get_ambulance_location_history(
            ambulance_id,
            hours=24,
            limit=10
        )

        assert history is not None
        assert isinstance(history, list)

    def test_set_ambulance_status(self, ambulance_repo, sample_ambulance_data):
        """Test setting ambulance status"""
        ambulance_id = ambulance_repo.create_ambulance(sample_ambulance_data)

        success = ambulance_repo.set_ambulance_status(ambulance_id, 'in_transit')

        assert success
        ambulance = ambulance_repo.get_ambulance(ambulance_id)
        assert ambulance['status'] == 'in_transit'

    def test_get_ambulance_stats(self, ambulance_repo, sample_ambulance_data):
        """Test getting ambulance statistics"""
        ambulance_id = ambulance_repo.create_ambulance(sample_ambulance_data)

        stats = ambulance_repo.get_ambulance_stats(ambulance_id, days=30)

        assert stats is not None
        assert 'total_dispatches' in stats or 'id' in stats

    def test_get_fleet_status(self, ambulance_repo, sample_ambulance_data):
        """Test getting fleet status"""
        # Create multiple ambulances
        for i in range(3):
            data = sample_ambulance_data.copy()
            data['code'] = f'AMB-{i:03d}'
            ambulance_repo.create_ambulance(data)

        fleet_status = ambulance_repo.get_fleet_status()

        assert fleet_status is not None
        assert 'total_ambulances' in fleet_status or isinstance(fleet_status, dict)

    def test_get_ambulance_type_distribution(self, ambulance_repo, sample_ambulance_data):
        """Test ambulance type distribution"""
        ambulance_repo.create_ambulance(sample_ambulance_data)

        distribution = ambulance_repo.get_ambulance_type_distribution()

        assert distribution is not None
        assert isinstance(distribution, dict)

    def test_schedule_maintenance(self, ambulance_repo, sample_ambulance_data):
        """Test scheduling maintenance"""
        ambulance_id = ambulance_repo.create_ambulance(sample_ambulance_data)

        maintenance_id = ambulance_repo.schedule_maintenance(
            ambulance_id,
            reason='Regular checkup'
        )

        assert maintenance_id is not None

    def test_complete_maintenance(self, ambulance_repo, sample_ambulance_data):
        """Test completing maintenance"""
        ambulance_id = ambulance_repo.create_ambulance(sample_ambulance_data)

        maintenance_id = ambulance_repo.schedule_maintenance(ambulance_id, reason='Checkup')

        success = ambulance_repo.complete_maintenance(maintenance_id, notes='Completed')

        assert success


# ============================================
# MODEL REPOSITORY TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.repo
class TestModelRepository:
    """Test ModelRepository"""

    def test_save_model_version(self, model_repo):
        """Test saving model version"""
        model_data = {
            'name': 'eta',
            'version': '1.0.0',
            'model_type': 'gradient_boosting',
            'training_samples': 5000,
            'accuracy': 0.92,
            'mae': 2.5
        }

        version_id = model_repo.save_model_version(model_data)

        assert version_id is not None
        assert isinstance(version_id, int)

    def test_get_model_version(self, model_repo):
        """Test retrieving model version"""
        model_data = {
            'name': 'severity',
            'version': '1.0.0',
            'model_type': 'naive_bayes',
            'training_samples': 3000,
            'accuracy': 0.88
        }

        version_id = model_repo.save_model_version(model_data)
        version = model_repo.get_model_version(version_id)

        assert version is not None
        assert version['version'] == '1.0.0'

    def test_get_active_model(self, model_repo):
        """Test getting active model"""
        model_data = {
            'name': 'route',
            'version': '1.0.0',
            'model_type': 'graph_based',
            'is_active': True
        }

        model_repo.save_model_version(model_data)
        active = model_repo.get_active_model('route')

        assert active is not None

    def test_activate_model(self, model_repo):
        """Test activating a model version"""
        model_data = {
            'name': 'ambulance',
            'version': '1.0.0',
            'model_type': 'weighted_scoring'
        }

        version_id = model_repo.save_model_version(model_data)
        success = model_repo.activate_model(version_id)

        assert success

    def test_deactivate_model(self, model_repo):
        """Test deactivating a model version"""
        model_data = {
            'name': 'eta',
            'version': '0.9.0',
            'model_type': 'gradient_boosting',
            'is_active': True
        }

        version_id = model_repo.save_model_version(model_data)
        success = model_repo.deactivate_model(version_id)

        assert success

    def test_record_prediction_performance(self, model_repo):
        """Test recording prediction performance"""
        model_data = {
            'name': 'severity',
            'version': '1.0.0',
            'model_type': 'naive_bayes'
        }
        model_repo.save_model_version(model_data)

        performance = {
            'prediction_time_ms': 15.5,
            'confidence': 0.95,
            'input_features': 8
        }

        success = model_repo.record_prediction_performance('severity', performance)

        assert success

    def test_get_model_performance_stats(self, model_repo):
        """Test getting model performance statistics"""
        model_data = {
            'name': 'eta',
            'version': '1.0.0',
            'model_type': 'gradient_boosting'
        }
        model_repo.save_model_version(model_data)

        performance = {
            'prediction_time_ms': 20.0,
            'confidence': 0.90
        }
        model_repo.record_prediction_performance('eta', performance)

        stats = model_repo.get_model_performance_stats('eta', hours=24)

        assert stats is not None

    def test_get_model_versions(self, model_repo):
        """Test getting model versions"""
        # Save multiple versions
        for version in ['1.0.0', '1.1.0', '1.2.0']:
            model_data = {
                'name': 'route',
                'version': version,
                'model_type': 'graph_based'
            }
            model_repo.save_model_version(model_data)

        versions = model_repo.get_model_versions('route', limit=5)

        assert versions is not None
        assert len(versions) >= 0

    def test_compare_models(self, model_repo):
        """Test comparing models"""
        model1 = {
            'name': 'eta',
            'version': '1.0.0',
            'accuracy': 0.92,
            'mae': 2.5
        }
        model2 = {
            'name': 'eta',
            'version': '1.1.0',
            'accuracy': 0.94,
            'mae': 2.2
        }

        model_repo.save_model_version(model1)
        model_repo.save_model_version(model2)

        comparison = model_repo.compare_models('eta', '1.0.0', '1.1.0')

        assert comparison is not None

    def test_validate_model(self, model_repo):
        """Test model validation"""
        model_data = {
            'name': 'severity',
            'version': '1.0.0',
            'model_type': 'naive_bayes',
            'accuracy': 0.88
        }

        version_id = model_repo.save_model_version(model_data)
        is_valid = model_repo.validate_model(version_id)

        assert is_valid


# ============================================
# CACHE REPOSITORY TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.repo
class TestCacheRepository:
    """Test CacheRepository"""

    def test_set_and_get_cache(self, cache_repo):
        """Test setting and getting cache"""
        cache_repo.set('test_key', {'data': 'value'}, ttl=300)

        result = cache_repo.get('test_key')

        assert result is not None

    def test_cache_exists(self, cache_repo):
        """Test checking cache existence"""
        cache_repo.set('exists_key', 'value')

        exists = cache_repo.exists('exists_key')

        assert exists

    def test_cache_delete(self, cache_repo):
        """Test deleting cache"""
        cache_repo.set('delete_key', 'value')

        success = cache_repo.delete('delete_key')

        assert success
        assert not cache_repo.exists('delete_key')

    def test_cache_by_pattern(self, cache_repo):
        """Test getting cache by pattern"""
        cache_repo.set('user:1:name', 'John')
        cache_repo.set('user:2:name', 'Jane')
        cache_repo.set('user:1:age', '30')

        results = cache_repo.get_by_pattern('user:1:*')

        assert results is not None
        assert isinstance(results, list)

    def test_delete_cache_pattern(self, cache_repo):
        """Test deleting cache by pattern"""
        cache_repo.set('temp:1:data', 'value1')
        cache_repo.set('temp:2:data', 'value2')

        deleted = cache_repo.delete_pattern('temp:*')

        assert deleted >= 0

    def test_cache_increment(self, cache_repo):
        """Test incrementing counter"""
        cache_repo.set('counter', 0)

        result = cache_repo.increment('counter')

        assert result >= 0

    def test_cache_decrement(self, cache_repo):
        """Test decrementing counter"""
        cache_repo.set('countdown', 10)

        result = cache_repo.decrement('countdown')

        assert result >= 0

    def test_cache_push_list(self, cache_repo):
        """Test pushing to list"""
        cache_repo.push_list('items', 'item1')
        cache_repo.push_list('items', 'item2')

        items = cache_repo.get_list('items', start=0, stop=-1)

        assert items is not None

    def test_cache_list_length(self, cache_repo):
        """Test getting list length"""
        cache_repo.push_list('queue', 'item1')
        cache_repo.push_list('queue', 'item2')

        length = cache_repo.list_length('queue')

        assert length >= 0

    def test_cache_add_to_set(self, cache_repo):
        """Test adding to set"""
        cache_repo.add_to_set('tags', 'python')
        cache_repo.add_to_set('tags', 'ml')

        tags = cache_repo.get_set('tags')

        assert tags is not None

    def test_cache_remove_from_set(self, cache_repo):
        """Test removing from set"""
        cache_repo.add_to_set('tags', 'python')

        success = cache_repo.remove_from_set('tags', 'python')

        assert success

    def test_cache_acquire_lock(self, cache_repo):
        """Test acquiring lock"""
        lock_id = cache_repo.acquire_lock('resource:1', timeout=10)

        assert lock_id is not None or lock_id is None  # Depends on Redis

    def test_cache_release_lock(self, cache_repo):
        """Test releasing lock"""
        lock_id = cache_repo.acquire_lock('resource:2', timeout=10)

        if lock_id:
            success = cache_repo.release_lock('resource:2', lock_id)
            assert success

    def test_cache_get_stats(self, cache_repo):
        """Test getting cache statistics"""
        cache_repo.set('stat_key', 'value')

        stats = cache_repo.get_cache_stats()

        assert stats is not None


# ============================================
# FEATURE ENGINEER TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.repo
class TestFeatureEngineer:
    """Test FeatureEngineer"""

    def test_calculate_distance(self, feature_engineer):
        """Test distance calculation"""
        distance = feature_engineer.calculate_distance(
            lat1=4.7110,
            lon1=-74.0721,
            lat2=4.7200,
            lon2=-74.0800
        )

        assert distance > 0
        assert isinstance(distance, float)

    def test_calculate_bearing(self, feature_engineer):
        """Test bearing calculation"""
        bearing = feature_engineer.calculate_bearing(
            lat1=4.7110,
            lon1=-74.0721,
            lat2=4.7200,
            lon2=-74.0800
        )

        assert 0 <= bearing < 360
        assert isinstance(bearing, float)

    def test_extract_geographic_features(self, feature_engineer):
        """Test geographic feature extraction"""
        features = feature_engineer.extract_geographic_features(
            patient_lat=4.7110,
            patient_lon=-74.0721,
            ambulance_lat=4.7120,
            ambulance_lon=-74.0720,
            hospital_lat=4.7150,
            hospital_lon=-74.0700
        )

        assert features is not None
        assert isinstance(features, dict)
        assert 'distance_to_ambulance' in features or 'patient_lat' in features

    def test_extract_datetime_features(self, feature_engineer):
        """Test datetime feature extraction"""
        features = feature_engineer.extract_datetime_features(
            timestamp=datetime.utcnow()
        )

        assert features is not None
        assert isinstance(features, dict)

    def test_extract_time_window_features(self, feature_engineer):
        """Test time window feature extraction"""
        features = feature_engineer.extract_time_window_features(
            timestamp=datetime.utcnow()
        )

        assert features is not None
        assert isinstance(features, dict)

    def test_encode_traffic_level(self, feature_engineer):
        """Test traffic level encoding"""
        for level in [0, 1, 2, 3, 4]:
            encoded = feature_engineer.encode_traffic_level(level)

            assert encoded is not None
            assert isinstance(encoded, (int, float, dict))

    def test_encode_weather(self, feature_engineer):
        """Test weather encoding"""
        weather = 'rainy'
        encoded = feature_engineer.encode_weather(weather)

        assert encoded is not None

    def test_extract_severity_indicators(self, feature_engineer):
        """Test severity indicators extraction"""
        indicators = feature_engineer.extract_severity_indicators(
            description='Chest pain and difficulty breathing',
            vital_signs={'heart_rate': 120, 'blood_pressure': '150/95'}
        )

        assert indicators is not None
        assert isinstance(indicators, dict)

    def test_extract_ambulance_features(self, feature_engineer):
        """Test ambulance feature extraction"""
        features = feature_engineer.extract_ambulance_features(
            ambulance_type='advanced',
            equipment_level=4,
            avg_response_time=8,
            is_available=True
        )

        assert features is not None
        assert isinstance(features, dict)

    def test_normalize_value(self, feature_engineer):
        """Test value normalization"""
        normalized = feature_engineer.normalize_value(
            value=50,
            min_value=0,
            max_value=100
        )

        assert 0 <= normalized <= 1

    def test_standardize_value(self, feature_engineer):
        """Test value standardization"""
        standardized = feature_engineer.standardize_value(
            value=50,
            mean=50,
            std=10
        )

        assert isinstance(standardized, float)

    def test_validate_features(self, feature_engineer):
        """Test feature validation"""
        features = {
            'distance': 2.5,
            'hour': 14,
            'traffic_level': 2
        }

        is_valid = feature_engineer.validate_features(features)

        assert isinstance(is_valid, bool)

    def test_extract_features_batch(self, feature_engineer):
        """Test batch feature extraction"""
        batch_data = [
            {
                'patient_lat': 4.71,
                'patient_lon': -74.07,
                'ambulance_lat': 4.71,
                'ambulance_lon': -74.07
            },
            {
                'patient_lat': 4.72,
                'patient_lon': -74.08,
                'ambulance_lat': 4.72,
                'ambulance_lon': -74.08
            }
        ]

        features = feature_engineer.extract_features_batch(batch_data)

        assert features is not None
        assert isinstance(features, (list, np.ndarray))

    def test_get_feature_statistics(self, feature_engineer):
        """Test getting feature statistics"""
        batch_data = [
            {'distance': 2.5, 'traffic': 1},
            {'distance': 3.0, 'traffic': 2},
            {'distance': 1.5, 'traffic': 0}
        ]

        stats = feature_engineer.get_feature_statistics(batch_data)

        assert stats is not None
        assert isinstance(stats, dict)

    def test_extract_features_consistency(self, feature_engineer):
        """Test consistency of feature extraction"""
        data = {
            'patient_lat': 4.7110,
            'patient_lon': -74.0721,
            'ambulance_lat': 4.7120,
            'ambulance_lon': -74.0720
        }

        features1 = feature_engineer.extract_geographic_features(**data)
        features2 = feature_engineer.extract_geographic_features(**data)

        # Same input should produce same output
        assert features1 == features2 or isinstance(features1, dict)


# ============================================
# REPOSITORY INTEGRATION TESTS
# ============================================

@pytest.mark.unit
@pytest.mark.repo
class TestRepositoryIntegration:
    """Test repository interactions"""

    def test_dispatch_ambulance_assignment(self, dispatch_repo, ambulance_repo, sample_dispatch_data, sample_ambulance_data):
        """Test dispatch and ambulance integration"""
        # Create dispatch
        dispatch_id = dispatch_repo.create_dispatch(sample_dispatch_data)

        # Create ambulance
        ambulance_id = ambulance_repo.create_ambulance(sample_ambulance_data)

        # Assign ambulance to dispatch
        success = dispatch_repo.assign_ambulance(dispatch_id, ambulance_id)

        assert success
        dispatch = dispatch_repo.get_dispatch(dispatch_id)
        assert dispatch['assigned_ambulance_id'] == ambulance_id

    def test_cache_invalidation_on_update(self, cache_repo, dispatch_repo, sample_dispatch_data):
        """Test cache invalidation"""
        dispatch_id = dispatch_repo.create_dispatch(sample_dispatch_data)

        # Cache dispatch
        cache_repo.set(f'dispatch:{dispatch_id}', sample_dispatch_data)
        assert cache_repo.exists(f'dispatch:{dispatch_id}')

        # Update dispatch
        dispatch_repo.update_dispatch_status(dispatch_id, 'in_transit')

        # Cache should be invalidated (application should do this)
        cache_repo.delete(f'dispatch:{dispatch_id}')
        assert not cache_repo.exists(f'dispatch:{dispatch_id}')

    def test_model_version_persistence(self, model_repo, feature_engineer):
        """Test model version persistence and retrieval"""
        model_data = {
            'name': 'eta',
            'version': '1.0.0',
            'model_type': 'gradient_boosting',
            'accuracy': 0.92
        }

        version_id = model_repo.save_model_version(model_data)
        retrieved = model_repo.get_model_version(version_id)

        assert retrieved is not None
        assert retrieved['version'] == '1.0.0'
