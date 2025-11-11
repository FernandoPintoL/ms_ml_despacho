"""
Integration Module - Integración de ml-despacho con ms-despacho
Proporciona clientes y loggers para comunicación entre servicios
"""

from .ml_client import MLClient, MLClientPool
from .prediction_logger import PredictionLogger, PredictionMetrics

__all__ = [
    'MLClient',
    'MLClientPool',
    'PredictionLogger',
    'PredictionMetrics'
]
