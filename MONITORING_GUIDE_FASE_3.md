# GUÍA DE MONITOREO - FASE 3, PASO 3

## Monitoreo y Alertas del Sistema ML

**Objetivo:** Sistema completo de monitoreo con detección de drift, alertas en tiempo real y health checking del sistema ML.

---

## COMPONENTES

### 1. Drift Detector (`src/monitoring/drift_detector.py`)

Sistema de detección de cambios en la distribución de datos.

#### Funcionalidades:
- **Detección de Drift en Predicciones**: Monitorea cambios en confianza promedio
- **Detección de Degradación**: Compara performance actual vs períodos anteriores
- **Detección de Calidad de Datos**: Identifica valores nulos y outliers
- **Logging de Alertas**: Registra en tabla `ml.drift_alerts`

#### Métodos:
```python
detector = DriftDetector(server, database, username, password)
detector.connect()

# Detectar drift en confianza
drift = detector.detect_prediction_drift(hours=24)

# Detectar degradación de performance
degradation = detector.detect_performance_degradation(hours=24, comparison_hours=72)

# Detectar problemas de calidad
quality = detector.detect_data_quality_issues(hours=24)

# Registrar alerta de drift
detector.log_drift(drift_type, severity, message, metrics)
```

### 2. Alert Manager (`src/monitoring/alert_manager.py`)

Gestor centralizado de alertas y notificaciones.

#### Tipos de Alertas:
```python
AlertType.DRIFT_DETECTED
AlertType.PERFORMANCE_DEGRADATION
AlertType.SERVICE_DOWN
AlertType.HIGH_FALLBACK_RATE
AlertType.LOW_CONFIDENCE
AlertType.DATA_QUALITY
AlertType.MEMORY_USAGE
AlertType.DATABASE_ERROR
```

#### Niveles de Severidad:
```python
AlertSeverity.CRITICAL    # Requiere acción inmediata
AlertSeverity.HIGH        # Acción urgente
AlertSeverity.MEDIUM      # Supervisar y planificar
AlertSeverity.LOW         # Informativo
AlertSeverity.INFO        # Notificación general
```

#### Umbrales Configurables:
```python
manager = AlertManager(server, database, username, password)
manager.thresholds.drift_confidence_change = 10  # %
manager.thresholds.fallback_rate_critical = 10   # %
manager.thresholds.confidence_minimum = 0.75
manager.thresholds.service_timeout = 30  # segundos
```

#### Métodos:
```python
# Crear alerta
manager.create_alert(
    alert_type=AlertType.HIGH_FALLBACK_RATE,
    severity=AlertSeverity.HIGH,
    title="Fallback rate exceeded",
    description="Fallback rate is 12%",
    details={'current_rate': 12, 'threshold': 10},
    resolution_steps=['Check service', 'Restart if needed']
)

# Obtener alertas activas
alerts = manager.get_active_alerts()

# Obtener historial
history = manager.get_alert_history(days=7)

# Obtener estadísticas
stats = manager.get_alert_statistics(days=7)

# Resolver alerta
manager.resolve_alert(alert_id, resolution_notes="Fixed service")

# Registrar handler para notificaciones
manager.register_handler(my_notification_function)
```

### 3. Health Checker (`src/monitoring/health_checker.py`)

Sistema de verificación de salud del servicio.

#### Estados de Salud:
```python
HealthStatus.HEALTHY      # Sistema operativo normalmente
HealthStatus.DEGRADED     # Funcionando con limitaciones
HealthStatus.UNHEALTHY    # Problemas críticos
```

#### Verificaciones:
1. **Database Health**: Conexión, tablas, espacio
2. **Model Health**: Archivos del modelo, fecha de actualización
3. **Prediction Service**: Confianza, tasa de baja confianza
4. **Fallback Health**: Tasa de fallbacks

#### Métodos:
```python
checker = HealthChecker(server, database, username, password)
checker.connect()

# Verificar salud general
health = checker.get_overall_health()

# Verificar componentes específicos
db_health = checker.check_database_health()
model_health = checker.check_model_health()
pred_health = checker.check_prediction_service_health()
fallback_health = checker.check_fallback_health()

# Registrar health check en BD
checker.log_health_check(health_data)
```

### 4. Monitoring Dashboard API (`src/api/monitoring_dashboard.py`)

REST endpoints para acceso a monitoreo y alertas.

#### Endpoints Disponibles:

**Health Check Endpoints:**
```
GET /api/v4/monitoring/health                  - Estado general
GET /api/v4/monitoring/health/database         - Salud de BD
GET /api/v4/monitoring/health/model            - Salud del modelo
GET /api/v4/monitoring/health/predictions      - Salud del servicio
GET /api/v4/monitoring/health/fallback         - Salud de fallbacks
```

**Drift Detection Endpoints:**
```
GET /api/v4/monitoring/drift/prediction        - Drift en predicciones
GET /api/v4/monitoring/drift/performance       - Degradación de performance
GET /api/v4/monitoring/drift/data-quality      - Problemas de calidad
```

**Alert Endpoints:**
```
GET /api/v4/monitoring/alerts/active           - Alertas activas
GET /api/v4/monitoring/alerts/history          - Historial
GET /api/v4/monitoring/alerts/statistics       - Estadísticas
POST /api/v4/monitoring/alerts/<id>/resolve    - Resolver alerta
```

**Dashboard:**
```
GET /api/v4/monitoring/dashboard               - Dashboard completo
```

---

## FLUJO DE INTEGRACIÓN

### Paso 1: Inicializar Monitoring

```python
from src.monitoring import (
    DriftDetector, AlertManager, HealthChecker,
    AlertType, AlertSeverity
)

# Crear instancias
drift_detector = DriftDetector(
    server='192.168.1.38',
    database='ms_ml_despacho',
    username='sa',
    password='1234'
)

alert_manager = AlertManager(
    server='192.168.1.38',
    database='ms_ml_despacho',
    username='sa',
    password='1234'
)

health_checker = HealthChecker(
    server='192.168.1.38',
    database='ms_ml_despacho',
    username='sa',
    password='1234'
)

# Conectar
drift_detector.connect()
alert_manager.connect()
health_checker.connect()
```

### Paso 2: Configurar Monitoreo Automático

```python
import time
from datetime import datetime

def monitor_system():
    """Función de monitoreo continuo"""

    while True:
        try:
            # 1. Verificar salud general
            health = health_checker.get_overall_health()
            print(f"System health: {health['overall_status']}")

            # 2. Detectar drifts
            drift = drift_detector.detect_prediction_drift(hours=1)
            if drift.get('has_drift'):
                for drift_item in drift.get('drifts_detected', []):
                    alert_manager.create_alert(
                        alert_type=AlertType.DRIFT_DETECTED,
                        severity=AlertSeverity[drift_item.get('severity')],
                        title=f"Drift: {drift_item.get('type')}",
                        description=drift_item.get('message'),
                        details=drift_item
                    )

            # 3. Verificar fallback rate
            fallback_type = alert_manager.check_fallback_rate(hours=1)
            if fallback_type:
                alert_manager.create_alert(
                    alert_type=fallback_type,
                    severity=AlertSeverity.HIGH,
                    title="High fallback rate detected",
                    description="Fallback rate exceeded critical threshold"
                )

            # 4. Registrar health check
            health_checker.log_health_check(health)

            # Esperar antes del siguiente chequeo
            time.sleep(300)  # Cada 5 minutos

        except Exception as e:
            print(f"Error in monitoring: {e}")
            time.sleep(60)

# Ejecutar en thread separado
import threading
monitor_thread = threading.Thread(target=monitor_system, daemon=True)
monitor_thread.start()
```

### Paso 3: Acceder al Dashboard

```bash
# Estado general
curl http://localhost:5000/api/v4/monitoring/health

# Historial de alertas
curl http://localhost:5000/api/v4/monitoring/alerts/history?days=7

# Dashboard completo
curl http://localhost:5000/api/v4/monitoring/dashboard
```

---

## RESPUESTAS DE ENDPOINTS

### 1. Health Check General

```bash
GET /api/v4/monitoring/health
```

**Response:**
```json
{
  "success": true,
  "health": {
    "overall_status": "HEALTHY",
    "timestamp": "2025-01-15T14:30:00",
    "checks": {
      "database": {
        "status": "HEALTHY",
        "database": "CONNECTED",
        "tables": {
          "ml.assignment_history": {
            "exists": true,
            "record_count": 1250,
            "status": "OK"
          },
          "ml.ab_test_log": {
            "exists": true,
            "record_count": 2500,
            "status": "OK"
          }
        },
        "database_size_mb": 125.45
      },
      "model": {
        "status": "HEALTHY",
        "model": {
          "file": "xgboost_model.pkl",
          "exists": true,
          "size_kb": 2048,
          "modified": "2025-01-10T10:30:00"
        },
        "scaler": {
          "file": "xgboost_model_scaler.pkl",
          "exists": true,
          "size_kb": 15,
          "modified": "2025-01-10T10:30:00"
        }
      },
      "prediction_service": {
        "status": "HEALTHY",
        "message": "Predictions healthy",
        "metrics": {
          "total_predictions_24h": 1250,
          "avg_confidence": 0.9156,
          "low_confidence_count": 0,
          "low_confidence_rate": 0.0
        }
      },
      "fallback": {
        "status": "HEALTHY",
        "message": "Fallback rate normal",
        "metrics": {
          "total_predictions": 1250,
          "fallback_count": 12,
          "fallback_rate": 0.96
        }
      }
    },
    "summary": {
      "healthy": 4,
      "degraded": 0,
      "unhealthy": 0
    }
  }
}
```

### 2. Drift Detection

```bash
GET /api/v4/monitoring/drift/prediction?hours=24
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
    "training_metrics": {
      "avg_confidence": 0.91,
      "std_confidence": 0.08
    },
    "has_drift": false,
    "drift_count": 0,
    "severity": "NONE",
    "drifts_detected": []
  }
}
```

### 3. Active Alerts

```bash
GET /api/v4/monitoring/alerts/active
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

### 4. Alert Statistics

```bash
GET /api/v4/monitoring/alerts/statistics?days=7
```

**Response:**
```json
{
  "success": true,
  "alert_statistics": {
    "period_days": 7,
    "timestamp": "2025-01-15T14:30:00",
    "by_severity": {
      "CRITICAL": 0,
      "HIGH": 2,
      "MEDIUM": 5,
      "LOW": 8
    },
    "by_type": {
      "DRIFT_DETECTED": 3,
      "PERFORMANCE_DEGRADATION": 2,
      "HIGH_FALLBACK_RATE": 1,
      "DATA_QUALITY": 9
    },
    "by_status": {
      "OPEN": 3,
      "RESOLVED": 12
    },
    "total_alerts": 15,
    "resolution_rate": 80.0
  }
}
```

### 5. Dashboard Completo

```bash
GET /api/v4/monitoring/dashboard
```

**Response:**
```json
{
  "success": true,
  "dashboard": {
    "timestamp": "2025-01-15T14:30:00",
    "overall_health": {
      "overall_status": "HEALTHY",
      "summary": {
        "healthy": 4,
        "degraded": 0,
        "unhealthy": 0
      }
    },
    "drift_detection": {
      "prediction": {
        "has_drift": false,
        "drift_count": 0
      },
      "performance": {
        "has_degradation": false,
        "degradation_count": 0
      },
      "data_quality": {
        "has_issues": false,
        "issue_count": 0
      }
    },
    "alerts": {
      "active_count": 1,
      "active_alerts": [...],
      "statistics": {
        "total_alerts": 15,
        "resolution_rate": 80.0
      }
    },
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

## INTERPRETACIÓN DE RESULTADOS

### Drift Detection

**Sin Drift (Normal):**
```
has_drift: false
drifts_detected: []
→ Sistema operando normalmente
```

**Drift Detectado:**
```
has_drift: true
drifts_detected: [
  {
    "type": "CONFIDENCE_DRIFT",
    "severity": "HIGH",
    "difference_percent": 15.5
  }
]
→ Cambio significativo en distribución
→ Puede indicar: cambios en datos, modelo degradado, o entorno diferente
```

### Performance Degradation

**Sin Degradación:**
```
confidence_change_percent: 2.5
has_degradation: false
→ Performance estable
```

**Degradación Detectada:**
```
confidence_change_percent: -8.3
has_degradation: true
→ Performance ha decaído 8.3%
→ Investigar causa: modelo, datos, configuración
```

### Alert Severity

| Nivel | Acción | Ejemplo |
|-------|--------|---------|
| CRITICAL | Inmediata | Servicio caído, datos corruptos |
| HIGH | Urgente (< 1 hora) | Fallback rate > 10% |
| MEDIUM | Planificar (< 24 horas) | Drift detectado, Confidence < 0.85 |
| LOW | Informativo | Cambios menores |

---

## MÉTRICAS CLAVE A MONITOREAR

### 1. Disponibilidad
- **Uptime del servicio**: Meta > 99.9%
- **Database availability**: Debe ser 100%
- **API response time**: < 5 segundos (warning > 3 seg)

### 2. Calidad de Predicciones
- **Average confidence**: Meta > 0.92
- **Confidence varianza**: < 0.10
- **Low confidence rate**: < 5%

### 3. Fallback Rate
- **Normal**: 0-2%
- **Warning**: 2-5%
- **Critical**: > 5%

### 4. Data Quality
- **Null rate**: < 2%
- **Outlier rate**: < 3%
- **Schema violations**: 0

### 5. Model Performance
- **Accuracy vs outcomes**: Monitorear degradación
- **Feature importance**: Verificar cambios
- **Training data distribution**: Comparar vs entrenamiento

---

## ALERTAS AUTOMÁTICAS

### Configuración de Alertas

```python
# 1. Drift en confianza > 10%
if confidence_change > 10:
    create_alert(AlertType.DRIFT_DETECTED, AlertSeverity.HIGH)

# 2. Performance degradation > 5%
if performance_change < -5:
    create_alert(AlertType.PERFORMANCE_DEGRADATION, AlertSeverity.MEDIUM)

# 3. Fallback rate > 10%
if fallback_rate > 0.10:
    create_alert(AlertType.HIGH_FALLBACK_RATE, AlertSeverity.CRITICAL)

# 4. Confidence promedio < 0.75
if avg_confidence < 0.75:
    create_alert(AlertType.LOW_CONFIDENCE, AlertSeverity.HIGH)

# 5. Null rate > 5%
if null_rate > 0.05:
    create_alert(AlertType.DATA_QUALITY, AlertSeverity.MEDIUM)
```

### Acciones Recomendadas

**Drift Detectado:**
1. Revisar últimos datos
2. Comparar distribución con entrenamiento
3. Evaluar modelo en datos nuevos
4. Considerear reentrenamiento

**Performance Degradation:**
1. Revisar métricas detalladas
2. Comparar predicciones vs outcomes
3. Investigar cambios recientes
4. Validar modelo

**High Fallback Rate:**
1. Revisar logs de errores
2. Verificar estado de BD
3. Revisar modelo (puede estar caído)
4. Considerar rollback

---

## SQL QUERIES ÚTILES

### Ver alertas recientes
```sql
SELECT TOP 20
    id, alert_type, severity, title, status, created_at
FROM ml.system_alerts
ORDER BY created_at DESC
```

### Alertas no resueltas
```sql
SELECT
    alert_type, COUNT(*) as count,
    MIN(created_at) as oldest,
    MAX(created_at) as latest
FROM ml.system_alerts
WHERE status = 'OPEN'
GROUP BY alert_type
ORDER BY count DESC
```

### Health check history
```sql
SELECT TOP 100
    overall_status, database_status, model_status,
    prediction_status, fallback_status, created_at
FROM ml.health_checks
ORDER BY created_at DESC
```

### Drift alerts
```sql
SELECT
    drift_type, COUNT(*) as count,
    MAX(created_at) as latest
FROM ml.drift_alerts
WHERE created_at > DATEADD(day, -7, GETDATE())
GROUP BY drift_type
```

---

## TROUBLESHOOTING

### Problema: Demasiadas alertas

**Causa:** Umbrales muy bajos
```python
# Ajustar umbrales
manager.thresholds.drift_confidence_change = 15  # De 10 a 15%
manager.thresholds.fallback_rate_warning = 8    # De 5 a 8%
```

### Problema: No se crean alertas

**Causa:** Insuficientes datos o no hay issues
```python
# Verificar datos
detector.connect()
results = detector.detect_prediction_drift(24)
print(results)  # Ver si hay drifts reales
```

### Problema: Performance degrada constantemente

**Causa:**
1. Datos de entrada han cambiado
2. Modelo necesita reentrenamiento
3. Problema en producción vs entrenamiento

**Solución:**
1. Revisar muestras de datos recientes
2. Comparar con datos de entrenamiento
3. Reentrenar modelo con datos nuevos

---

## MONITOREO RECOMENDADO

### Diariamente
- [ ] Revisar dashboard general
- [ ] Verificar alertas activas
- [ ] Chequear health status
- [ ] Revisar fallback rate (< 5%)

### Semanalmente
- [ ] Analizar trend de drifts
- [ ] Revisar estadísticas de alertas
- [ ] Comparar performance vs baseline
- [ ] Revisar data quality metrics

### Mensualmente
- [ ] Análisis completo de performance
- [ ] Revisión de umbrales de alertas
- [ ] Validación de modelo vs outcomes
- [ ] Planificación de reentrenamiento

---

**Status:** Fase 3, Paso 3 - Monitoreo y Alertas COMPLETO
**Archivos:**
- `src/monitoring/drift_detector.py` (450 líneas)
- `src/monitoring/alert_manager.py` (400 líneas)
- `src/monitoring/health_checker.py` (380 líneas)
- `src/api/monitoring_dashboard.py` (420 líneas)
- `src/monitoring/__init__.py`
