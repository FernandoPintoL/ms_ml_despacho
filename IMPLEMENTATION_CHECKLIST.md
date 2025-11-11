# Checklist de Implementación - Fase 1

## Resumen de Entregables

Se han creado **5 componentes principales** listos para integrar en tu sistema:

### 1. ✅ Base de Datos SQL Server

**Archivo:** `scripts/01_create_schema.sql`

**Qué se crea:**
- Schema `ml` con 8 tablas principales
- Índices optimizados
- Stored Procedures útiles
- Vistas para reportes
- Seed data (configuración Fase 1)

**Pasos para ejecutar:**

```bash
# 1. Conectarse a SQL Server
sqlcmd -S <server> -U <user> -P <password> -d master

# 2. Crear la BD
CREATE DATABASE ms_ml_despacho;
GO

# 3. Ejecutar script de schema
sqlcmd -S <server> -U <user> -P <password> -d ms_ml_despacho -i scripts/01_create_schema.sql

# 4. Verificar
SELECT * FROM sys.schemas WHERE name = 'ml';
SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'ml';
```

**Tablas creadas:**
- `ml.assignment_history` - Histórico de asignaciones (PRINCIPAL)
- `ml.trained_models` - Registro de modelos ML
- `ml.predictions_log` - Auditoría de predicciones
- `ml.features_cache` - Cache de features calculados
- `ml.model_configuration` - Configuración de parámetros
- `ml.metrics_summary` - KPIs agregados
- `ml.audit_log` - Log de auditoría
- Vistas: `v_assignment_history_summary`, `v_active_models`, `v_predictions_evaluation`

---

### 2. ✅ Servicio Python - Lógica de Asignación

**Archivo:** `src/services/dispatch_assignment_service.py`

**Qué proporciona:**

Clase `DispatchAssignmentService` con método principal:

```python
result = service.assign_ambulance_and_personnel(dispatch_data)
```

**Responsabilidades:**
- Seleccionar ambulancia más cercana (Regla 1)
- Validar disponibilidad (Regla 2)
- Asignar personal según severidad (Regla 3)
- Registrar en BD para entrenar ML
- Calcular confianza de asignación

**Características:**
- Cálculo de distancias con Haversine formula
- Fallback automático si no hay paramedics del nivel requerido
- Logging detallado
- Manejo de errores robusto

---

### 3. ✅ Repositorio de Datos

**Archivo:** `src/repositories/assignment_history_repository.py`

**Qué proporciona:**

Clase `AssignmentHistoryRepository` para:

```python
# Crear registros
history_id = repo.create_assignment_history(data)

# Leer datos
assignments = repo.get_recent_assignments(limit=50, hours=24)
stats = repo.get_assignment_statistics(hours=24)
optimal_rate = repo.get_optimal_assignment_rate(hours=168)

# Para entrenar ML
training_data = repo.get_assignments_for_training(min_samples=500)
```

**Métodos principales:**
- `create_assignment_history()` - Guardar asignación
- `get_assignment_by_dispatch()` - Obtener por ID
- `get_recent_assignments()` - Historial reciente
- `get_assignments_by_ambulance()` - Por ambulancia
- `get_assignment_statistics()` - Estadísticas período
- `get_ambulance_performance()` - Desempeño ambulancia
- `get_assignments_for_training()` - Datos para entrenar ML

---

### 4. ✅ API REST Endpoints

**Archivo:** `src/api/dispatch_assignment_routes.py`

**Endpoints disponibles:**

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/v1/dispatch/assign` | POST | Asignar ambulancia y personal |
| `/api/v1/dispatch/assign/batch` | POST | Asignaciones en lote |
| `/api/v1/dispatch/history/<id>` | GET | Obtener histórico de asignación |
| `/api/v1/dispatch/history/recent` | GET | Asignaciones recientes |
| `/api/v1/dispatch/history/ambulance/<id>` | GET | Histórico de ambulancia |
| `/api/v1/dispatch/statistics` | GET | Estadísticas globales |
| `/api/v1/dispatch/statistics/ambulance/<id>` | GET | Estadísticas ambulancia |
| `/api/v1/dispatch/statistics/severity-distribution` | GET | Distribución por severidad |
| `/api/v1/dispatch/health` | GET | Health check |

**Ejemplo de uso:**

```bash
# Asignar ambulancia
curl -X POST http://localhost:5000/api/v1/dispatch/assign \
  -H "Content-Type: application/json" \
  -d '{
    "dispatch_id": 123,
    "patient_latitude": 4.7110,
    "patient_longitude": -74.0721,
    "emergency_type": "trauma",
    "severity_level": 4,
    "available_ambulances": [...],
    "available_paramedics": [...]
  }'

# Obtener estadísticas
curl http://localhost:5000/api/v1/dispatch/statistics?hours=24

# Health check
curl http://localhost:5000/api/v1/dispatch/health
```

---

### 5. ✅ Documentación Completa

**Archivos:**
- `FASE_1_IMPLEMENTATION_GUIDE.md` - Guía paso a paso
- `scripts/SCHEMA_DIAGRAM.md` - Diagrama ER visual
- `IMPLEMENTATION_CHECKLIST.md` - Este archivo

---

## Checklist de Implementación

### Fase A: Instalación Base de Datos

- [ ] **1. Conectarse a SQL Server**
  ```bash
  sqlcmd -S <tu_servidor> -U sa -P <tu_password>
  ```

- [ ] **2. Crear BD ms_ml_despacho**
  ```sql
  CREATE DATABASE ms_ml_despacho;
  GO
  ```

- [ ] **3. Ejecutar script SQL**
  ```bash
  sqlcmd -S <tu_servidor> -U sa -P <tu_password> \
    -d ms_ml_despacho \
    -i scripts/01_create_schema.sql
  ```

- [ ] **4. Verificar tablas creadas**
  ```sql
  SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
  WHERE TABLE_SCHEMA = 'ml';
  ```

- [ ] **5. Verificar seed data (Fase 1 config)**
  ```sql
  SELECT * FROM ml.model_configuration
  WHERE config_name = 'phase1_deterministic_rules';
  ```

---

### Fase B: Integración Python

- [ ] **1. Copiar archivos a proyecto**
  ```bash
  cp src/services/dispatch_assignment_service.py <tu_proyecto>/src/services/
  cp src/repositories/assignment_history_repository.py <tu_proyecto>/src/repositories/
  cp src/api/dispatch_assignment_routes.py <tu_proyecto>/src/api/
  ```

- [ ] **2. Instalar dependencias (si no están)**
  ```bash
  pip install sqlalchemy python-dotenv
  ```

- [ ] **3. Configurar variables de entorno**
  ```bash
  # En .env o docker-compose.yml
  DATABASE_URL=mssql+pyodbc://user:password@server:1433/ms_ml_despacho?driver=ODBC+Driver+17+for+SQL+Server
  AMBULANCE_MAX_DISTANCE_KM=15
  ```

- [ ] **4. Registrar blueprint Flask**
  ```python
  # En src/main.py o app.py
  from src.api.dispatch_assignment_routes import dispatch_assignment_bp

  app.register_blueprint(dispatch_assignment_bp)
  ```

- [ ] **5. Inicializar repositorios en main**
  ```python
  from src.repositories.assignment_history_repository import AssignmentHistoryRepository
  from src.services.dispatch_assignment_service import DispatchAssignmentService

  assignment_history_repo = AssignmentHistoryRepository(db_connection)
  dispatch_service = DispatchAssignmentService(
      assignment_history_repo=assignment_history_repo
  )
  ```

---

### Fase C: Testing

- [ ] **1. Verificar endpoint de salud**
  ```bash
  curl http://localhost:5000/api/v1/dispatch/health
  ```

- [ ] **2. Enviar asignación de prueba**
  ```bash
  curl -X POST http://localhost:5000/api/v1/dispatch/assign \
    -H "Content-Type: application/json" \
    -d '{
      "dispatch_id": 1,
      "patient_latitude": 4.7110,
      "patient_longitude": -74.0721,
      "emergency_type": "trauma",
      "severity_level": 3,
      "available_ambulances": [
        {
          "id": 1,
          "latitude": 4.7120,
          "longitude": -74.0710,
          "status": "available",
          "crew_level": "junior"
        }
      ],
      "available_paramedics": [
        {"id": 10, "level": "junior", "status": "available"},
        {"id": 11, "level": "junior", "status": "available"}
      ],
      "available_nurses": []
    }'
  ```

- [ ] **3. Verificar que se guardó en BD**
  ```sql
  SELECT TOP 1 * FROM ml.assignment_history
  ORDER BY created_at DESC;
  ```

- [ ] **4. Obtener estadísticas**
  ```bash
  curl http://localhost:5000/api/v1/dispatch/statistics?hours=1
  ```

- [ ] **5. Revisar logs**
  ```bash
  tail -f logs/app.log
  ```

---

### Fase D: Integración con MS-DESPACHO

- [ ] **1. Actualizar MS-DESPACHO para llamar a MS-ML-DESPACHO**
  ```javascript
  // En ms-despacho (Node.js)
  const response = await fetch('http://localhost:5000/api/v1/dispatch/assign', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      dispatch_id: req.body.id,
      patient_latitude: req.body.lat,
      patient_longitude: req.body.lon,
      emergency_type: req.body.type,
      severity_level: req.body.severity,
      available_ambulances: ambulances,
      available_paramedics: paramedics,
      available_nurses: nurses
    })
  });

  const assignment = await response.json();
  ```

- [ ] **2. Usar resultado en MS-DESPACHO**
  ```javascript
  if (assignment.success) {
    // Asignar ambulancia y personal
    await assignAmbulance(assignment.ambulance_id);
    await assignParamedics(assignment.paramedic_ids);

    // Notificar paramédico
    await notifyParamedic(assignment.paramedic_ids[0]);
  }
  ```

- [ ] **3. Registrar resultado post-despacho**
  ```javascript
  // Cuando se completa el despacho
  await fetch(`http://localhost:5000/api/v1/dispatch/history/${assignment.history_id}`, {
    method: 'PUT',
    body: {
      actual_response_time_minutes: responseTime,
      patient_outcome: 'transferred_to_hospital',
      was_optimal: true
    }
  });
  ```

---

### Fase E: Monitoreo en Producción

- [ ] **1. Configurar logging**
  ```bash
  # En .env
  LOG_LEVEL=INFO
  VERBOSE_LOGGING=false
  ```

- [ ] **2. Configurar alertas**
  - [ ] Alerta si más del 10% de asignaciones fallan
  - [ ] Alerta si tiempo promedio de asignación > 5 segundos
  - [ ] Alerta si BD tiene >1M registros

- [ ] **3. Dashboard de monitoreo**
  - [ ] Endpoint para estadísticas: `/api/v1/dispatch/statistics`
  - [ ] Endpoint para desempeño ambulancia: `/api/v1/dispatch/statistics/ambulance/<id>`
  - [ ] Consulta SQL para distribución por severidad

- [ ] **4. Backup automático de BD**
  ```bash
  # SQL Server Agent job
  BACKUP DATABASE ms_ml_despacho TO DISK = '/backups/ms_ml_despacho_daily.bak'
  ```

---

### Fase F: Preparación para Fase 2 (ML)

- [ ] **1. Monitorear crecimiento de datos**
  ```sql
  SELECT COUNT(*) as total_records FROM ml.assignment_history;
  -- Objetivo: 500+ registros para entrenar en Fase 2
  ```

- [ ] **2. Analizar distribución de severidades**
  ```sql
  SELECT severity_level, COUNT(*) as count
  FROM ml.assignment_history
  GROUP BY severity_level;
  ```

- [ ] **3. Revisar tasas de optimalidad**
  ```sql
  SELECT
    CAST(COUNT(CASE WHEN was_optimal = 1 THEN 1 END) as FLOAT) / COUNT(*) * 100 as optimal_rate
  FROM ml.assignment_history;
  ```

- [ ] **4. Preparar ambiente para Fase 2**
  - [ ] Instalar librerías ML: `pip install xgboost scikit-learn`
  - [ ] Crear directorio para modelos: `mkdir -p models/`
  - [ ] Crear script de entrenamiento: `src/ml/training/train_ambulance_selector.py`

---

## Estado de Implementación

### Completado ✅

- ✅ Esquema SQL Server 100% listo
- ✅ 8 tablas con índices y constraints
- ✅ Stored Procedures útiles
- ✅ Servicio Python Fase 1 implementado
- ✅ Repositorio de datos funcional
- ✅ 9 endpoints REST documentados
- ✅ Documentación completa

### Próximos Pasos (Fase 2)

- ⏳ Recolectar 500+ registros históricos (2-3 meses)
- ⏳ Entrenar modelo XGBoost
- ⏳ Integrar predicciones ML en lugar de reglas
- ⏳ Optimizar con feedback y reentrenamiento

---

## Estimación de Esfuerzo

| Actividad | Tiempo |
|-----------|--------|
| Instalación BD | 30 minutos |
| Integración código Python | 1-2 horas |
| Testing y debugging | 2-3 horas |
| Integración con MS-DESPACHO | 4-6 horas |
| Deployment producción | 2-3 horas |
| **Total Fase 1** | **10-16 horas** |
| Recolección datos | 2-3 meses |
| Entrenamiento ML (Fase 2) | 2-3 semanas |

---

## Archivos Referencia Rápida

```
ms_ml_despacho/
├── scripts/
│   ├── 01_create_schema.sql              ← SQL para BD
│   └── SCHEMA_DIAGRAM.md                 ← Diagrama ER
├── src/
│   ├── services/
│   │   └── dispatch_assignment_service.py ← Lógica asignación
│   ├── repositories/
│   │   └── assignment_history_repository.py ← Data layer
│   └── api/
│       └── dispatch_assignment_routes.py  ← REST endpoints
├── FASE_1_IMPLEMENTATION_GUIDE.md        ← Guía completa
└── IMPLEMENTATION_CHECKLIST.md           ← Este archivo
```

---

## Contacto y Preguntas

**¿Problema con la BD?**
- Revisar: `scripts/01_create_schema.sql`
- Verificar conectividad a SQL Server

**¿Problema con endpoints?**
- Revisar logs: `logs/app.log`
- Probar con curl/Postman

**¿Duda sobre lógica?**
- Revisar: `FASE_1_IMPLEMENTATION_GUIDE.md` sección 3

**¿Listo para Fase 2?**
- Cuando tengas 500+ registros en `ml.assignment_history`
- Revisar sección "Próximos Pasos (Fase 2)"

---

## Última Actualización

**Fecha:** 2025-11-10
**Versión:** 1.0.0
**Estado:** Listo para Implementación
