# Testing Fase 1 - Guía Paso a Paso

## 🎯 Objetivo

Verificar que todos los endpoints de Fase 1 funcionan correctamente.

---

## ✅ PASO 1: Iniciar la Aplicación

### Opción A: Ejecutar desde línea de comandos

```bash
# En la carpeta raíz del proyecto
cd D:\SWII\micro_servicios\ms_ml_despacho

# Activar virtual environment (si tienes)
# venv\Scripts\activate

# Instalar dependencias necesarias (si faltan)
pip install pyodbc flask flask-cors

# Ejecutar la aplicación
python -m src.main

# O directamente:
python src/main.py
```

**Esperado:**
```
 * Running on http://0.0.0.0:5000
 * Environment: development
 * Debug mode: on
```

### Opción B: Ejecutar con Flask CLI

```bash
set FLASK_APP=src/main.py
set FLASK_ENV=development
flask run
```

---

## 🧪 PASO 2: Testing de Endpoints

Abre **Postman** o **curl** y prueba los siguientes endpoints:

### Test 1: Health Check

```bash
curl http://localhost:5000/api/v1/dispatch/health
```

**Respuesta esperada (200):**
```json
{
  "status": "healthy",
  "service": "dispatch_assignment",
  "phase": 1,
  "timestamp": "2025-11-10T23:30:00Z"
}
```

---

### Test 2: Asignar Ambulancia (PRINCIPAL)

```bash
curl -X POST http://localhost:5000/api/v1/dispatch/assign \
  -H "Content-Type: application/json" \
  -d '{
    "dispatch_id": 1001,
    "patient_latitude": 4.7110,
    "patient_longitude": -74.0721,
    "emergency_type": "trauma",
    "severity_level": 4,
    "zone_code": "ZONA_CENTRO",
    "available_ambulances": [
      {
        "id": 1,
        "latitude": 4.7120,
        "longitude": -74.0710,
        "status": "available",
        "crew_level": "senior",
        "unit_type": "advanced"
      },
      {
        "id": 2,
        "latitude": 4.7050,
        "longitude": -74.0800,
        "status": "available",
        "crew_level": "junior",
        "unit_type": "basic"
      }
    ],
    "available_paramedics": [
      {"id": 101, "level": "senior", "status": "available"},
      {"id": 102, "level": "junior", "status": "available"}
    ],
    "available_nurses": [
      {"id": 201, "status": "available"}
    ]
  }'
```

**Respuesta esperada (200):**
```json
{
  "success": true,
  "dispatch_id": 1001,
  "ambulance_id": 1,
  "paramedic_ids": [101, 102],
  "nurse_id": 201,
  "distance_km": 0.15,
  "confidence": 0.95,
  "assignment_type": "deterministic_rules",
  "phase": 1,
  "reasoning": "...",
  "timestamp": "2025-11-10T23:30:15.123Z",
  "history_id": 5001
}
```

✅ **Si ves esto, significa que:**
- La BD está conectada
- Los datos se guardaron en `ml.assignment_history`
- Todo funciona

---

### Test 3: Asignaciones en Lote

```bash
curl -X POST http://localhost:5000/api/v1/dispatch/assign/batch \
  -H "Content-Type: application/json" \
  -d '{
    "dispatches": [
      {
        "dispatch_id": 1002,
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
          {"id": 101, "level": "junior", "status": "available"},
          {"id": 102, "level": "junior", "status": "available"}
        ]
      }
    ]
  }'
```

---

### Test 4: Obtener Estadísticas

```bash
curl http://localhost:5000/api/v1/dispatch/statistics?hours=24
```

**Respuesta esperada:**
```json
{
  "success": true,
  "period_hours": 24,
  "statistics": {
    "total_assignments": 1,
    "optimal_assignments": 1,
    "optimal_rate": 100.0,
    "avg_response_time": null,
    "avg_optimization_score": null,
    "avg_patient_satisfaction": null,
    "unique_ambulances": 1
  }
}
```

---

### Test 5: Obtener Histórico

```bash
curl http://localhost:5000/api/v1/dispatch/history/1001
```

---

## 🔍 PASO 3: Verificar Datos en BD

Abre **SQL Server Management Studio** y ejecuta estas consultas:

### Verificar que se guardaron los datos

```sql
-- Ver últimas asignaciones
SELECT TOP 5
  id,
  dispatch_id,
  emergency_type,
  severity_level,
  assigned_ambulance_id,
  created_at
FROM ml.assignment_history
ORDER BY created_at DESC
```

**Esperado:** Ver filas con los datos que acabas de enviar

### Ver estadísticas

```sql
-- Contar total de asignaciones
SELECT COUNT(*) as total_assignments FROM ml.assignment_history

-- Ver distribución por severidad
SELECT severity_level, COUNT(*) as count
FROM ml.assignment_history
GROUP BY severity_level
```

---

## 📋 Checklist de Verificación

- [ ] Health check responde (Test 1)
- [ ] Asignación individual funciona (Test 2)
- [ ] Se recibe ambulancia_id en respuesta
- [ ] Se reciben paramedic_ids en respuesta
- [ ] La confianza es > 0.5
- [ ] El history_id es un número
- [ ] Asignaciones en lote funcionan (Test 3)
- [ ] Estadísticas se calculan (Test 4)
- [ ] Datos se ven en SQL Server (PASO 3)

---

## ❌ Si algo falla

### Error: "Cannot connect to database"

**Solución:**
```bash
# Verifica que la BD está corriendo
# En SQL Server Management Studio conecta a 192.168.1.38

# Verifica DATABASE_URL en .env:
DATABASE_URL=mssql+pyodbc://sa:1234@192.168.1.38:1433/ms_ml_despacho?driver=ODBC+Driver+17+for+SQL+Server
```

### Error: "No module named 'dispatch_assignment_routes'"

**Solución:**
- Verifica que el archivo existe: `src/api/dispatch_assignment_routes.py`
- Revisa que `main.py` tiene el `import` correcto (línea 150)

### Error: "No ambulances available"

**Solución:**
- Es normal si envías `available_ambulances: []`
- Asegúrate de enviar al menos 1 ambulancia en disponibles

### Error en BD: "Table 'ml.assignment_history' not found"

**Solución:**
- Ejecuta nuevamente `scripts/03_SCHEMA_LIMPIO.sql` en SSMS
- Verifica que las 7 tablas están creadas en SQL Server

---

## 🎯 Próximo Paso

Una vez todos los tests pasen ✅:

1. **Paso 8:** Verificar datos completos en BD
2. **Paso 9:** Integración con MS-DESPACHO
3. **Paso 10:** Deploy a producción

---

## 📊 Monitoreo en Tiempo Real

Para ver los logs mientras haces requests:

```bash
# En terminal diferente, monitorea los logs
tail -f logs/app.log

# O en otra ventana, usa curl con -v para ver detalles
curl -v http://localhost:5000/api/v1/dispatch/health
```

---

**¿Ya ejecutaste los tests?** Confirma cuáles pasaron y cuáles fallaron 👇
