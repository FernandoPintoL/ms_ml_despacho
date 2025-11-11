# API ENDPOINTS REFERENCE

Guía completa de todos los endpoints disponibles en el microservicio ML.

---

## FASE 1: DISPATCH ASSIGNMENT (v1)

Base URL: `http://localhost:5000/api/v1/dispatch`

### Endpoints

| Método | Endpoint | Descripción | Parámetros |
|--------|----------|-------------|-----------|
| GET | `/health` | Verificar salud del servicio | Ninguno |
| POST | `/assign` | Asignar ambulancia (reglas determinísticas) | JSON body |
| GET | `/test` | Test endpoint | Ninguno |

### Ejemplo: Assign Ambulance
```bash
curl -X POST http://localhost:5000/api/v1/dispatch/assign \
  -H "Content-Type: application/json" \
  -d '{
    "dispatch_id": 123,
    "patient_latitude": 4.7110,
    "patient_longitude": -74.0721,
    "severity_level": 4,
    "zone_code": "ZONA_1",
    "available_ambulances": [
      {
        "id": 1,
        "latitude": 4.7120,
        "longitude": -74.0700,
        "status": "available",
        "crew_level": "senior",
        "unit_type": "advanced"
      }
    ],
    "available_paramedics": [
      { "id": 1, "level": "senior", "status": "available" }
    ]
  }'
```

---

## FASE 2: ML DISPATCH (v2)

Base URL: `http://localhost:5000/api/v2/dispatch`

### Endpoints

| Método | Endpoint | Descripción | Parámetros |
|--------|----------|-------------|-----------|
| GET | `/health` | Verificar salud del servicio ML | Ninguno |
| POST | `/predict` | Obtener predicción del modelo | JSON body (18 features) |
| POST | `/predict/batch` | Predicciones en lote | JSON array |
| GET | `/model/info` | Información del modelo | Ninguno |
| GET | `/model/feature-importance` | Importancia de features | Ninguno |

### Ejemplo: Predict
```bash
curl -X POST http://localhost:5000/api/v2/dispatch/predict \
  -H "Content-Type: application/json" \
  -d '{
    "dispatch_id": 123,
    "severity_level": 4,
    "hour_of_day": 14,
    "day_of_week": 3,
    "zone_code": "ZONA_1",
    "patient_age": 45,
    "patient_satisfaction": 4,
    "paramedic_satisfaction": 5,
    "distance_km": 2.5,
    "response_time_minutes": 5,
    "available_ambulances": 3,
    "senior_paramedics": 2,
    "junior_paramedics": 1,
    "availability_index": 0.85,
    "peak_hours": 1,
    "weather_condition": "sunny",
    "traffic_level": "moderate",
    "hospital_distance_km": 8
  }'
```

**Response:**
```json
{
  "success": true,
  "prediction": 1,
  "confidence": 0.95,
  "phase": 2,
  "recommendation": "ASSIGN",
  "feature_importance": {...}
}
```

### Modelo: XGBoost
- **Accuracy**: 90%
- **Precision**: 89.33%
- **Recall**: 97.10%
- **AUC**: 95.18%
- **Features**: 18
- **Training data**: 500 records (69% optimal)

---

## FASE 3, PASO 2: A/B TESTING (v3)

Base URL: `http://localhost:5000/api/v3/ab-testing`

### Endpoints

| Método | Endpoint | Descripción | Parámetros |
|--------|----------|-------------|-----------|
| GET | `/status` | Estado actual del A/B test | hours (opcional, default 24) |
| GET | `/dashboard` | Dashboard completo | hours (opcional) |
| GET | `/comparison` | Comparativa Fase 1 vs 2 | hours (opcional) |
| POST | `/decide-phase` | Decidir qué fase usar | dispatch_id |
| POST | `/log` | Registrar resultado | JSON body |
| GET | `/recommendation` | Recomendación automática | hours (opcional) |
| GET | `/metrics` | Métricas detalladas | hours (opcional) |
| GET | `/strategies` | Estrategias disponibles | Ninguno |

### Ejemplo: Decide Phase
```bash
curl -X POST http://localhost:5000/api/v3/ab-testing/decide-phase \
  -H "Content-Type: application/json" \
  -d '{
    "dispatch_id": 123
  }'
```

**Response:**
```json
{
  "success": true,
  "phase": 2,
  "strategy": "random_50_50",
  "dispatch_id": 123
}
```

### Ejemplo: Log Result
```bash
curl -X POST http://localhost:5000/api/v3/ab-testing/log \
  -H "Content-Type: application/json" \
  -d '{
    "dispatch_id": 123,
    "phase_used": 2,
    "phase1_result": null,
    "phase2_result": {
      "prediction": 1,
      "confidence": 0.95,
      "recommendation": "ASSIGN"
    }
  }'
```

### Ejemplo: Get Dashboard
```bash
curl http://localhost:5000/api/v3/ab-testing/dashboard?hours=24
```

**Response:**
```json
{
  "success": true,
  "report": {
    "period": "Last 24 hours",
    "summary": {
      "total_requests": 1250,
      "phase1_requests": 623,
      "phase2_requests": 627,
      "phase1_percentage": 49.84,
      "phase2_percentage": 50.16
    },
    "phase1_metrics": {
      "total": 623,
      "avg_confidence": 0.8234,
      "confidence_range": {
        "min": 0.5012,
        "max": 0.9987
      }
    },
    "phase2_metrics": {
      "total": 627,
      "avg_confidence": 0.9156,
      "confidence_range": {
        "min": 0.5678,
        "max": 0.9999
      }
    },
    "comparison": {
      "confidence_difference": 0.0922,
      "confidence_improvement_percent": 11.21,
      "phase2_better": true,
      "recommendation": "Phase 2 performing better. Consider gradual rollout."
    },
    "strategy": "random_50_50",
    "recommendation": "Phase 2 showing significant improvement. Consider gradual rollout."
  }
}
```

### Estrategias Disponibles
1. **RANDOM_50_50**: División aleatoria 50-50
2. **ROUND_ROBIN**: Alternancia sistemática
3. **TIME_BASED**: Split según hora (peak: 70% Fase 2, off-peak: 30%)
4. **WEIGHT_BASED**: Peso customizable para rollout gradual

---

## FASE 3, PASO 3: MONITORING (v4)

Base URL: `http://localhost:5000/api/v4/monitoring`

### A. Health Check Endpoints (5)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Estado general del sistema |
| GET | `/health/database` | Salud de la base de datos |
| GET | `/health/model` | Salud del modelo ML |
| GET | `/health/predictions` | Salud del servicio de predicciones |
| GET | `/health/fallback` | Salud basada en fallbacks |

#### Ejemplo: Get System Health
```bash
curl http://localhost:5000/api/v4/monitoring/health
```

**Response:**
```json
{
  "success": true,
  "health": {
    "overall_status": "HEALTHY",
    "timestamp": "2025-01-15T14:30:00",
    "checks": {
      "database": {"status": "HEALTHY", ...},
      "model": {"status": "HEALTHY", ...},
      "prediction_service": {"status": "HEALTHY", ...},
      "fallback": {"status": "HEALTHY", ...}
    },
    "summary": {
      "healthy": 4,
      "degraded": 0,
      "unhealthy": 0
    }
  }
}
```

### B. Drift Detection Endpoints (3)

| Método | Endpoint | Descripción | Parámetros |
|--------|----------|-------------|-----------|
| GET | `/drift/prediction` | Detectar drift en predicciones | hours (default 24) |
| GET | `/drift/performance` | Detectar degradación | hours, comparison_hours |
| GET | `/drift/data-quality` | Problemas de calidad | hours (default 24) |

#### Ejemplo: Detect Drift
```bash
curl http://localhost:5000/api/v4/monitoring/drift/prediction?hours=24
```

**Response:**
```json
{
  "success": true,
  "drift_detection": {
    "period_hours": 24,
    "timestamp": "2025-01-15T14:30:00",
    "current_metrics": {
      "avg_confidence": 0.9156,
      "std_confidence": 0.0821,
      "sample_count": 1250
    },
    "has_drift": false,
    "drift_count": 0,
    "severity": "NONE",
    "drifts_detected": []
  }
}
```

#### Ejemplo: Detect Performance Degradation
```bash
curl http://localhost:5000/api/v4/monitoring/drift/performance?hours=24&comparison_hours=72
```

### C. Alert Management Endpoints (4)

| Método | Endpoint | Descripción | Parámetros |
|--------|----------|-------------|-----------|
| GET | `/alerts/active` | Alertas activas | Ninguno |
| GET | `/alerts/history` | Historial de alertas | days (default 7) |
| GET | `/alerts/statistics` | Estadísticas de alertas | days (default 7) |
| POST | `/alerts/<id>/resolve` | Resolver alerta | alert_id, resolution_notes |

#### Ejemplo: Get Active Alerts
```bash
curl http://localhost:5000/api/v4/monitoring/alerts/active
```

**Response:**
```json
{
  "success": true,
  "active_alerts": [
    {
      "id": 1,
      "type": "HIGH_FALLBACK_RATE",
      "severity": "HIGH",
      "title": "Fallback rate exceeded",
      "description": "Fallback rate is 12%",
      "created_at": "2025-01-15T10:30:00",
      "resolution_steps": [
        "Check ML service health",
        "Review recent changes",
        "Restart service if needed"
      ]
    }
  ],
  "count": 1
}
```

#### Ejemplo: Get Alert Statistics
```bash
curl http://localhost:5000/api/v4/monitoring/alerts/statistics?days=7
```

#### Ejemplo: Resolve Alert
```bash
curl -X POST http://localhost:5000/api/v4/monitoring/alerts/1/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "resolution_notes": "Service restarted and is now healthy"
  }'
```

### D. Dashboard Endpoint (1)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/dashboard` | Dashboard completo de monitoreo |

#### Ejemplo: Get Full Dashboard
```bash
curl http://localhost:5000/api/v4/monitoring/dashboard
```

**Response:**
```json
{
  "success": true,
  "dashboard": {
    "timestamp": "2025-01-15T14:30:00",
    "overall_health": {...},
    "drift_detection": {...},
    "alerts": {...},
    "summary": {
      "system_status": "HEALTHY",
      "critical_issues": 0,
      "high_severity": 1,
      "drifts_detected": 0,
      "performance_degradations": 0,
      "data_quality_issues": 0
    }
  }
}
```

---

## HEALTH ENDPOINTS

### Global Health Check
```bash
GET http://localhost:5000/health
```

### Detailed Health Check
```bash
GET http://localhost:5000/health/detailed
```

---

## RESUMEN DE ENDPOINTS

| Versión | Cantidad | Propósito |
|---------|----------|-----------|
| v1 (Fase 1) | 3 | Asignación determinística |
| v2 (Fase 2) | 5 | Predicciones ML |
| v3 (Fase 3.2) | 8 | A/B Testing |
| v4 (Fase 3.3) | 15 | Monitoreo y Alertas |
| **Total** | **31** | **Sistema Completo** |

---

## ALERTAS AUTOMÁTICAS

El sistema crea alertas automáticamente para:

1. **Drift Detectado** (DRIFT_DETECTED)
   - Cambio en confianza > 10%
   - Severidad: HIGH

2. **Degradación de Performance** (PERFORMANCE_DEGRADATION)
   - Caída de performance > 5%
   - Severidad: MEDIUM

3. **Alta Tasa de Fallback** (HIGH_FALLBACK_RATE)
   - Fallback rate > 5% (warning) o > 10% (critical)
   - Severidad: HIGH/CRITICAL

4. **Baja Confianza** (LOW_CONFIDENCE)
   - Promedio < 0.75
   - Severidad: HIGH

5. **Problemas de Calidad de Datos** (DATA_QUALITY)
   - Null rate > 5%
   - Outliers > 5%
   - Severidad: MEDIUM

---

## INTEGRACIÓN CON ms-despacho

```python
from src.integration import MLClient, PredictionLogger
from src.integration import ABTest, ABTestingStrategy

# 1. Crear cliente ML
ml_client = MLClient(ml_service_url='http://localhost:5000')

# 2. Decidir fase para cada dispatch
phase = ABTest(...).decide_phase(dispatch_id=123)

# 3. Obtener predicción
if phase == 2:
    result = ml_client.predict(features)
else:
    result = reglas_deterministicas(features)

# 4. Registrar predicción
logger = PredictionLogger(...)
logger.log_prediction(dispatch_id=123, phase=phase, ...)

# 5. Monitorear
from src.monitoring import HealthChecker
health = HealthChecker(...).get_overall_health()
```

---

**Última actualización:** 2025-01-15
**Versión:** 1.0.0
**Estado:** PRODUCCIÓN
