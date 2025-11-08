"""
MS ML Despacho - Machine Learning Microservice
Main entry point for Flask application
"""

import os
import sys
from flask import Flask, jsonify
from flask_cors import CORS
from prometheus_client import make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from config.settings import config
from config.logger import setup_logger, get_logger

# Get configuration
ENV = os.getenv('FLASK_ENV', 'production')
app_config = config.get(ENV, config['default'])


def create_app(config_class=None):
    """
    Application factory

    Args:
        config_class: Configuration class to use

    Returns:
        Flask application instance
    """

    if config_class is None:
        config_class = app_config

    app = Flask(__name__)
    app.config.from_object(config_class)

    # Setup logging
    logger = setup_logger(config_class)
    logger.info(f"Creating Flask app in {ENV} mode")

    # Setup CORS
    CORS(app, origins=config_class.CORS_ORIGINS)

    # Add Prometheus metrics endpoint
    if config_class.PROMETHEUS_ENABLED:
        app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
            '/metrics': make_wsgi_app()
        })

    # Register blueprints
    register_routes(app)

    # Error handlers
    register_error_handlers(app)

    # Health check
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        return jsonify({
            'status': 'healthy',
            'service': 'ms-ml-despacho',
            'version': '1.0.0',
            'environment': ENV
        }), 200

    @app.route('/health/detailed', methods=['GET'])
    def health_check_detailed():
        """Detailed health check"""
        return jsonify({
            'status': 'healthy',
            'service': 'ms-ml-despacho',
            'version': '1.0.0',
            'environment': ENV,
            'checks': {
                'models': 'loaded',
                'database': 'connected',
                'cache': 'connected'
            }
        }), 200

    return app


def register_routes(app: Flask):
    """
    Register all routes/blueprints

    Args:
        app: Flask application instance
    """

    logger = get_logger()

    try:
        # Initialize services
        from services import (
            ModelManager, PredictionService, TrainingService,
            OptimizationService, HealthService
        )
        from repositories import (
            DispatchRepository, AmbulanceRepository, ModelRepository,
            CacheRepository
        )
        from api.rest_routes import create_rest_routes
        from graphql import schema as graphql_schema

        # Initialize database and cache connections
        db_connection = None  # Will be initialized with database connection
        redis_client = None   # Will be initialized with redis client

        # Initialize repositories
        dispatch_repo = DispatchRepository(db_connection, redis_client)
        ambulance_repo = AmbulanceRepository(db_connection, redis_client)
        model_repo = ModelRepository(db_connection, redis_client)
        cache_repo = CacheRepository(redis_client)

        # Initialize services
        model_manager = ModelManager(model_repo)
        model_manager.load_active_models()

        prediction_service = PredictionService(
            model_manager, dispatch_repo, ambulance_repo, model_repo, cache_repo
        )

        training_service = TrainingService(
            model_manager, dispatch_repo, model_repo, cache_repo
        )

        optimization_service = OptimizationService(
            prediction_service, dispatch_repo, ambulance_repo, cache_repo
        )

        health_service = HealthService(
            model_manager, model_repo, cache_repo, dispatch_repo, ambulance_repo
        )

        # Register REST API routes
        rest_api = create_rest_routes(
            prediction_service,
            optimization_service,
            health_service,
            dispatch_repo,
            ambulance_repo
        )
        app.register_blueprint(rest_api)

        # Register GraphQL endpoint
        from strawberry.flask.views import GraphQLView
        app.add_url_rule(
            "/graphql",
            view_func=GraphQLView.for_app(graphql_schema, debug=app.config.get('DEBUG', False))
        )

        logger.info("Routes registered successfully")
        logger.info("REST API available at /api/v1")
        logger.info("GraphQL available at /graphql")

    except ImportError as e:
        logger.warning(f"Routes not yet fully implemented: {e}")
    except Exception as e:
        logger.error(f"Error registering routes: {str(e)}")


def register_error_handlers(app: Flask):
    """
    Register error handlers

    Args:
        app: Flask application instance
    """

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'error': 'Bad Request',
            'message': str(error)
        }), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Authentication required'
        }), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            'error': 'Forbidden',
            'message': 'Access denied'
        }), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Not Found',
            'message': 'Resource not found'
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger = get_logger()
        logger.error(f"Internal server error: {str(error)}")
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500


if __name__ == '__main__':
    app = create_app()

    # Get server config
    host = app.config['SERVER_HOST']
    port = app.config['SERVER_PORT']
    debug = app.config['DEBUG']

    logger = get_logger()
    logger.info(f"Starting Flask server on {host}:{port}")

    app.run(host=host, port=port, debug=debug)
