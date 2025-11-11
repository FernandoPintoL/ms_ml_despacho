"""
Model Trainer - Entrenar modelo XGBoost para Fase 2
Entrena clasificador XGBoost con validacion cruzada y tuning de hiperparametros
"""

import pandas as pd
import numpy as np
import pyodbc
import joblib
import logging
from datetime import datetime
from typing import Tuple, Dict, List

from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report
)
import xgboost as xgb

logger = logging.getLogger(__name__)


class ModelTrainer:
    """Entrena modelo XGBoost para clasificación de optimalidad"""

    def __init__(self, server: str, database: str, username: str, password: str):
        """
        Inicializar trainer

        Args:
            server: Servidor SQL Server
            database: Nombre de BD
            username: Usuario
            password: Contraseña
        """
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.connection = None
        self.df = None
        self.X_train = None
        self.X_test = None
        self.y_train = None
        self.y_test = None
        self.model = None
        self.scaler = None

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
            logger.info(f"Conectado a {self.database}")
            return True
        except Exception as e:
            logger.error(f"Error conectando: {e}")
            return False

    def load_data(self) -> bool:
        """Cargar datos desde BD"""
        if not self.connection:
            if not self.connect():
                return False

        try:
            # Cargar todos los datos disponibles
            query = """
            SELECT
                severity_level, hour_of_day, day_of_week, is_weekend,
                available_ambulances_count, nearest_ambulance_distance_km,
                paramedics_available_count, paramedics_senior_count,
                paramedics_junior_count, nurses_available_count,
                active_dispatches_count, ambulances_busy_percentage,
                average_response_time_minutes, actual_response_time_minutes,
                actual_travel_distance_km, optimization_score,
                paramedic_satisfaction_rating, patient_satisfaction_rating,
                was_optimal
            FROM ml.assignment_history
            """

            self.df = pd.read_sql(query, self.connection)
            logger.info(f"Cargados {len(self.df)} registros para entrenamiento")
            return True

        except Exception as e:
            logger.error(f"Error cargando datos: {e}")
            return False

    def disconnect(self):
        """Cerrar conexión"""
        if self.connection:
            self.connection.close()

    def prepare_data(self, test_size: float = 0.2) -> bool:
        """
        Preparar datos para entrenamiento

        Args:
            test_size: Proporción de datos para test

        Returns:
            True si fue exitoso
        """
        if self.df is None:
            return False

        try:
            # Separar features y target
            X = self.df.drop('was_optimal', axis=1)
            y = self.df['was_optimal']

            logger.info(f"Features: {X.shape[1]}")
            logger.info(f"Target distribution: {y.value_counts().to_dict()}")

            # Split de datos
            self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
                X, y, test_size=test_size, random_state=42, stratify=y
            )

            # Normalizar features
            self.scaler = StandardScaler()
            self.X_train = self.scaler.fit_transform(self.X_train)
            self.X_test = self.scaler.transform(self.X_test)

            logger.info(f"Train set: {self.X_train.shape}")
            logger.info(f"Test set: {self.X_test.shape}")

            return True

        except Exception as e:
            logger.error(f"Error preparando datos: {e}")
            return False

    def train_baseline_model(self) -> Dict:
        """
        Entrenar modelo baseline con hyperparameters por defecto

        Returns:
            Diccionario con métricas
        """
        print("\n" + "=" * 70)
        print("ENTRENANDO MODELO BASELINE")
        print("=" * 70)

        # Crear modelo con parámetros iniciales
        self.model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric='logloss'
        )

        # Entrenar
        self.model.fit(
            self.X_train, self.y_train,
            eval_set=[(self.X_test, self.y_test)],
            verbose=False
        )

        # Evaluar
        y_pred = self.model.predict(self.X_test)
        y_pred_proba = self.model.predict_proba(self.X_test)[:, 1]

        metrics = {
            'accuracy': accuracy_score(self.y_test, y_pred),
            'precision': precision_score(self.y_test, y_pred),
            'recall': recall_score(self.y_test, y_pred),
            'f1': f1_score(self.y_test, y_pred),
            'auc': roc_auc_score(self.y_test, y_pred_proba)
        }

        print(f"\nAccuracy:  {metrics['accuracy']:.4f}")
        print(f"Precision: {metrics['precision']:.4f}")
        print(f"Recall:    {metrics['recall']:.4f}")
        print(f"F1-Score:  {metrics['f1']:.4f}")
        print(f"AUC-ROC:   {metrics['auc']:.4f}")

        return metrics

    def hyperparameter_tuning(self) -> Dict:
        """
        Hacer tuning de hiperparámetros con GridSearchCV

        Returns:
            Diccionario con mejores parámetros y métricas
        """
        print("\n" + "=" * 70)
        print("TUNING DE HIPERPARAMETROS")
        print("=" * 70)

        param_grid = {
            'n_estimators': [100, 200, 300],
            'max_depth': [3, 5, 7],
            'learning_rate': [0.05, 0.1, 0.2],
            'subsample': [0.7, 0.8, 0.9],
            'colsample_bytree': [0.7, 0.8, 0.9]
        }

        base_model = xgb.XGBClassifier(random_state=42, eval_metric='logloss')

        grid_search = GridSearchCV(
            base_model,
            param_grid,
            cv=5,
            scoring='f1',
            n_jobs=-1,
            verbose=1
        )

        print(f"Buscando en {len(param_grid['n_estimators']) * len(param_grid['max_depth']) * len(param_grid['learning_rate']) * len(param_grid['subsample']) * len(param_grid['colsample_bytree'])} combinaciones...")

        grid_search.fit(self.X_train, self.y_train)

        print(f"\nMejores parámetros: {grid_search.best_params_}")
        print(f"Mejor F1-Score (CV): {grid_search.best_score_:.4f}")

        # Entrenar con los mejores parámetros
        self.model = grid_search.best_estimator_

        # Evaluar en test set
        y_pred = self.model.predict(self.X_test)
        y_pred_proba = self.model.predict_proba(self.X_test)[:, 1]

        metrics = {
            'accuracy': accuracy_score(self.y_test, y_pred),
            'precision': precision_score(self.y_test, y_pred),
            'recall': recall_score(self.y_test, y_pred),
            'f1': f1_score(self.y_test, y_pred),
            'auc': roc_auc_score(self.y_test, y_pred_proba),
            'best_params': grid_search.best_params_
        }

        print(f"\nMétricas en Test Set:")
        print(f"Accuracy:  {metrics['accuracy']:.4f}")
        print(f"Precision: {metrics['precision']:.4f}")
        print(f"Recall:    {metrics['recall']:.4f}")
        print(f"F1-Score:  {metrics['f1']:.4f}")
        print(f"AUC-ROC:   {metrics['auc']:.4f}")

        return metrics

    def evaluate_model(self) -> Dict:
        """
        Evaluar modelo en detalle

        Returns:
            Diccionario con métricas detalladas
        """
        print("\n" + "=" * 70)
        print("EVALUACION DETALLADA DEL MODELO")
        print("=" * 70)

        y_pred = self.model.predict(self.X_test)
        y_pred_proba = self.model.predict_proba(self.X_test)[:, 1]

        # Métricas
        accuracy = accuracy_score(self.y_test, y_pred)
        precision = precision_score(self.y_test, y_pred)
        recall = recall_score(self.y_test, y_pred)
        f1 = f1_score(self.y_test, y_pred)
        auc = roc_auc_score(self.y_test, y_pred_proba)

        # Matriz de confusión
        cm = confusion_matrix(self.y_test, y_pred)
        tn, fp, fn, tp = cm.ravel()

        print(f"\nMerica                 Valor")
        print("-" * 40)
        print(f"Accuracy               {accuracy:.4f}")
        print(f"Precision              {precision:.4f}")
        print(f"Recall                 {recall:.4f}")
        print(f"F1-Score               {f1:.4f}")
        print(f"AUC-ROC                {auc:.4f}")

        print(f"\nMatriz de Confusión:")
        print(f"  True Negatives:  {tn}")
        print(f"  False Positives: {fp}")
        print(f"  False Negatives: {fn}")
        print(f"  True Positives:  {tp}")

        # Feature importance
        print(f"\nTop 10 Features Más Importantes:")
        print("-" * 40)
        feature_importance = pd.DataFrame({
            'feature': self.df.drop('was_optimal', axis=1).columns,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)

        for idx, row in feature_importance.head(10).iterrows():
            print(f"{row['feature']:40s} {row['importance']:.4f}")

        # Validación de criterios de éxito
        print(f"\nValidacion de Criterios de Exito:")
        print("-" * 40)
        print(f"Accuracy >= 0.75:     {accuracy >= 0.75} ({accuracy:.4f})")
        print(f"Precision >= 0.70:    {precision >= 0.70} ({precision:.4f})")
        print(f"Recall >= 0.70:       {recall >= 0.70} ({recall:.4f})")
        print(f"AUC >= 0.80:          {auc >= 0.80} ({auc:.4f})")

        metrics = {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'auc': auc,
            'confusion_matrix': cm.tolist(),
            'feature_importance': feature_importance.to_dict('records')
        }

        return metrics

    def save_model(self, path: str = 'src/models/xgboost_model.pkl') -> bool:
        """
        Guardar modelo entrenado

        Args:
            path: Ruta donde guardar el modelo

        Returns:
            True si fue exitoso
        """
        try:
            joblib.dump(self.model, path)
            logger.info(f"Modelo guardado en {path}")

            # También guardar el scaler
            scaler_path = path.replace('.pkl', '_scaler.pkl')
            joblib.dump(self.scaler, scaler_path)
            logger.info(f"Scaler guardado en {scaler_path}")

            return True
        except Exception as e:
            logger.error(f"Error guardando modelo: {e}")
            return False

    def train(self, use_tuning: bool = True) -> bool:
        """
        Pipeline completo de entrenamiento

        Args:
            use_tuning: Si hacer hyperparameter tuning

        Returns:
            True si fue exitoso
        """
        print("\n" + "=" * 70)
        print("PIPELINE DE ENTRENAMIENTO - XGBOOST")
        print("=" * 70)

        # Cargar datos
        if not self.load_data():
            return False

        # Preparar datos
        if not self.prepare_data():
            return False

        # Entrenar modelo baseline
        baseline_metrics = self.train_baseline_model()

        # Tuning de hiperparámetros (opcional)
        if use_tuning:
            tuning_metrics = self.hyperparameter_tuning()
        else:
            tuning_metrics = baseline_metrics

        # Evaluar
        eval_metrics = self.evaluate_model()

        # Guardar modelo
        if not self.save_model():
            return False

        print("\n" + "=" * 70)
        print("ENTRENAMIENTO COMPLETADO")
        print("=" * 70)

        return True


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    trainer = ModelTrainer(
        server='192.168.1.38',
        database='ms_ml_despacho',
        username='sa',
        password='1234'
    )

    if trainer.train(use_tuning=True):
        trainer.disconnect()
        print("\nModelo entrenado exitosamente!")
    else:
        print("\nError durante el entrenamiento")
