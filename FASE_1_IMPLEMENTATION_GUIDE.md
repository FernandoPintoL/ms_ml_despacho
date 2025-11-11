# Fase 1: Implementación - Guía Completa

## Resumen Ejecutivo

Esta es la **Fase 1** del sistema de asignación de ambulancias basado en ML.

**Estado:** Reglas Determinísticas (Sin Machine Learning aún)

**Duración:** 2-3 semanas implementar + 2-3 meses recolectar datos para Fase 2

**Objetivo:** Recolectar datos históricos mientras usamos lógica determinística simple

---

## 1. ARQUITECTURA BASE DE DATOS

### 1.1 Crear la Base de Datos en SQL Server

```sql
-- Conectarse a SQL Server
-- Ejecutar el script: scripts/01_create_schema.sql

-- Verify schema was created
SELECT * FROM sys.schemas WHERE name = 'ml'

-- Verify tables exist
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'ml'
```

### 1.2 Tablas Principales

#### `ml.assignment_history`
- Propósito: Guardar TODAS las asignaciones realizadas
- Registros por día: ~100-500 (depende del volumen de emergencias)
- Período de retención: 12 meses (para entrenar ML)
- Features: Datos de entrada + Datos de salida + Métricas post-asignación

#### `ml.trained_models`
- Propósito: Registro de modelos ML entrenados
- En Fase 1: Tendrá 1 registro (configuración de reglas)
- En Fase 2: Tendrá 1+ registros de modelos XGBoost

#### `ml.predictions_log`
- Propósito: Auditoría de predicciones
- En Fase 1: Vacío (aún no hay predicciones ML)
- En Fase 2: Registrará cada predicción del modelo

#### `ml.model_configuration`
- Propósito: Guardar configuración de reglas y parámetros
- En Fase 1: Contiene configuración de asignación por severidad

---

## 2. IMPLEMENTACIÓN FASE 1: CÓDIGO PYTHON

### 2.1 Archivos Creados

```
ms_ml_despacho/
├── scripts/
│   ├── 01_create_schema.sql          ← Script SQL para crear BD
│   └── SCHEMA_DIAGRAM.md             ← Diagrama ER
├── src/
│   ├── services/
│   │   └── dispatch_assignment_service.py    ← Lógica de asignación (NUEVA)
│   ├── repositories/
│   │   └── assignment_history_repository.py  ← Repository para histórico (NUEVA)
│   └── api/
│       └── dispatch_assignment_routes.py     ← Endpoints REST (NUEVA)
└── FASE_1_IMPLEMENTATION_GUIDE.md    ← Esta guía
```

### 2.2 Componentes Principales

#### `DispatchAssignmentService`
Responsable de toda la lógica de asignación

```python
# Inicializar
service = DispatchAssignmentService(
    dispatch_repo=dispatch_repo,
    assignment_history_repo=assignment_history_repo
)

# Usar
result = service.assign_ambulance_and_personnel({
    'dispatch_id': 123,
    'patient_latitude': 4.7110,
    'patient_longitude': -74.0721,
    'emergency_type': 'trauma',
    'severity_level': 4,
    'available_ambulances': [...],
    'available_paramedics': [...]
})

# Retorna
{
    'success': True,
    'ambulance_id': 1,
    'paramedic_ids': [1, 2],
    'confidence': 0.92,
    'history_id': 456
}
```

#### `AssignmentHistoryRepository`
Maneja lectura/escritura de datos históricos

```python
# Crear registro
history_id = repo.create_assignment_history({
    'dispatch_id': 123,
    'emergency_latitude': 4.7110,
    'emergency_longitude': -74.0721,
    'severity_level': 4,
    'assigned_ambulance_id': 1,
    'assigned_paramedic_ids': json.dumps([1, 2])
})

# Leer estadísticas
stats = repo.get_assignment_statistics(hours=24)
# Retorna: {total_assignments, optimal_count, avg_response_time, ...}

# Obtener datos para entrenar ML
training_data = repo.get_assignments_for_training(min_samples=500)
```

### 2.3 Reglas de Asignación (Fase 1)

#### Regla 1: Ambulancia Más Cercana

```
Algoritmo:
1. Filtrar ambulancias disponibles
2. Calcular distancia (Haversine formula) de cada una
3. Aplicar máximo de 15km (configurable)
4. Retornar la más cercana

Confianza:
- 0-2km: 0.95
- 2-5km: 0.85
- 5-10km: 0.70
- 10-15km: 0.50
```

#### Regla 2: Validación de Disponibilidad

```
Automatizado: Se filtra directamente en la función _select_ambulance()
```

#### Regla 3: Asignación de Personal por Severidad

```
Severidad 5 (Crítico/Extremo):
  ├─ 3 Paramédicos (2 senior + 1 junior)
  ├─ 1 Enfermero
  └─ 1 Especialista

Severidad 4 (Alto):
  ├─ 2 Paramédicos (1 senior + 1 junior)
  └─ 1 Enfermero

Severidad 3 (Medio):
  └─ 2 Paramédicos (2 junior)

Severidad 2 (Bajo-Medio):
  └─ 1 Paramédico (junior)

Severidad 1 (Bajo):
  └─ 1 Paramédico (junior)
```

---

## 3. INTEGRACIÓN CON LA APLICACIÓN

### 3.1 Endpoints REST Disponibles

#### 1. Asignar Ambulancia (Principal)

```
POST /api/v1/dispatch/assign

Request:
{
    "dispatch_id": 123,
    "patient_latitude": 4.7110,
    "patient_longitude": -74.0721,
    "emergency_type": "trauma",
    "severity_level": 4,
    "zone_code": "ZONA_1",
    "available_ambulances": [
        {
            "id": 1,
            "latitude": 4.7120,
            "longitude": -74.0700,
            "status": "available",
            "crew_level": "senior"
        }
    ],
    "available_paramedics": [
        {"id": 1, "level": "senior", "status": "available"},
        {"id": 2, "level": "junior", "status": "available"}
    ],
    "available_nurses": [
        {"id": 10, "status": "available"}
    ]
}

Response (Success):
{
    "success": true,
    "dispatch_id": 123,
    "ambulance_id": 1,
    "paramedic_ids": [1, 2],
    "nurse_id": 10,
    "distance_km": 0.25,
    "confidence": 0.92,
    "assignment_type": "deterministic_rules",
    "phase": 1,
    "reasoning": "Nearest ambulance at 0.25km + 2 paramedics for high severity",
    "timestamp": "2025-11-10T12:34:56Z",
    "history_id": 456
}

Response (Error):
{
    "success": false,
    "error": "No ambulances available"
}
```

#### 2. Asignaciones en Lote

```
POST /api/v1/dispatch/assign/batch

Request:
{
    "dispatches": [
        {...dispatch_1...},
        {...dispatch_2...}
    ]
}

Response:
{
    "success": true,
    "total": 2,
    "successful": 2,
    "failed": 0,
    "results": [...]
}
```

#### 3. Obtener Histórico

```
GET /api/v1/dispatch/history/<dispatch_id>

Response:
{
    "success": true,
    "dispatch_id": 123,
    "assignment": {
        "id": 456,
        "ambulance_id": 1,
        "paramedic_ids": [1, 2],
        "severity_level": 4,
        "response_time": 2.5,
        "created_at": "2025-11-10T12:30:00Z"
    }
}
```

#### 4. Asignaciones Recientes

```
GET /api/v1/dispatch/history/recent?limit=50&hours=24

Response:
{
    "success": true,
    "count": 42,
    "limit": 50,
    "assignments": [...]
}
```

#### 5. Estadísticas

```
GET /api/v1/dispatch/statistics?hours=24

Response:
{
    "success": true,
    "period_hours": 24,
    "statistics": {
        "total_assignments": 150,
        "optimal_assignments": 127,
        "optimal_rate": 84.67,
        "avg_response_time": 3.2,
        "avg_optimization_score": 0.85,
        "avg_patient_satisfaction": 4.2
    }
}
```

### 3.2 Integración con MS-DESPACHO

El flujo completo:

```
1. n8n/MS Recepción recibe solicitud de ambulancia
   └─ Envía a MS-ML-DESPACHO

2. MS-ML-DESPACHO (Fase 1)
   ├─ POST /api/v1/dispatch/assign
   ├─ Aplica reglas determinísticas
   ├─ Retorna: {ambulance_id, paramedic_ids, confidence}
   └─ Guarda en ml.assignment_history

3. MS-DESPACHO recibe respuesta
   ├─ Valida asignación en su BD
   ├─ Ejecuta despacho real
   ├─ Notifica paramédico
   └─ Continúa flujo normal

4. Después (cuando termina)
   ├─ MS-DESPACHO notifica resultado
   └─ MS-ML-DESPACHO actualiza assignment_history
      con: response_time, patient_outcome, was_optimal
```

---

## 4. RECOLECCIÓN DE DATOS

### 4.1 Plan de Recolección

**Objetivo:** Recolectar 500-1000 registros en 2-3 meses

| Semana | Objetivo | Registros Esperados |
|--------|----------|-------------------|
| 1-2 | Deployment y testing | 0 |
| 3-4 | Primer mes live | 100-150 |
| 5-8 | Mes 2 | 200-300 |
| 9-12 | Mes 3 | 200-250 |
| **Total en 3 meses** | **Listo para Fase 2** | **~600-800** |

### 4.2 Qué Registrar

Cada asignación guarda automáticamente:

```
FEATURES (Input):
├─ Ubicación: latitude, longitude, zone_code
├─ Contexto: hour_of_day, day_of_week, is_weekend
├─ Emergencia: emergency_type, severity_level
├─ Disponibilidad:
│  ├─ ambulances_available_count
│  ├─ paramedics_available_count
│  └─ ambulances_busy_percentage
└─ Histórico: avg_response_time_zone, active_dispatches_count

TARGET (Output):
├─ assigned_ambulance_id  ← Lo que queremos predecir
├─ assigned_paramedic_ids ← Lo que queremos predecir
└─ assigned_paramedic_levels

POST-ASIGNACIÓN (Se llena después):
├─ actual_response_time_minutes
├─ patient_outcome
├─ was_optimal (LABEL: ¿fue la mejor opción?)
└─ optimization_score
```

### 4.3 Script para Simular Datos (Opcional)

Si necesitas testing sin datos reales:

```python
# scripts/simulate_assignments.py
import random
from datetime import datetime, timedelta

def generate_test_data(count=500):
    """Generar datos simulados para testing"""

    for i in range(count):
        dispatch_data = {
            'dispatch_id': 1000 + i,
            'patient_latitude': random.uniform(4.5, 5.0),
            'patient_longitude': random.uniform(-74.3, -74.0),
            'emergency_type': random.choice(['trauma', 'paro', 'quemadura', 'intoxicacion']),
            'severity_level': random.randint(1, 5),
            'zone_code': f"ZONA_{random.randint(1, 10)}",
            'available_ambulances': generate_ambulances(),
            'available_paramedics': generate_paramedics()
        }

        # Asignar
        result = service.assign_ambulance_and_personnel(dispatch_data)
        print(f"Simulation {i+1}/{count}: {result}")
```

---

## 5. IMPLEMENTACIÓN EN PRODUCCIÓN

### 5.1 Checklist Pre-Deployment

- [ ] SQL Server BD creada en ambiente de producción
- [ ] Tablas `ml.*` verificadas
- [ ] Variables de entorno configuradas:
  ```
  DATABASE_URL=mssql://user:pass@server/ms_ml_despacho
  AMBULANCE_MAX_DISTANCE_KM=15
  DISTANCE_WEIGHT=0.3
  AVAILABILITY_WEIGHT=0.3
  ```
- [ ] Endpoints `/api/v1/dispatch/assign` funcionando
- [ ] Logging configurado y monitoreado
- [ ] Monitoring/Alertas configuradas

### 5.2 Variables de Entorno (Fase 1)

```bash
# Database
DATABASE_URL=mssql://hads_user:hads_password@localhost:1433/ms_ml_despacho

# ML Models
AMBULANCE_MAX_DISTANCE_KM=15              # Máxima distancia permitida
AMBULANCE_PREFERENCE_WEIGHT=0.4           # No usado en Fase 1
DISTANCE_WEIGHT=0.3                       # No usado en Fase 1
AVAILABILITY_WEIGHT=0.3                   # No usado en Fase 1

# Feature flags
FEATURE_AMBULANCE_OPTIMIZATION=true

# Logging
LOG_LEVEL=INFO
VERBOSE_LOGGING=false
```

### 5.3 Monitoreo

Endpoints útiles para monitoreo:

```bash
# Health check
curl http://localhost:5000/api/v1/dispatch/health

# Estadísticas en vivo
curl http://localhost:5000/api/v1/dispatch/statistics?hours=1

# Distribución por severidad
curl http://localhost:5000/api/v1/dispatch/statistics/severity-distribution
```

---

## 6. PRÓXIMOS PASOS (Fase 2)

Una vez tengas 500+ registros en `ml.assignment_history`:

### 6.1 Entrenar Modelo XGBoost

```python
# src/ml/training/train_ambulance_selector.py

from xgboost import XGBClassifier
from sklearn.preprocessing import StandardScaler

# 1. Cargar datos
assignments = assignment_history_repo.get_assignments_for_training(min_samples=500)

# 2. Preparar features y target
X = prepare_features(assignments)
y = prepare_target(assignments)  # assigned_ambulance_id

# 3. Entrenar modelo
model = XGBClassifier(n_estimators=100, max_depth=7)
model.fit(X, y)

# 4. Evaluar
accuracy = model.score(X_test, y_test)

# 5. Guardar
model.save_model('models/ambulance_selector_v1.pkl')

# 6. Registrar en BD
trained_models_repo.register_model({
    'model_name': 'ambulance_selector',
    'model_type': 'xgboost',
    'accuracy': accuracy,
    'feature_importance': model.get_booster().get_score(),
    'model_file_path': 'models/ambulance_selector_v1.pkl'
})
```

### 6.2 Cambiar a Predicción ML

```python
# En dispatch_assignment_service.py, cambiar método
def assign_ambulance_and_personnel(self, dispatch_data):
    if self.config.PHASE == 2:
        # Usar modelo XGBoost en lugar de reglas
        return self._assign_with_ml_model(dispatch_data)
    else:
        # Usar reglas determinísticas (Fase 1)
        return self._assign_with_deterministic_rules(dispatch_data)
```

### 6.3 Comparar Fase 1 vs Fase 2

```sql
-- Comparar accuracy
SELECT
    'Phase 1 (Rules)' as phase,
    COUNT(*) as total,
    COUNT(CASE WHEN was_optimal = 1 THEN 1 END) as optimal,
    CAST(COUNT(CASE WHEN was_optimal = 1 THEN 1 END) as FLOAT) / COUNT(*) * 100 as optimal_rate
FROM ml.assignment_history
WHERE created_at >= DATEADD(DAY, -30, GETUTCDATE())
```

---

## 7. TROUBLESHOOTING

### Problema: "No ambulances available"

**Causa:** Las ambulancias proporcionadas están a >15km

**Solución:** Aumentar `AMBULANCE_MAX_DISTANCE_KM` en config

### Problema: "No paramedics available"

**Causa:** No hay paramédicos del nivel requerido

**Solución:** Fallback automático a siguiente nivel (senior → junior)

### Problema: Histórico no se está guardando

**Causa:** `assignment_history_repo` no inicializado correctamente

**Solución:** Verificar conexión a BD en `src/config/settings.py`

### Problema: Respuesta lenta en asignación

**Causa:** Demasiadas ambulancias o cálculos de distancia ineficientes

**Solución:**
1. Optimizar consulta de ambulancias disponibles
2. Implementar índices en tabla de ambulancias
3. Considerar dividir por zonas

---

## 8. REFERENCIAS

- Base de datos schema: `scripts/01_create_schema.sql`
- Diagrama ER: `scripts/SCHEMA_DIAGRAM.md`
- Service: `src/services/dispatch_assignment_service.py`
- Repository: `src/repositories/assignment_history_repository.py`
- API Routes: `src/api/dispatch_assignment_routes.py`

---

## 9. CONTACTO Y SOPORTE

Para dudas o problemas:
1. Revisar logs: `logs/app.log`
2. Revisar BD directamente: SQL Server Management Studio
3. Probar endpoints con Postman/curl
4. Revisar esta guía en sección "Troubleshooting"
