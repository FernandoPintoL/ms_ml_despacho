# GUÍA DE INTEGRACIÓN - FASE 3, PASO 1

## Integración de ml-despacho con ms-despacho

**Objetivo:** Conectar el servicio ML con ms-despacho para obtener predicciones en tiempo real.

---

## ARQUITECTURA DE INTEGRACIÓN

```
┌──────────────────────┐
│   ms-despacho        │
│   (Central)          │
└──────────┬───────────┘
           │
           │ HTTP Request
           │ POST /api/v2/dispatch/predict
           │
┌──────────▼───────────────────┐
│   ml-despacho                │
│   (ML Service)               │
│                              │
│ ┌────────────────────────┐  │
│ │ XGBoost Model          │  │
│ │ (90% Accuracy)         │  │
│ └────────────────────────┘  │
│                              │
│ ┌────────────────────────┐  │
│ │ Fallback (Fase 1)      │  │
│ │ Deterministic Rules    │  │
│ └────────────────────────┘  │
└──────────┬───────────────────┘
           │
           │ HTTP Response
           │ Prediction + Confidence
           │
┌──────────▼───────────────────┐
│   SQL Server                 │
│   ml.predictions_log         │
│   ml.assignment_history      │
└──────────────────────────────┘
```

---

## MÓDULOS CREADOS

### 1. MLClient (`src/integration/ml_client.py`)

Cliente HTTP para comunicarse con el servicio ML.

**Características:**
- Predicciones individuales
- Predicciones en lote
- Health check
- Fallback automático a Fase 1
- Pool de conexiones

**Uso:**
```python
from src.integration import MLClient

# Crear cliente
client = MLClient(
    ml_service_url='http://localhost:5000',
    timeout=5,
    fallback_to_v1=True
)

# Verificar salud del servicio
if client.check_health():
    print("ML service is healthy")

# Hacer predicción
features = {
    'dispatch_id': 123,
    'severity_level': 4,
    'hour_of_day': 14,
    # ... 15 features más
}

result = client.predict(features)
print(f"Prediction: {result['prediction']}")  # 0 o 1
print(f"Confidence: {result['confidence']}")  # 0.0-1.0
print(f"Recommendation: {result['recommendation']}")
```

### 2. PredictionLogger (`src/integration/prediction_logger.py`)

Logger centralizado para registrar todas las predicciones y outcomes.

**Características:**
- Log de predicciones
- Log de outcomes
- Estadísticas de predicciones
- Comparativa Fase 1 vs Fase 2

**Uso:**
```python
from src.integration import PredictionLogger

# Crear logger
logger = PredictionLogger(
    server='192.168.1.38',
    database='ms_ml_despacho',
    username='sa',
    password='1234'
)

if logger.connect():
    # Log de predicción
    logger.log_prediction(
        dispatch_id=123,
        phase=2,
        prediction=1,
        confidence=0.95,
        features=features_dict,
        recommendation="ASSIGN"
    )

    # Log de outcome (después, cuando se completa)
    logger.log_outcome(
        dispatch_id=123,
        actual_response_time=4.5,
        was_optimal=1,
        patient_satisfaction=5
    )

    # Obtener estadísticas
    stats = logger.get_statistics(hours=24)
    print(f"Predicciones ML (24h): {stats['ml_predictions']}")
    print(f"Tasa fallback: {stats['fallback_rate']:.2f}%")
```

---

## FLUJO DE INTEGRACIÓN

### Paso 1: Desde ms-despacho

```python
# En ms-despacho, al recibir una solicitud de despacho:
from src.integration import MLClient, PredictionLogger

# 1. Crear cliente
ml_client = MLClient()

# 2. Preparar features
ml_features = {
    'dispatch_id': request.dispatch_id,
    'severity_level': request.severity,
    'hour_of_day': datetime.now().hour,
    # ... 15 features más del contexto de la solicitud
}

# 3. Obtener predicción
prediction_result = ml_client.predict(ml_features)

# 4. Usar la predicción
if prediction_result['success']:
    if prediction_result['phase'] == 2:
        # Usar predicción de ML
        confidence = prediction_result['confidence']
        recommendation = prediction_result['recommendation']
    else:
        # Fallback a Fase 1 (reglas determinísticas)
        confidence = 0.8  # Confianza por defecto
        recommendation = prediction_result['recommendation']

    # 5. Registrar predicción
    logger.log_prediction(
        dispatch_id=request.dispatch_id,
        phase=prediction_result.get('phase', 1),
        prediction=prediction_result['prediction'],
        confidence=confidence,
        features=ml_features,
        recommendation=recommendation,
        fallback=prediction_result.get('fallback', False)
    )

    # 6. Tomar decisión
    if prediction_result['prediction'] == 1:
        # Predicción óptima - proceder
        assign_ambulance(...)
    else:
        # Predicción no óptima - revisar manualmente
        request_manual_review(...)
```

### Paso 2: Registrar Outcome (después de completar despacho)

```python
# Cuando se complete la asignación:
logger.log_outcome(
    dispatch_id=request.dispatch_id,
    actual_response_time=response_time_minutes,
    was_optimal=1 if met_criteria else 0,
    patient_satisfaction=patient_rating,
    paramedic_satisfaction=paramedic_rating
)
```

---

## CONFIGURACIÓN DE ms-despacho

### Instalación de dependencia

```bash
# En ms-despacho, instalar requests
pip install requests
```

### Configuración en .env

```env
# ML Service Configuration
ML_SERVICE_URL=http://ml-despacho:5000
ML_SERVICE_TIMEOUT=5
ML_FALLBACK_ENABLED=true
```

### Integración en código

```python
# En ms-despacho/src/services/dispatch_service.py

import os
from src.integration.ml_client import MLClient

class DispatchService:
    def __init__(self):
        self.ml_client = MLClient(
            ml_service_url=os.getenv('ML_SERVICE_URL', 'http://localhost:5000'),
            timeout=int(os.getenv('ML_SERVICE_TIMEOUT', 5)),
            fallback_to_v1=os.getenv('ML_FALLBACK_ENABLED', 'true').lower() == 'true'
        )

    def assign_ambulance(self, dispatch_request):
        """Asignar ambulancia usando ML"""

        # Preparar features
        features = self._prepare_ml_features(dispatch_request)

        # Obtener predicción
        result = self.ml_client.predict(features)

        if result['success']:
            if result['prediction'] == 1:
                return self._proceed_with_assignment(dispatch_request)
            else:
                return self._request_review(dispatch_request)
        else:
            # Fallback manual
            return self._manual_assignment(dispatch_request)
```

---

## MANEJO DE ERRORES

### Escenarios y Soluciones

**Escenario 1: Servicio ML no responde**
```
→ Fallback automático a Fase 1
→ Log del error
→ Alerta a administrador
→ Reintentar después de 60 segundos
```

**Escenario 2: Predicción tarda demasiado (> timeout)**
```
→ Usar Fase 1 inmediatamente
→ Log de timeout
→ Continuar operación
```

**Escenario 3: Modelo degradado (baja confianza)**
```
→ Si confianza < 0.6 → Usar Fase 1
→ Si confianza 0.6-0.8 → Usar con supervisión
→ Si confianza > 0.8 → Usar normalmente
```

---

## MONITOREO

### Endpoints de Salud

```bash
# Health check
curl http://localhost:5000/api/v2/dispatch/health

# Response:
{
  "status": "healthy",
  "service": "dispatch_assignment_ml",
  "phase": 2,
  "version": "2.0.0",
  "ml_status": "loaded"
}
```

### Estadísticas en BD

```sql
-- Ver predicciones recientes
SELECT TOP 10
    dispatch_id, phase, prediction, confidence,
    recommendation, used_fallback, created_at
FROM ml.predictions_log
ORDER BY created_at DESC

-- Ver tasa de uso por fase
SELECT
    phase,
    COUNT(*) as count,
    COUNT(*) * 100.0 / (SELECT COUNT(*) FROM ml.predictions_log) as percentage
FROM ml.predictions_log
WHERE created_at > DATEADD(day, -1, GETDATE())
GROUP BY phase

-- Ver tasa de fallback
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN used_fallback = 1 THEN 1 ELSE 0 END) as fallback_count,
    SUM(CASE WHEN used_fallback = 1 THEN 1 ELSE 0 END) * 100.0 /
        COUNT(*) as fallback_percentage
FROM ml.predictions_log
WHERE created_at > DATEADD(day, -1, GETDATE())
```

---

## TESTING

### Test unitario

```python
import unittest
from src.integration.ml_client import MLClient

class TestMLClient(unittest.TestCase):

    def setUp(self):
        self.client = MLClient()

    def test_health_check(self):
        result = self.client.check_health()
        self.assertIsInstance(result, bool)

    def test_predict(self):
        features = {
            'dispatch_id': 999,
            'severity_level': 4,
            # ... 16 features más
        }
        result = self.client.predict(features)
        self.assertTrue('success' in result)
        self.assertTrue('prediction' in result)
```

### Test de integración

```bash
# Iniciar ml-despacho
python src/main.py

# En otra terminal, ejecutar tests
python -m src.integration.ml_client
python -m src.integration.prediction_logger
```

---

## MÉTRICAS A MONITOREAR

1. **Disponibilidad del servicio ML**
   - % uptime
   - Tiempo de respuesta promedio
   - Timeouts (< 1%)

2. **Precisión de predicciones**
   - Accuracy vs outcomes reales
   - Precision y Recall
   - Confusion matrix

3. **Adopción de Fase 2**
   - % de predicciones usando ML
   - % de fallbacks (meta: < 5%)
   - Confianza promedio

4. **Impacto en negocio**
   - Tiempo de respuesta promedio
   - Tasa de optimalidad
   - Satisfacción de pacientes
   - Satisfacción de paramedics

---

## TROUBLESHOOTING

### Problema: "Connection refused"
```
Solución:
1. Verificar que ml-despacho está ejecutándose
2. Verificar URL y puerto correcto
3. Verificar firewall
```

### Problema: "Timeout"
```
Solución:
1. Aumentar timeout en MLClient (timeout=10)
2. Verificar performance de ml-despacho
3. Verificar carga de red
```

### Problema: "Model not loaded"
```
Solución:
1. Verificar que modelo existe: src/models/xgboost_model.pkl
2. Reiniciar servicio
3. Reentrenar modelo
```

---

## PRÓXIMOS PASOS

- Paso 2: A/B Testing Framework
- Paso 3: Monitoreo y Alertas
- Paso 4: Recopilación de Datos Reales

---

**Status:** Fase 3, Paso 1 - COMPLETO
**Archivos generados:**
- `src/integration/ml_client.py` (400 líneas)
- `src/integration/prediction_logger.py` (450 líneas)
- `src/integration/__init__.py`
