"""
Retraining API
REST endpoints para gestion de reentrenamiento automatico
"""

from flask import Blueprint, jsonify, request
import logging
import sys
import os
import threading

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from training.auto_retrain import AutomaticRetrainingPipeline

logger = logging.getLogger(__name__)

# Crear blueprint
retraining_bp = Blueprint(
    'retraining',
    __name__,
    url_prefix='/api/v6/retraining'
)

# Instancia global
_pipeline = None
_retraining_in_progress = False


def get_pipeline():
    """Obtener o inicializar pipeline"""
    global _pipeline
    if _pipeline is None:
        _pipeline = AutomaticRetrainingPipeline(
            server='192.168.1.38',
            database='ms_ml_despacho',
            username='sa',
            password='1234'
        )
    return _pipeline


# ============================================
# RETRAINING ENDPOINTS
# ============================================

@retraining_bp.route('/run', methods=['POST'])
def run_retraining():
    """
    Ejecutar pipeline de reentrenamiento

    POST /api/v6/retraining/run
    Body: {"hours": 168}
    """
    global _retraining_in_progress

    if _retraining_in_progress:
        return jsonify({
            'success': False,
            'error': 'Retraining already in progress'
        }), 409

    try:
        data = request.get_json() or {}
        hours = data.get('hours', 168)

        _retraining_in_progress = True
        pipeline = get_pipeline()

        if not pipeline.connection:
            pipeline.connect()

        # Run in background thread
        thread = threading.Thread(
            target=_run_retraining_background,
            args=(pipeline, hours)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Retraining pipeline started',
            'hours': hours,
            'check_status_at': '/api/v6/retraining/status'
        }), 202

    except Exception as e:
        logger.error(f"Error starting retraining: {e}")
        _retraining_in_progress = False
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _run_retraining_background(pipeline, hours):
    """Ejecutar reentrenamiento en background"""
    global _retraining_in_progress
    try:
        pipeline.run_retraining_pipeline(hours)
    finally:
        _retraining_in_progress = False


@retraining_bp.route('/status', methods=['GET'])
def get_retraining_status():
    """
    Obtener estado del reentrenamiento

    GET /api/v6/retraining/status
    """
    return jsonify({
        'success': True,
        'retraining_in_progress': _retraining_in_progress,
        'timestamp': __import__('datetime').datetime.now().isoformat()
    }), 200


@retraining_bp.route('/history', methods=['GET'])
def get_retraining_history():
    """
    Obtener historial de reentrenamientos

    GET /api/v6/retraining/history?days=30
    """
    pipeline = get_pipeline()

    try:
        metadata = pipeline.model_manager.get_model_metadata()

        history = {
            'current_model': metadata if metadata else None,
            'timestamp': __import__('datetime').datetime.now().isoformat()
        }

        return jsonify({
            'success': True,
            'history': history
        }), 200

    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@retraining_bp.route('/config', methods=['GET', 'POST'])
def manage_retraining_config():
    """
    Obtener o actualizar configuración de reentrenamiento

    GET /api/v6/retraining/config
    POST /api/v6/retraining/config
    Body: {
        "min_accuracy": 0.88,
        "min_samples": 200
    }
    """
    pipeline = get_pipeline()

    if request.method == 'GET':
        config = {
            'min_accuracy': pipeline.min_accuracy,
            'min_samples': pipeline.min_samples,
            'model_params': pipeline.model_params
        }
        return jsonify({
            'success': True,
            'config': config
        }), 200

    elif request.method == 'POST':
        try:
            data = request.get_json() or {}

            if 'min_accuracy' in data:
                pipeline.min_accuracy = float(data['min_accuracy'])
            if 'min_samples' in data:
                pipeline.min_samples = int(data['min_samples'])

            return jsonify({
                'success': True,
                'message': 'Configuration updated',
                'config': {
                    'min_accuracy': pipeline.min_accuracy,
                    'min_samples': pipeline.min_samples
                }
            }), 200

        except Exception as e:
            logger.error(f"Error updating config: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


@retraining_bp.route('/schedule', methods=['GET'])
def get_scheduling_instructions():
    """
    Obtener instrucciones para scheduling automático

    GET /api/v6/retraining/schedule?hour=2
    """
    pipeline = get_pipeline()
    hour = request.args.get('hour', 2, type=int)

    instructions = pipeline.schedule_daily_retraining(hour)

    return jsonify({
        'success': True,
        'instructions': instructions
    }), 200


@retraining_bp.route('/rollback', methods=['POST'])
def rollback_model():
    """
    Rollback al modelo anterior

    POST /api/v6/retraining/rollback
    """
    try:
        pipeline = get_pipeline()
        metadata = pipeline.model_manager.get_model_metadata()

        if not metadata or metadata.get('version', 0) <= 1:
            return jsonify({
                'success': False,
                'error': 'No previous model version available'
            }), 400

        current_version = metadata['version']
        prev_version = current_version - 1

        # Try to restore from backup
        backup_model_path = os.path.join(
            pipeline.model_manager.models_dir,
            f'xgboost_model_v{prev_version}.pkl.backup'
        )
        backup_scaler_path = os.path.join(
            pipeline.model_manager.models_dir,
            f'xgboost_model_scaler_v{prev_version}.pkl.backup'
        )

        if os.path.exists(backup_model_path) and os.path.exists(backup_scaler_path):
            import shutil
            shutil.copy(backup_model_path, pipeline.model_manager.model_file)
            shutil.copy(backup_scaler_path, pipeline.model_manager.scaler_file)

            logger.info(f"Rolled back to model version {prev_version}")
            return jsonify({
                'success': True,
                'message': f'Rolled back to version {prev_version}',
                'previous_version': current_version,
                'rolled_back_to': prev_version
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Backup model files not found'
            }), 500

    except Exception as e:
        logger.error(f"Error in rollback: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("\n=== RETRAINING API TEST ===\n")

    pipeline = get_pipeline()
    if pipeline.connect():
        print("Connected to database")
        config = {
            'min_accuracy': pipeline.min_accuracy,
            'min_samples': pipeline.min_samples
        }
        print(f"Pipeline config: {config}")
        pipeline.disconnect()

    print("\n=== TEST COMPLETE ===\n")
