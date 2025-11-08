"""
Configuration settings for MS ML Despacho microservice
Loads from environment variables with sensible defaults
"""

import os
from datetime import timedelta
from pathlib import Path

# ============================================
# BASE CONFIGURATION
# ============================================

class Config:
    """Base configuration"""

    # Flask
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    TESTING = os.getenv('TESTING', 'False').lower() == 'true'
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Server
    SERVER_HOST = os.getenv('SERVER_HOST', '0.0.0.0')
    SERVER_PORT = int(os.getenv('SERVER_PORT', 5000))
    SERVER_WORKERS = int(os.getenv('SERVER_WORKERS', 4))

    # Paths
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    MODELS_DIR = os.getenv('MODEL_PATH', str(BASE_DIR / 'ml' / 'models'))
    DATA_DIR = os.getenv('DATA_PATH', str(BASE_DIR / 'ml' / 'data'))
    LOGS_DIR = str(BASE_DIR / 'logs')

    # ============================================
    # DATABASE
    # ============================================

    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'postgresql://user:password@localhost:5432/ms_ml_despacho'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': int(os.getenv('DATABASE_POOL_SIZE', 20)),
        'pool_recycle': int(os.getenv('DATABASE_POOL_RECYCLE', 3600)),
        'pool_pre_ping': True,
        'max_overflow': int(os.getenv('DATABASE_MAX_OVERFLOW', 40))
    }

    # ============================================
    # REDIS CACHE
    # ============================================

    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = int(os.getenv('REDIS_CACHE_TTL', 3600))

    # ============================================
    # AUTHENTICATION & SECURITY
    # ============================================

    JWT_SECRET = os.getenv('JWT_SECRET', SECRET_KEY)
    JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
    JWT_EXPIRATION = int(os.getenv('JWT_EXPIRATION', 86400))

    ENFORCE_HTTPS = os.getenv('ENFORCE_HTTPS', 'True').lower() == 'true'
    SECURE_COOKIES = os.getenv('SECURE_COOKIES', 'True').lower() == 'true'

    # ============================================
    # CORS
    # ============================================

    CORS_ORIGINS = os.getenv(
        'CORS_ORIGINS',
        'http://localhost:3000,http://localhost:3001'
    ).split(',')
    CORS_ALLOW_CREDENTIALS = os.getenv('CORS_ALLOW_CREDENTIALS', 'True').lower() == 'true'
    CORS_ALLOW_METHODS = os.getenv('CORS_ALLOW_METHODS', 'GET,POST,PUT,DELETE,OPTIONS').split(',')
    CORS_ALLOW_HEADERS = os.getenv('CORS_ALLOW_HEADERS', 'Content-Type,Authorization').split(',')

    # ============================================
    # RATE LIMITING
    # ============================================

    RATE_LIMIT_ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'True').lower() == 'true'
    RATE_LIMIT_DEFAULT = int(os.getenv('RATE_LIMIT_DEFAULT', 100))
    RATE_LIMIT_WINDOW = int(os.getenv('RATE_LIMIT_WINDOW', 60))
    RATE_LIMIT_PER_USER = int(os.getenv('RATE_LIMIT_PER_USER', 200))
    RATE_LIMIT_PER_USER_WINDOW = int(os.getenv('RATE_LIMIT_PER_USER_WINDOW', 3600))

    # ============================================
    # LOGGING
    # ============================================

    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = os.getenv('LOG_FORMAT', 'json')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/app.log')
    LOG_MAX_BYTES = int(os.getenv('LOG_MAX_BYTES', 10485760))  # 10MB
    LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', 5))
    VERBOSE_LOGGING = os.getenv('VERBOSE_LOGGING', 'False').lower() == 'true'

    # ============================================
    # MONITORING
    # ============================================

    PROMETHEUS_ENABLED = os.getenv('PROMETHEUS_ENABLED', 'True').lower() == 'true'
    PROMETHEUS_PORT = int(os.getenv('PROMETHEUS_PORT', 8001))
    HEALTH_CHECK_INTERVAL = int(os.getenv('HEALTH_CHECK_INTERVAL', 30))
    SENTRY_DSN = os.getenv('SENTRY_DSN', '')

    # ============================================
    # ML MODELS
    # ============================================

    MODEL_VERSION = os.getenv('MODEL_VERSION', '1.0.0')
    ENABLE_MODEL_AUTO_UPDATE = os.getenv('ENABLE_MODEL_AUTO_UPDATE', 'False').lower() == 'true'
    MODEL_AUTO_UPDATE_INTERVAL = int(os.getenv('MODEL_AUTO_UPDATE_INTERVAL', 604800))

    # ETA Model
    ETA_MODEL_TYPE = os.getenv('ETA_MODEL_TYPE', 'gradient_boosting')
    ETA_MODEL_MIN_ACCURACY = float(os.getenv('ETA_MODEL_MIN_ACCURACY', 0.85))
    ETA_CONFIDENCE_THRESHOLD = float(os.getenv('ETA_CONFIDENCE_THRESHOLD', 0.7))

    # Severity Classifier
    SEVERITY_MODEL_TYPE = os.getenv('SEVERITY_MODEL_TYPE', 'naive_bayes')
    SEVERITY_CONFIDENCE_THRESHOLD = float(os.getenv('SEVERITY_CONFIDENCE_THRESHOLD', 0.75))

    # Ambulance Selector
    AMBULANCE_MAX_DISTANCE_KM = int(os.getenv('AMBULANCE_MAX_DISTANCE_KM', 15))
    AMBULANCE_PREFERENCE_WEIGHT = float(os.getenv('AMBULANCE_PREFERENCE_WEIGHT', 0.4))
    DISTANCE_WEIGHT = float(os.getenv('DISTANCE_WEIGHT', 0.3))
    AVAILABILITY_WEIGHT = float(os.getenv('AVAILABILITY_WEIGHT', 0.3))

    # Route Optimizer
    ROUTE_OPTIMIZATION_ENABLED = os.getenv('ROUTE_OPTIMIZATION_ENABLED', 'True').lower() == 'true'
    ROUTE_CACHE_TTL = int(os.getenv('ROUTE_CACHE_TTL', 300))
    ROUTE_MAX_ALTERNATIVES = int(os.getenv('ROUTE_MAX_ALTERNATIVES', 3))
    ROUTE_TRAFFIC_FORECAST = os.getenv('ROUTE_TRAFFIC_FORECAST', 'True').lower() == 'true'

    # ============================================
    # TRAINING & UPDATES
    # ============================================

    AUTO_TRAIN_ENABLED = os.getenv('AUTO_TRAIN_ENABLED', 'False').lower() == 'true'
    AUTO_TRAIN_INTERVAL = int(os.getenv('AUTO_TRAIN_INTERVAL', 604800))
    MIN_TRAINING_SAMPLES = int(os.getenv('MIN_TRAINING_SAMPLES', 1000))
    RETRAIN_ON_ACCURACY_DROP = os.getenv('RETRAIN_ON_ACCURACY_DROP', 'True').lower() == 'true'
    ACCURACY_DROP_THRESHOLD = float(os.getenv('ACCURACY_DROP_THRESHOLD', 0.05))

    # ============================================
    # CACHING
    # ============================================

    CACHE_PREDICTIONS = os.getenv('CACHE_PREDICTIONS', 'True').lower() == 'true'
    CACHE_MODEL_OUTPUTS = os.getenv('CACHE_MODEL_OUTPUTS', 'True').lower() == 'true'
    CACHE_EXTERNAL_CALLS = os.getenv('CACHE_EXTERNAL_CALLS', 'True').lower() == 'true'
    CACHE_EXPIRATION = int(os.getenv('CACHE_EXPIRATION', 300))

    # ============================================
    # EXTERNAL SERVICES
    # ============================================

    MS_DESPACHO_URL = os.getenv('MS_DESPACHO_URL', 'http://localhost:9000')
    MS_AUTH_URL = os.getenv('MS_AUTH_URL', 'http://localhost:8003')
    MS_WEBSOCKET_URL = os.getenv('MS_WEBSOCKET_URL', 'http://localhost:3000')

    TRAFFIC_API_ENABLED = os.getenv('TRAFFIC_API_ENABLED', 'True').lower() == 'true'
    TRAFFIC_API_KEY = os.getenv('TRAFFIC_API_KEY', '')
    HOSPITAL_API_URL = os.getenv('HOSPITAL_API_URL', '')
    HOSPITAL_API_KEY = os.getenv('HOSPITAL_API_KEY', '')

    # ============================================
    # FEATURE FLAGS
    # ============================================

    FEATURE_ADVANCED_ROUTING = os.getenv('FEATURE_ADVANCED_ROUTING', 'True').lower() == 'true'
    FEATURE_TRAFFIC_PREDICTION = os.getenv('FEATURE_TRAFFIC_PREDICTION', 'True').lower() == 'true'
    FEATURE_AMBULANCE_OPTIMIZATION = os.getenv('FEATURE_AMBULANCE_OPTIMIZATION', 'True').lower() == 'true'
    FEATURE_BATCH_PREDICTION = os.getenv('FEATURE_BATCH_PREDICTION', 'True').lower() == 'true'
    FEATURE_MODEL_VERSIONING = os.getenv('FEATURE_MODEL_VERSIONING', 'True').lower() == 'true'


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    LOG_LEVEL = 'DEBUG'
    VERBOSE_LOGGING = True


class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    LOG_LEVEL = 'INFO'
    ENFORCE_HTTPS = True


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
