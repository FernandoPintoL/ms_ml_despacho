# Diagrama de Esquema - MS ML Despacho

## Diagrama Entidad-Relación (ER)

```
┌─────────────────────────────────────────────────────────────────┐
│                    ml.assignment_history                         │
├─────────────────────────────────────────────────────────────────┤
│ PK │ id (INT)                                                     │
│    │ dispatch_id (INT)                                            │
│    │                                                              │
│    │ FEATURES (INPUT):                                            │
│    │ ├─ emergency_latitude, emergency_longitude                  │
│    │ ├─ emergency_type (trauma, paro, etc)                      │
│    │ ├─ severity_level (1-5)                                     │
│    │ ├─ hour_of_day (0-23), day_of_week (0-6)                   │
│    │ ├─ zone_code (sector de ciudad)                             │
│    │ ├─ available_ambulances_count                               │
│    │ ├─ nearest_ambulance_distance_km                            │
│    │ ├─ paramedics_available_count                               │
│    │ ├─ active_dispatches_count                                  │
│    │ └─ ambulances_busy_percentage                               │
│    │                                                              │
│    │ TARGET (OUTPUT):                                             │
│    │ ├─ assigned_ambulance_id ★                                  │
│    │ ├─ assigned_paramedic_ids (JSON) ★                          │
│    │ └─ assigned_paramedic_levels (JSON) ★                       │
│    │                                                              │
│    │ POST-ASIGNACIÓN:                                             │
│    │ ├─ actual_response_time_minutes                             │
│    │ ├─ patient_outcome                                          │
│    │ ├─ was_optimal (LABEL para entrenar)                        │
│    │ └─ optimization_score (0-1)                                 │
│    │                                                              │
│    │ created_at, updated_at                                       │
└─────────────────────────────────────────────────────────────────┘
         │
         │ (recolecta datos para entrenar)
         │
         ↓
┌─────────────────────────────────────────────────────────────────┐
│                    ml.trained_models                             │
├─────────────────────────────────────────────────────────────────┤
│ PK │ id (INT)                                                     │
│    │ model_name (VARCHAR)                                         │
│    │ model_type (xgboost, random_forest, rules)                  │
│    │ model_version (1.0.0, 1.1.0)                                │
│    │                                                              │
│    │ input_features (JSON)                                        │
│    │ target_variable (VARCHAR)                                    │
│    │                                                              │
│    │ MÉTRICAS:                                                    │
│    │ ├─ accuracy, precision, recall, f1_score                    │
│    │ ├─ training_samples_count                                   │
│    │ ├─ training_date                                            │
│    │ └─ validation_accuracy, test_accuracy                       │
│    │                                                              │
│    │ hyperparameters (JSON)                                       │
│    │ feature_importance (JSON)                                    │
│    │ model_file_path (ruta al .pkl)                              │
│    │                                                              │
│    │ is_active, is_production                                     │
│    │ last_used_at                                                 │
└─────────────────────────────────────────────────────────────────┘
         │
         │ (predice con modelo)
         │
         ↓
┌─────────────────────────────────────────────────────────────────┐
│                   ml.predictions_log                             │
├─────────────────────────────────────────────────────────────────┤
│ PK │ id (INT)                                                     │
│ FK │ model_id (INT) → trained_models                             │
│    │ dispatch_id (INT)                                            │
│    │ request_timestamp                                            │
│    │                                                              │
│    │ input_features (JSON - features usadas)                      │
│    │                                                              │
│    │ PREDICCIÓN:                                                  │
│    │ ├─ predicted_ambulance_id                                    │
│    │ ├─ predicted_paramedic_ids (JSON)                           │
│    │ └─ prediction_confidence (0-1)                              │
│    │                                                              │
│    │ REALIDAD:                                                    │
│    │ ├─ actual_ambulance_id                                       │
│    │ ├─ actual_paramedic_ids (JSON)                              │
│    │ └─ actual_response_time_minutes                             │
│    │                                                              │
│    │ EVALUACIÓN:                                                  │
│    │ ├─ prediction_correct (BOOLEAN)                             │
│    │ ├─ prediction_accuracy_score (0-1)                          │
│    │ └─ feedback_score                                            │
│    │                                                              │
│    │ execution_status, error_message                              │
└─────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────┐
│              ml.model_configuration                              │
├─────────────────────────────────────────────────────────────────┤
│ PK │ id (INT)                                                     │
│    │ config_name (phase1_rules, phase2_xgboost)                  │
│    │ config_type (phase, algorithm, feature)                     │
│    │                                                              │
│    │ configuration_json (NVARCHAR(MAX))                          │
│    │ ├─ phase number                                              │
│    │ ├─ algorithm type                                            │
│    │ ├─ rules for phase 1                                        │
│    │ ├─ paramedic assignment rules                               │
│    │ └─ hyperparameters for phase 2+                             │
│    │                                                              │
│    │ is_active, version                                           │
│    │ created_at, updated_at, created_by                          │
└─────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────┐
│                  ml.features_cache                               │
├─────────────────────────────────────────────────────────────────┤
│ PK │ id (INT)                                                     │
│    │ dispatch_id (INT)                                            │
│    │ features_json (NVARCHAR(MAX))                               │
│    │ calculated_at, expires_at                                    │
└─────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────┐
│                 ml.metrics_summary                               │
├─────────────────────────────────────────────────────────────────┤
│ PK │ id (INT)                                                     │
│    │ metric_date, metric_hour                                     │
│    │                                                              │
│    │ VOLUMEN: total_dispatches, completed, optimal               │
│    │ DESEMPEÑO: avg response time, distance, optimization_score  │
│    │ MODELOS: accuracy, f1_score, confidence_avg                 │
│    │ AMBULANCIAS: utilization_rate, busy_percentage              │
│    │ PERSONAL: paramedics_utilization, avg_team_size             │
│    │ CALIDAD: patient satisfaction, paramedic satisfaction       │
└─────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────┐
│                    ml.audit_log                                  │
├─────────────────────────────────────────────────────────────────┤
│ PK │ id (INT)                                                     │
│    │ event_type, entity_type, entity_id                          │
│    │ action (CREATE, UPDATE, DELETE)                             │
│    │ old_values, new_values (JSON)                               │
│    │ user_id, ip_address                                          │
│    │ status (SUCCESS, FAILED)                                     │
│    │ error_message                                                │
│    │ created_at                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Explicación del Flujo de Datos

### Fase 1: Reglas Determinísticas

```
┌─────────────────────────────────────────────────────────────┐
│ Solicitud de Ambulancia (n8n / MS Recepción)               │
│ - GPS location                                              │
│ - Tipo emergencia                                           │
│ - Severidad                                                 │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ↓
         ┌───────────────────┐
         │ MS ML DESPACHO    │
         │ FASE 1 (REGLAS)   │
         └───────┬───────────┘
                 │
         ┌───────↓────────────────────────────┐
         │ 1. Feature Engineering              │
         │    ├─ Calcula distancias GPS       │
         │    ├─ Obtiene ambulancias disponibles
         │    ├─ Cuenta personal disponible   │
         │    └─ Extrae contexto (hora, día)  │
         └───────┬────────────────────────────┘
                 │
         ┌───────↓────────────────────────────┐
         │ 2. Aplica Reglas Determinísticas    │
         │    ├─ Regla 1: Ambulancia CERCANA  │
         │    │   (min distancia)              │
         │    ├─ Regla 2: Validar disponibilidad
         │    └─ Regla 3: Asignar personal    │
         │        por severidad               │
         └───────┬────────────────────────────┘
                 │
         ┌───────↓────────────────────────────┐
         │ 3. Guardar en assignment_history    │
         │    (Datos para entrenar ML)         │
         └───────┬────────────────────────────┘
                 │
         ┌───────↓────────────────────────────┐
         │ 4. Retornar Decisión:               │
         │    {                                │
         │      "ambulance_id": 42,            │
         │      "paramedic_ids": [1, 5, 8],  │
         │      "confidence": 1.0,             │
         │      "phase": "deterministic"       │
         │    }                                │
         └───────┬────────────────────────────┘
                 │
                 ↓
      ┌──────────────────────────────┐
      │ MS DESPACHO                  │
      │ ├─ Ejecuta asignación        │
      │ ├─ Notifica paramédico       │
      │ └─ Registra en su BD         │
      └──────────────────────────────┘
```

### Fase 2: Machine Learning (Futuro)

```
Después de 2-3 meses con datos reales en assignment_history:

┌─────────────────────────────────────┐
│ 1. Entrenar Modelo XGBoost          │
│    ├─ Datos: assignment_history     │
│    ├─ Input: features               │
│    ├─ Target: assigned_ambulance_id │
│    └─ Output: trained_models        │
└─────────────────────────────────────┘
           │
           ↓
┌─────────────────────────────────────┐
│ 2. Usar Modelo en Predicciones      │
│    ├─ Cargar modelo de trained_models
│    ├─ Pasar features                │
│    ├─ Obtener predicción            │
│    └─ Registrar en predictions_log  │
└─────────────────────────────────────┘
           │
           ↓
┌─────────────────────────────────────┐
│ 3. Evaluar Desempeño                │
│    ├─ Accuracy: ¿ambulancia correcta?
│    ├─ Feedback: ¿fue óptima?        │
│    └─ Reentrenar si accuracy baja   │
└─────────────────────────────────────┘
```

## Índices Estratégicos

```
assignment_history:
├─ PK: id
├─ idx_dispatch_id          → Búsquedas por dispatch
├─ idx_created_at           → Datos recientes
├─ idx_severity             → Histórico por severidad
├─ idx_ambulance            → Histórico por ambulancia
└─ idx_optimal              → Filtrar asignaciones óptimas

trained_models:
├─ PK: id
├─ UNIQUE: model_name + model_version
├─ idx_active               → Modelos activos
└─ idx_production           → Modelos en producción

predictions_log:
├─ PK: id
├─ FK: model_id
├─ idx_dispatch             → Predicciones por despacho
├─ idx_model                → Predicciones por modelo
├─ idx_created              → Historial temporal
└─ idx_correct              → Predicciones correctas vs incorrectas
```

## Vistas Principales

```
v_assignment_history_summary
├─ Resumen de asignaciones realizadas
├─ Incluye: dispatch_id, emergency_type, severity, ambulancia, outcome
└─ Usada para: reportes y auditoría

v_active_models
├─ Modelos activos en el sistema
├─ Solo modelos con is_active = 1
└─ Usada para: verificar qué modelo se está usando

v_predictions_evaluation
├─ Predicciones con evaluación
├─ Relaciona predictions_log con trained_models
└─ Usada para: evaluar accuracy del modelo
```

## Constraints y Validaciones

```
assignment_history:
├─ severity_level: CHECK (severity_level BETWEEN 1 AND 5)
├─ hour_of_day: CHECK (hour_of_day BETWEEN 0 AND 23)
├─ day_of_week: CHECK (day_of_week BETWEEN 0 AND 6)
├─ paramedic_satisfaction_rating: CHECK (BETWEEN 1 AND 5)
└─ patient_satisfaction_rating: CHECK (BETWEEN 1 AND 5)

trained_models:
├─ UNIQUE (model_name, model_version)
├─ accuracy: DECIMAL(5,4) → 0.0000 to 1.0000
└─ f1_score: DECIMAL(5,4) → 0.0000 to 1.0000

predictions_log:
└─ FOREIGN KEY (model_id) → trained_models(id)
```
