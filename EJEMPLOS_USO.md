# Ejemplos de Uso - Fase 1

## 1. CREAR UNA ASIGNACIÓN (Endpoint Principal)

### Ejemplo 1: Emergencia de Severidad Alta (trauma)

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
      {"id": 102, "level": "junior", "status": "available"},
      {"id": 103, "level": "junior", "status": "available"}
    ],
    "available_nurses": [
      {"id": 201, "status": "available"}
    ]
  }'
```

**Respuesta Esperada (200 OK):**

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
  "reasoning": "Nearest ambulance at 0.15km (crew: senior). Personnel: Severity 4: 2 paramedics + nurse for high severity",
  "timestamp": "2025-11-10T12:34:56.789Z",
  "history_id": 5001
}
```

**Explicación:**
- ✅ Se seleccionó ambulancia 1 (más cercana: 0.15km vs 0.77km)
- ✅ Se asignaron 2 paramédicos (1 senior + 1 junior) por severidad 4
- ✅ Se asignó 1 enfermero (required para severidad 4)
- ✅ Confianza muy alta (0.95) porque está muy cerca
- ✅ Se guardó en BD con history_id=5001 para actualizar después

---

### Ejemplo 2: Emergencia de Severidad Crítica (paro cardíaco)

```bash
curl -X POST http://localhost:5000/api/v1/dispatch/assign \
  -H "Content-Type: application/json" \
  -d '{
    "dispatch_id": 1002,
    "patient_latitude": 4.6500,
    "patient_longitude": -74.1000,
    "emergency_type": "paro_cardiaco",
    "severity_level": 5,
    "zone_code": "ZONA_NORTE",
    "available_ambulances": [
      {
        "id": 3,
        "latitude": 4.6510,
        "longitude": -74.0995,
        "status": "available",
        "crew_level": "senior",
        "unit_type": "advanced"
      }
    ],
    "available_paramedics": [
      {"id": 104, "level": "senior", "status": "available"},
      {"id": 105, "level": "senior", "status": "available"},
      {"id": 106, "level": "junior", "status": "available"},
      {"id": 107, "level": "junior", "status": "available"}
    ],
    "available_nurses": [
      {"id": 202, "status": "available"}
    ]
  }'
```

**Respuesta Esperada:**

```json
{
  "success": true,
  "dispatch_id": 1002,
  "ambulance_id": 3,
  "paramedic_ids": [104, 105, 106],
  "nurse_id": 202,
  "distance_km": 0.17,
  "confidence": 0.95,
  "assignment_type": "deterministic_rules",
  "phase": 1,
  "reasoning": "Nearest ambulance at 0.17km (crew: senior). Personnel: Severity 5: 3 paramedics + nurse for critical case",
  "timestamp": "2025-11-10T12:35:20.123Z",
  "history_id": 5002
}
```

**Explicación:**
- ✅ Se asignaron **3 paramédicos** (2 senior + 1 junior) por ser crítico
- ✅ Se asignó enfermero (required para severidad 5)
- ✅ Confianza máxima (0.95) por proximidad

---

### Ejemplo 3: Fallo - No hay ambulancias disponibles

```bash
curl -X POST http://localhost:5000/api/v1/dispatch/assign \
  -H "Content-Type: application/json" \
  -d '{
    "dispatch_id": 1003,
    "patient_latitude": 4.5000,
    "patient_longitude": -74.2000,
    "emergency_type": "intoxicacion",
    "severity_level": 2,
    "available_ambulances": [],
    "available_paramedics": [
      {"id": 108, "level": "junior", "status": "available"}
    ]
  }'
```

**Respuesta Esperada (400 Bad Request):**

```json
{
  "success": false,
  "dispatch_id": 1003,
  "error": "No ambulances available",
  "timestamp": "2025-11-10T12:36:00.456Z",
  "phase": 1
}
```

---

## 2. ASIGNACIONES EN LOTE

```bash
curl -X POST http://localhost:5000/api/v1/dispatch/assign/batch \
  -H "Content-Type: application/json" \
  -d '{
    "dispatches": [
      {
        "dispatch_id": 2001,
        "patient_latitude": 4.7110,
        "patient_longitude": -74.0721,
        "emergency_type": "trauma",
        "severity_level": 3,
        "available_ambulances": [
          {"id": 1, "latitude": 4.7120, "longitude": -74.0710, "status": "available", "crew_level": "junior"}
        ],
        "available_paramedics": [
          {"id": 101, "level": "junior", "status": "available"},
          {"id": 102, "level": "junior", "status": "available"}
        ]
      },
      {
        "dispatch_id": 2002,
        "patient_latitude": 4.6500,
        "patient_longitude": -74.1000,
        "emergency_type": "quemadura",
        "severity_level": 2,
        "available_ambulances": [
          {"id": 2, "latitude": 4.6510, "longitude": -74.0995, "status": "available", "crew_level": "junior"}
        ],
        "available_paramedics": [
          {"id": 103, "level": "junior", "status": "available"}
        ]
      }
    ]
  }'
```

**Respuesta Esperada:**

```json
{
  "success": true,
  "total": 2,
  "successful": 2,
  "failed": 0,
  "results": [
    {
      "success": true,
      "dispatch_id": 2001,
      "ambulance_id": 1,
      "paramedic_ids": [101, 102],
      "distance_km": 0.15,
      "confidence": 0.90,
      "history_id": 5003
    },
    {
      "success": true,
      "dispatch_id": 2002,
      "ambulance_id": 2,
      "paramedic_ids": [103],
      "distance_km": 0.17,
      "confidence": 0.85,
      "history_id": 5004
    }
  ]
}
```

---

## 3. OBTENER HISTÓRICO

### Obtener asignación específica

```bash
curl http://localhost:5000/api/v1/dispatch/history/1001
```

**Respuesta:**

```json
{
  "success": true,
  "dispatch_id": 1001,
  "assignment": {
    "id": 5001,
    "dispatch_id": 1001,
    "emergency_latitude": 4.7110,
    "emergency_longitude": -74.0721,
    "emergency_type": "trauma",
    "severity_level": 4,
    "zone_code": "ZONA_CENTRO",
    "assigned_ambulance_id": 1,
    "assigned_paramedic_ids": [101, 102],
    "assigned_paramedic_levels": ["senior", "junior"],
    "distance_km": 0.15,
    "actual_response_time_minutes": null,
    "patient_outcome": null,
    "was_optimal": null,
    "created_at": "2025-11-10T12:34:56.789Z"
  }
}
```

---

### Obtener asignaciones recientes (últimas 24 horas)

```bash
curl 'http://localhost:5000/api/v1/dispatch/history/recent?limit=10&hours=24'
```

**Respuesta:**

```json
{
  "success": true,
  "count": 8,
  "limit": 10,
  "hours": 24,
  "assignments": [
    {
      "id": 5008,
      "dispatch_id": 1008,
      "emergency_type": "trauma",
      "severity_level": 3,
      "assigned_ambulance_id": 1,
      "assigned_paramedic_ids": [101, 102],
      "actual_response_time_minutes": 3.5,
      "patient_outcome": "transferred_to_hospital",
      "was_optimal": true,
      "created_at": "2025-11-10T15:20:00Z"
    },
    {
      "id": 5007,
      "dispatch_id": 1007,
      "emergency_type": "paro",
      "severity_level": 5,
      "assigned_ambulance_id": 2,
      "assigned_paramedic_ids": [104, 105, 106],
      "actual_response_time_minutes": 2.1,
      "patient_outcome": "treated_on_site",
      "was_optimal": true,
      "created_at": "2025-11-10T14:45:00Z"
    }
    // ... más registros
  ]
}
```

---

### Obtener histórico de una ambulancia

```bash
curl 'http://localhost:5000/api/v1/dispatch/history/ambulance/1'
```

**Respuesta:**

```json
{
  "success": true,
  "ambulance_id": 1,
  "total_assignments": 45,
  "assignments": [
    {
      "id": 5001,
      "dispatch_id": 1001,
      "emergency_type": "trauma",
      "severity_level": 4,
      "assigned_paramedic_ids": [101, 102],
      "actual_response_time_minutes": 2.8,
      "patient_outcome": "transferred_to_hospital",
      "was_optimal": true,
      "created_at": "2025-11-10T12:34:56Z"
    },
    // ... más registros
  ]
}
```

---

## 4. ESTADÍSTICAS

### Estadísticas globales (últimas 24 horas)

```bash
curl 'http://localhost:5000/api/v1/dispatch/statistics?hours=24'
```

**Respuesta:**

```json
{
  "success": true,
  "period_hours": 24,
  "statistics": {
    "total_assignments": 150,
    "optimal_assignments": 127,
    "optimal_rate": 84.67,
    "avg_response_time": 3.2,
    "avg_optimization_score": 0.85,
    "avg_patient_satisfaction": 4.2,
    "unique_ambulances": 8
  }
}
```

**Interpretación:**
- 150 asignaciones en últimas 24h
- 127 fueron óptimas (84.67%)
- Tiempo promedio respuesta: 3.2 minutos
- Score de optimización: 0.85/1.0
- Satisfacción paciente: 4.2/5.0

---

### Estadísticas de una ambulancia

```bash
curl 'http://localhost:5000/api/v1/dispatch/statistics/ambulance/1?hours=168'
```

**Respuesta:**

```json
{
  "success": true,
  "ambulance_id": 1,
  "period_hours": 168,
  "performance": {
    "total_assignments": 45,
    "optimal_assignments": 38,
    "optimal_rate": 84.44,
    "avg_response_time": 2.8,
    "avg_optimization_score": 0.87,
    "avg_patient_satisfaction": 4.4
  }
}
```

---

### Distribución de severidades

```bash
curl 'http://localhost:5000/api/v1/dispatch/statistics/severity-distribution?hours=168'
```

**Respuesta:**

```json
{
  "success": true,
  "period_hours": 168,
  "distribution": {
    "1": 15,
    "2": 45,
    "3": 120,
    "4": 85,
    "5": 35
  }
}
```

**Interpretación:**
- Severidad 1 (baja): 15 casos
- Severidad 2 (bajo-media): 45 casos
- Severidad 3 (media): 120 casos
- Severidad 4 (alta): 85 casos
- Severidad 5 (crítica): 35 casos

---

## 5. HEALTH CHECK

```bash
curl http://localhost:5000/api/v1/dispatch/health
```

**Respuesta:**

```json
{
  "status": "healthy",
  "service": "dispatch_assignment",
  "phase": 1,
  "timestamp": "2025-11-10T12:40:00.123Z"
}
```

---

## 6. INTEGRACIÓN CON MS-DESPACHO (Node.js)

```javascript
// En ms-despacho (dispatch controller)

async function assignAmbulanceAndPersonnel(req, res) {
  try {
    const {
      dispatch_id,
      patient_latitude,
      patient_longitude,
      emergency_type,
      severity_level,
      zone_code
    } = req.body;

    // Obtener ambulancias disponibles desde tu BD
    const ambulances = await Ambulance.find({ status: 'available' });

    // Obtener paramédicos disponibles
    const paramedics = await Paramedic.find({ status: 'available' });
    const nurses = await Nurse.find({ status: 'available' });

    // Llamar a MS-ML-DESPACHO
    const response = await fetch('http://localhost:5000/api/v1/dispatch/assign', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dispatch_id,
        patient_latitude,
        patient_longitude,
        emergency_type,
        severity_level,
        zone_code,
        available_ambulances: ambulances.map(a => ({
          id: a.id,
          latitude: a.current_latitude,
          longitude: a.current_longitude,
          status: a.status,
          crew_level: a.crew_level
        })),
        available_paramedics: paramedics.map(p => ({
          id: p.id,
          level: p.level,
          status: p.status
        })),
        available_nurses: nurses.map(n => ({
          id: n.id,
          status: n.status
        }))
      })
    });

    const assignment = await response.json();

    if (assignment.success) {
      // Guardar asignación
      const dispatch = new Dispatch({
        id: dispatch_id,
        ambulance_id: assignment.ambulance_id,
        paramedic_ids: assignment.paramedic_ids,
        nurse_id: assignment.nurse_id,
        ml_history_id: assignment.history_id,
        ml_confidence: assignment.confidence,
        status: 'assigned',
        created_at: new Date()
      });

      await dispatch.save();

      // Cambiar ambulancia a ocupada
      await Ambulance.updateOne(
        { id: assignment.ambulance_id },
        { status: 'busy', dispatch_id: dispatch_id }
      );

      // Notificar paramédico principal
      await notifyParamedic(assignment.paramedic_ids[0], {
        type: 'assignment',
        dispatch_id,
        location: { lat: patient_latitude, lon: patient_longitude },
        emergency_type,
        severity_level
      });

      return res.json({
        success: true,
        dispatch_id,
        assignment
      });
    } else {
      return res.status(400).json({
        success: false,
        error: assignment.error
      });
    }
  } catch (error) {
    console.error('Error assigning ambulance:', error);
    res.status(500).json({ success: false, error: error.message });
  }
}

// Cuando termina el despacho
async function completeDispatch(req, res) {
  try {
    const { dispatch_id, response_time_minutes, patient_outcome } = req.body;

    // Obtener el dispatch
    const dispatch = await Dispatch.findById(dispatch_id);

    // Actualizar en MS-ML-DESPACHO (opcional - para mejorar datos de training)
    if (dispatch.ml_history_id) {
      await fetch(`http://localhost:5000/api/v1/dispatch/history/${dispatch.ml_history_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          actual_response_time_minutes: response_time_minutes,
          patient_outcome: patient_outcome,
          was_optimal: true // Tu lógica para determinar si fue óptima
        })
      });
    }

    // Cambiar ambulancia a disponible
    await Ambulance.updateOne(
      { id: dispatch.ambulance_id },
      { status: 'available', dispatch_id: null }
    );

    res.json({ success: true });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
}
```

---

## 7. CONSULTAS SQL ÚTILES

### Ver últimas asignaciones

```sql
SELECT TOP 10
    id,
    dispatch_id,
    emergency_type,
    severity_level,
    assigned_ambulance_id,
    assigned_paramedic_ids,
    created_at
FROM ml.assignment_history
ORDER BY created_at DESC;
```

### Tasa de optimalidad por día

```sql
SELECT
    CAST(created_at as DATE) as date,
    COUNT(*) as total,
    COUNT(CASE WHEN was_optimal = 1 THEN 1 END) as optimal,
    CAST(COUNT(CASE WHEN was_optimal = 1 THEN 1 END) as FLOAT) / COUNT(*) * 100 as optimal_rate
FROM ml.assignment_history
GROUP BY CAST(created_at as DATE)
ORDER BY date DESC;
```

### Ambulancia con mejor desempeño

```sql
SELECT TOP 5
    assigned_ambulance_id,
    COUNT(*) as total_assignments,
    AVG(actual_response_time_minutes) as avg_response_time,
    AVG(CAST(optimization_score as FLOAT)) as avg_optimization
FROM ml.assignment_history
WHERE was_optimal = 1
GROUP BY assigned_ambulance_id
ORDER BY avg_optimization DESC;
```

### Tiempo promedio respuesta por zona

```sql
SELECT
    zone_code,
    COUNT(*) as total,
    AVG(actual_response_time_minutes) as avg_response_time
FROM ml.assignment_history
WHERE actual_response_time_minutes IS NOT NULL
GROUP BY zone_code
ORDER BY avg_response_time DESC;
```

---

## 8. FLUJO COMPLETO EJEMPLO

```
1. Usuario solicita ambulancia por WhatsApp
   └─ n8n captura y envía a MS-Recepción

2. MS-Recepción obtiene GPS y tipo emergencia
   └─ Envía a MS-ML-DESPACHO

3. MS-ML-DESPACHO (Fase 1) AQUÍ ERES TÚ
   ├─ POST /api/v1/dispatch/assign
   ├─ Aplica Regla 1: ambulancia más cercana
   ├─ Aplica Regla 3: personal por severidad
   ├─ Guarda en ml.assignment_history
   └─ Retorna: {ambulance_id: 1, paramedic_ids: [101, 102], confidence: 0.92}

4. MS-DESPACHO recibe resultado
   ├─ Valida en su BD
   ├─ Asigna ambulancia 1
   ├─ Asigna paramédicos 101, 102
   └─ Notifica paramédico principal

5. Paramédico llega a lugar (2.8 min)
   ├─ Evalúa al paciente
   ├─ Toma vitales, fotos
   └─ Envía a Hospital X

6. MS-DESPACHO notifica resultado
   ├─ dispatch_id: 1001
   ├─ response_time: 2.8 min
   └─ outcome: "transferred_to_hospital"

7. MS-ML-DESPACHO actualiza registro
   ├─ actual_response_time_minutes: 2.8
   ├─ patient_outcome: "transferred_to_hospital"
   ├─ was_optimal: true (fue la mejor opción)
   └─ optimization_score: 0.92

8. Después de 2-3 meses
   ├─ 500+ registros en ml.assignment_history
   ├─ Entrenar modelo XGBoost (Fase 2)
   ├─ Cambiar de reglas a predicción ML
   └─ Esperar mejora de ~5-10% en optimalidad
```

---

## 9. DEBUGGING

Si algo no funciona, revisa en este orden:

1. **Health check**
   ```bash
   curl http://localhost:5000/api/v1/dispatch/health
   ```
   - Si falla: problema con el servicio

2. **Logs**
   ```bash
   tail -f logs/app.log
   ```
   - Ver errores específicos

3. **Base de datos**
   ```sql
   SELECT COUNT(*) FROM ml.assignment_history;
   ```
   - Verificar que se guardan datos

4. **Endpoint simple**
   ```bash
   curl 'http://localhost:5000/api/v1/dispatch/statistics?hours=1'
   ```
   - Si funciona, problema está en lógica de asignación

5. **Test con datos mínimos**
   ```bash
   # Revisar ejemplo 1 de este documento
   # Copiar exactamente y probar
   ```
