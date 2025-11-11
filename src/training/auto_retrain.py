"""
Automatic Retraining Pipeline - Reentrenamiento automatico de modelos
Recopila datos, entrena nuevos modelos, valida y deploya
"""

import logging
import os
import sys
from typing import Dict, Tuple, Optional
from datetime import datetime
import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
import pyodbc

logger = logging.getLogger(__name__)


class ModelVersionManager:
    """Gestor de versiones de modelos"""

    def __init__(self, models_dir: str = 'src/models'):
        self.models_dir = models_dir
        self.model_file = os.path.join(models_dir, 'xgboost_model.pkl')
        self.scaler_file = os.path.join(models_dir, 'xgboost_model_scaler.pkl')
        self.metadata_file = os.path.join(models_dir, 'model_metadata.pkl')

    def save_model_version(self, model: XGBClassifier, scaler: StandardScaler,
                          version: int, metrics: Dict) -> bool:
        """Guardar versión de modelo"""
        try:
            # Create backup of current model
            if os.path.exists(self.model_file):
                backup_model = os.path.join(
                    self.models_dir,
                    f'xgboost_model_v{version-1}.pkl.backup'
                )
                backup_scaler = os.path.join(
                    self.models_dir,
                    f'xgboost_model_scaler_v{version-1}.pkl.backup'
                )
                if not os.path.exists(backup_model):
                    joblib.dump(joblib.load(self.model_file), backup_model)
                    joblib.dump(joblib.load(self.scaler_file), backup_scaler)

            # Save new model
            joblib.dump(model, self.model_file)
            joblib.dump(scaler, self.scaler_file)

            # Save metadata
            metadata = {
                'version': version,
                'timestamp': datetime.now().isoformat(),
                'metrics': metrics,
                'training_samples': metrics.get('training_samples', 0)
            }
            joblib.dump(metadata, self.metadata_file)

            logger.info(f"Model version {version} saved successfully")
            return True

        except Exception as e:
            logger.error(f"Error saving model version: {e}")
            return False

    def load_model(self) -> Tuple[Optional[XGBClassifier], Optional[StandardScaler]]:
        """Cargar modelo actual"""
        try:
            if os.path.exists(self.model_file) and os.path.exists(self.scaler_file):
                model = joblib.load(self.model_file)
                scaler = joblib.load(self.scaler_file)
                logger.info("Model loaded successfully")
                return model, scaler
            return None, None
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return None, None

    def get_model_metadata(self) -> Optional[Dict]:
        """Obtener metadata del modelo"""
        try:
            if os.path.exists(self.metadata_file):
                return joblib.load(self.metadata_file)
            return None
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")
            return None


class AutomaticRetrainingPipeline:
    """
    Pipeline de reentrenamiento automático
    Recopila datos, entrena, valida y deploya
    """

    def __init__(self, server: str, database: str, username: str, password: str,
                 models_dir: str = 'src/models'):
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.connection = None
        self.model_manager = ModelVersionManager(models_dir)

        # Hiperparámetros del modelo
        self.model_params = {
            'n_estimators': 100,
            'max_depth': 6,
            'learning_rate': 0.1,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'random_state': 42
        }

        # Criterios de validación
        self.min_accuracy = 0.88  # No retrain si accuracy < 88%
        self.min_samples = 200     # Mínimo 200 muestras para reentrenar

    def connect(self) -> bool:
        """Establecer conexión a BD"""
        try:
            connection_string = (
                f'DRIVER={{ODBC Driver 17 for SQL Server}};'
                f'SERVER={self.server};'
                f'DATABASE={self.database};'
                f'UID={self.username};'
                f'PWD={self.password}'
            )
            self.connection = pyodbc.connect(connection_string, timeout=10)
            logger.info("Connected to database for retraining")
            return True
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            return False

    def disconnect(self):
        """Cerrar conexión"""
        if self.connection:
            self.connection.close()

    def fetch_training_data(self, hours: int = 168) -> Tuple[pd.DataFrame, int]:
        """
        Obtener datos para reentrenamiento

        Args:
            hours: Período en horas

        Returns:
            Tupla (DataFrame, count)
        """
        if not self.connection:
            if not self.connect():
                return pd.DataFrame(), 0

        try:
            cursor = self.connection.cursor()

            query = """
            SELECT TOP 1000
                dispatch_id, prediction, actual, confidence,
                features_json, validated_at
            FROM ml.prediction_validation
            WHERE validated_at > DATEADD(hour, -?, GETDATE())
            AND is_correct = 1
            ORDER BY validated_at DESC
            """

            cursor.execute(query, (hours,))
            rows = cursor.fetchall()
            cursor.close()

            if not rows:
                logger.warning(f"No training data found for {hours}h")
                return pd.DataFrame(), 0

            # Convertir a DataFrame
            data = []
            for row in rows:
                try:
                    import json
                    features = json.loads(row[4]) if row[4] else {}
                    record = {
                        'dispatch_id': row[0],
                        'prediction': row[1],
                        'actual': row[2],
                        'confidence': row[3],
                        'validated_at': row[5]
                    }
                    # Agregar features
                    record.update(features)
                    data.append(record)
                except:
                    continue

            df = pd.DataFrame(data)
            logger.info(f"Fetched {len(df)} training records")
            return df, len(df)

        except Exception as e:
            logger.error(f"Error fetching training data: {e}")
            return pd.DataFrame(), 0

    def prepare_data(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, StandardScaler, list]:
        """
        Preparar datos para entrenamiento

        Args:
            df: DataFrame con datos crudos

        Returns:
            Tupla (X, y, scaler, feature_names)
        """
        try:
            # Feature engineering (se asume que ya vienen procesadas)
            # Ordenar columnas esperadas
            feature_cols = [
                'severity_level', 'hour_of_day', 'day_of_week',
                'patient_age', 'patient_satisfaction', 'paramedic_satisfaction',
                'distance_km', 'response_time_minutes', 'available_ambulances',
                'senior_paramedics', 'junior_paramedics', 'availability_index',
                'peak_hours', 'traffic_level'
            ]

            # Usar solo features que existan
            available_features = [col for col in feature_cols if col in df.columns]

            X = df[available_features].fillna(df[available_features].mean()).values
            y = df['actual'].values

            # Normalizar
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            logger.info(f"Data prepared: {X_scaled.shape[0]} samples, {X_scaled.shape[1]} features")
            return X_scaled, y, scaler, available_features

        except Exception as e:
            logger.error(f"Error preparing data: {e}")
            return np.array([]), np.array([]), StandardScaler(), []

    def train_model(self, X: np.ndarray, y: np.ndarray) -> Tuple[XGBClassifier, Dict]:
        """
        Entrenar modelo

        Args:
            X: Features
            y: Target

        Returns:
            Tupla (modelo, métricas)
        """
        try:
            # Entrenar modelo
            model = XGBClassifier(**self.model_params)
            model.fit(X, y, verbose=False)

            # Evaluar
            y_pred = model.predict(X)
            y_pred_proba = model.predict_proba(X)[:, 1]

            metrics = {
                'accuracy': accuracy_score(y, y_pred),
                'precision': precision_score(y, y_pred, zero_division=0),
                'recall': recall_score(y, y_pred, zero_division=0),
                'auc': roc_auc_score(y, y_pred_proba),
                'training_samples': len(X)
            }

            logger.info(f"Model trained: Accuracy={metrics['accuracy']:.4f}, AUC={metrics['auc']:.4f}")
            return model, metrics

        except Exception as e:
            logger.error(f"Error training model: {e}")
            return None, {}

    def validate_model(self, current_metrics: Dict, new_metrics: Dict) -> Dict:
        """
        Validar si nuevo modelo es mejor

        Args:
            current_metrics: Métricas del modelo actual
            new_metrics: Métricas del nuevo modelo

        Returns:
            Diccionario con validación
        """
        validation = {
            'is_better': False,
            'reason': 'No model to compare',
            'improvements': {}
        }

        if not current_metrics:
            # Primer modelo
            validation['is_better'] = new_metrics.get('accuracy', 0) >= self.min_accuracy
            validation['reason'] = 'First model' if validation['is_better'] else f"Accuracy {new_metrics.get('accuracy', 0):.4f} < {self.min_accuracy}"
            return validation

        # Comparar con modelo actual
        acc_improvement = new_metrics.get('accuracy', 0) - current_metrics.get('accuracy', 0)
        prec_improvement = new_metrics.get('precision', 0) - current_metrics.get('precision', 0)
        recall_improvement = new_metrics.get('recall', 0) - current_metrics.get('recall', 0)

        validation['improvements'] = {
            'accuracy': round(acc_improvement, 4),
            'precision': round(prec_improvement, 4),
            'recall': round(recall_improvement, 4)
        }

        # Criterios de validación
        if new_metrics.get('accuracy', 0) < self.min_accuracy:
            validation['reason'] = f"Accuracy below threshold ({self.min_accuracy})"
        elif acc_improvement < -0.02:  # Caída de más del 2%
            validation['reason'] = "Accuracy decreased significantly"
        elif new_metrics.get('training_samples', 0) < self.min_samples:
            validation['reason'] = f"Insufficient samples ({self.min_samples} required)"
        else:
            validation['is_better'] = True
            validation['reason'] = "Model improvements validated"

        return validation

    def run_retraining_pipeline(self, hours: int = 168) -> Dict:
        """
        Ejecutar pipeline completo de reentrenamiento

        Args:
            hours: Período de datos para reentrenamiento

        Returns:
            Diccionario con resultado del pipeline
        """
        logger.info("Starting automatic retraining pipeline...")

        result = {
            'timestamp': datetime.now().isoformat(),
            'status': 'FAILED',
            'stages': {}
        }

        try:
            # Stage 1: Fetch data
            logger.info("Stage 1: Fetching training data...")
            df, count = self.fetch_training_data(hours)
            result['stages']['fetch_data'] = {
                'status': 'SUCCESS' if count >= self.min_samples else 'INSUFFICIENT',
                'samples_count': count,
                'required': self.min_samples
            }

            if count < self.min_samples:
                result['reason'] = f"Insufficient data ({count} < {self.min_samples})"
                return result

            # Stage 2: Prepare data
            logger.info("Stage 2: Preparing data...")
            X, y, scaler, features = self.prepare_data(df)
            result['stages']['prepare_data'] = {
                'status': 'SUCCESS',
                'samples': len(X),
                'features': len(features)
            }

            # Stage 3: Train model
            logger.info("Stage 3: Training model...")
            new_model, new_metrics = self.train_model(X, y)
            if new_model is None:
                result['stages']['train_model'] = {'status': 'FAILED'}
                return result

            result['stages']['train_model'] = {
                'status': 'SUCCESS',
                'metrics': new_metrics
            }

            # Stage 4: Validate model
            logger.info("Stage 4: Validating model...")
            current_metadata = self.model_manager.get_model_metadata()
            current_metrics = current_metadata.get('metrics', {}) if current_metadata else {}

            validation = self.validate_model(current_metrics, new_metrics)
            result['stages']['validate_model'] = {
                'status': 'SUCCESS',
                'is_better': validation['is_better'],
                'reason': validation['reason'],
                'improvements': validation['improvements']
            }

            # Stage 5: Deploy model
            if validation['is_better']:
                logger.info("Stage 5: Deploying model...")
                version = (current_metadata.get('version', 0) + 1) if current_metadata else 1
                deployed = self.model_manager.save_model_version(new_model, scaler, version, new_metrics)

                result['stages']['deploy_model'] = {
                    'status': 'SUCCESS' if deployed else 'FAILED',
                    'version': version
                }

                result['status'] = 'SUCCESS'
            else:
                result['stages']['deploy_model'] = {
                    'status': 'SKIPPED',
                    'reason': 'Model did not pass validation'
                }

            logger.info(f"Retraining pipeline completed: {result['status']}")
            return result

        except Exception as e:
            logger.error(f"Error in retraining pipeline: {e}")
            result['error'] = str(e)
            return result

    def schedule_daily_retraining(self, hour: int = 2) -> str:
        """
        Schedule retraining to run daily at specific hour

        Args:
            hour: Hour of day (0-23)

        Returns:
            Instrucciones para scheduling
        """
        return f"""
Schedule the retraining pipeline to run daily at {hour}:00 AM using:

Option 1: Python APScheduler
```python
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()
scheduler.add_job(pipeline.run_retraining_pipeline, 'cron', hour={hour})
scheduler.start()
```

Option 2: Windows Task Scheduler
```
schtasks /create /tn "AutoMLRetrain" /tr "python src/training/auto_retrain.py" /sc daily /st {hour}:00:00
```

Option 3: Linux Cron
```
0 {hour} * * * cd /path/to/project && python src/training/auto_retrain.py
```
"""


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    pipeline = AutomaticRetrainingPipeline(
        server='192.168.1.38',
        database='ms_ml_despacho',
        username='sa',
        password='1234'
    )

    print("\n=== AUTOMATIC RETRAINING PIPELINE TEST ===\n")

    if pipeline.connect():
        # Run pipeline
        result = pipeline.run_retraining_pipeline(hours=168)
        print(f"Pipeline status: {result['status']}")
        for stage, details in result['stages'].items():
            print(f"  {stage}: {details.get('status')}")

        pipeline.disconnect()
    else:
        print("Failed to connect to database")

    print("\n=== TEST COMPLETE ===\n")
