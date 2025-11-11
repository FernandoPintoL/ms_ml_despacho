# A/B TESTING FRAMEWORK - GUÍA DE USO

## Fase 3, Paso 2: A/B Testing Framework

**Objetivo:** Sistema para dividir tráfico entre Fase 1 (reglas determinísticas) y Fase 2 (ML) para comparar performance.

---

## COMPONENTES

### 1. ABTest Class (`src/integration/ab_testing.py`)

Sistema principal de A/B testing con 4 estrategias de división:

#### Estrategia 1: RANDOM_50_50
```
Divide aleatoriamente 50% Fase 1, 50% Fase 2
Uso: Comparación general
```

#### Estrategia 2: ROUND_ROBIN
```
Alterna sistemáticamente entre fases
Uso: Distribución consistente
```

#### Estrategia 3: TIME_BASED
```
Diferentes splits según hora del día:
- Peak hours (9-17): 70% Fase 2, 30% Fase 1
- Off-peak: 30% Fase 2, 70% Fase 1
Uso: Testing en diferentes condiciones
```

#### Estrategia 4: WEIGHT_BASED
```
Split customizable con peso específico
Uso: Rollout gradual
```

### 2. Dashboard API (`src/api/ab_testing_dashboard.py`)

7 nuevos endpoints REST para visualizar y controlar A/B test:

```
GET    /api/v3/ab-testing/status                  - Estado actual
GET    /api/v3/ab-testing/dashboard               - Dashboard completo
GET    /api/v3/ab-testing/comparison              - Fase 1 vs Fase 2
POST   /api/v3/ab-testing/decide-phase            - Decidir qué fase usar
POST   /api/v3/ab-testing/log                     - Registrar resultado
GET    /api/v3/ab-testing/recommendation          - Recomendación
GET    /api/v3/ab-testing/metrics                 - Métricas detalladas
GET    /api/v3/ab-testing/strategies              - Estrategias disponibles
```

---

## FLUJO DE USO

### Paso 1: Inicializar A/B Test

```python
from src.integration.ab_testing import ABTest, ABTestingStrategy

ab_test = ABTest(
    server='192.168.1.38',
    database='ms_ml_despacho',
    username='sa',
    password='1234',
    strategy=ABTestingStrategy.RANDOM_50_50,  # 50/50 split
    phase2_weight=0.5
)

ab_test.connect()
```

### Paso 2: Decidir qué fase usar para cada solicitud

```python
# Para cada nuevo dispatch:
phase = ab_test.decide_phase(dispatch_id=123)

if phase == 1:
    result = ml_client.predict(features)  # Usa fallback a Fase 1
else:
    result = ml_client.predict(features)  # Usa Fase 2 ML
```

### Paso 3: Registrar resultado

```python
ab_test.log_ab_test(
    dispatch_id=123,
    phase_used=2,
    phase1_result=None,  # Si se evaluó Fase 1
    phase2_result=result  # Resultado de Fase 2
)
```

### Paso 4: Analizar resultados

```python
# Obtener estadísticas
results = ab_test.get_ab_test_results(hours=24)
print(f"Fase 1: {results['phase1_percentage']:.1f}%")
print(f"Fase 2: {results['phase2_percentage']:.1f}%")

# Comparar performance
comparison = ab_test.compare_phases(hours=24)
print(f"Mejora Fase 2: {comparison['comparison']['confidence_improvement_percent']:.2f}%")
```

---

## ENDPOINTS REST

### 1. Status - Estado Actual del Test

```bash
GET /api/v3/ab-testing/status

Response:
{
    "success": true,
    "strategy": "random_50_50",
    "total_tests_24h": 1250,
    "phase1_percentage": 49.8,
    "phase2_percentage": 50.2,
    "phase1_avg_confidence": 0.8234,
    "phase2_avg_confidence": 0.9156
}
```

### 2. Dashboard - Reporte Completo

```bash
GET /api/v3/ab-testing/dashboard?hours=24

Response:
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

### 3. Comparison - Comparativa Detallada

```bash
GET /api/v3/ab-testing/comparison?hours=24

Response:
{
    "success": true,
    "comparison": {
        "period_hours": 24,
        "phase1": {
            "total": 623,
            "avg_confidence": 0.8234,
            "min_confidence": 0.5012,
            "max_confidence": 0.9987
        },
        "phase2": {
            "total": 627,
            "avg_confidence": 0.9156,
            "min_confidence": 0.5678,
            "max_confidence": 0.9999
        },
        "comparison": {
            "confidence_difference": 0.0922,
            "confidence_improvement_percent": 11.21,
            "phase2_better": true,
            "recommendation": "Phase 2 performing better"
        }
    }
}
```

### 4. Decide Phase - Decidir Fase para Dispatch

```bash
POST /api/v3/ab-testing/decide-phase
Content-Type: application/json

{
    "dispatch_id": 123
}

Response:
{
    "success": true,
    "phase": 2,
    "strategy": "random_50_50",
    "dispatch_id": 123
}
```

### 5. Log Test - Registrar Resultado

```bash
POST /api/v3/ab-testing/log
Content-Type: application/json

{
    "dispatch_id": 123,
    "phase_used": 2,
    "phase1_result": null,
    "phase2_result": {
        "prediction": 1,
        "confidence": 0.95,
        "recommendation": "ASSIGN"
    }
}

Response:
{
    "success": true,
    "message": "A/B test logged successfully"
}
```

### 6. Recommendation - Recomendación

```bash
GET /api/v3/ab-testing/recommendation?hours=24

Response:
{
    "success": true,
    "recommendation": "Phase 2 showing significant improvement. Consider gradual rollout.",
    "period_hours": 24,
    "data_available": true
}
```

### 7. Metrics - Métricas Detalladas

```bash
GET /api/v3/ab-testing/metrics?hours=24

Response:
{
    "success": true,
    "period_hours": 24,
    "distribution": {
        "phase1": {
            "count": 623,
            "percentage": 49.84
        },
        "phase2": {
            "count": 627,
            "percentage": 50.16
        }
    },
    "phase1_metrics": {
        "total": 623,
        "avg_confidence": 0.8234,
        "min_confidence": 0.5012,
        "max_confidence": 0.9987
    },
    "phase2_metrics": {
        "total": 627,
        "avg_confidence": 0.9156,
        "min_confidence": 0.5678,
        "max_confidence": 0.9999
    },
    "improvement": {
        "confidence_difference": 0.0922,
        "confidence_improvement_percent": 11.21,
        "phase2_better": true
    }
}
```

---

## EJEMPLO DE INTEGRACIÓN EN ms-despacho

```python
from src.integration.ab_testing import ABTest, ABTestingStrategy
from src.integration.ml_client import MLClient

class DispatchServiceWithABTesting:
    def __init__(self):
        self.ab_test = ABTest(
            server='192.168.1.38',
            database='ms_ml_despacho',
            username='sa',
            password='1234',
            strategy=ABTestingStrategy.RANDOM_50_50,
            phase2_weight=0.5
        )
        self.ml_client = MLClient()
        self.ab_test.connect()

    def assign_ambulance(self, dispatch_request):
        """Asignar ambulancia con A/B testing"""

        # 1. Decidir qué fase usar
        phase = self.ab_test.decide_phase(dispatch_request.dispatch_id)

        # 2. Hacer predicción
        features = self._prepare_features(dispatch_request)
        result = self.ml_client.predict(features)

        # 3. Registrar resultado
        self.ab_test.log_ab_test(
            dispatch_id=dispatch_request.dispatch_id,
            phase_used=phase if result['success'] else 1,
            phase2_result=result if phase == 2 else None
        )

        # 4. Proceder con asignación
        if result['success']:
            return self._proceed_with_assignment(dispatch_request, result)
        else:
            return self._manual_assignment(dispatch_request)
```

---

## INTERPRETACIÓN DE RESULTADOS

### Métrica: Confidence Improvement

```
> 10%      → Mejora significativa, rollout gradual
5-10%      → Mejora moderada, continuar testing
0-5%       → Mejora ligera, recopilar más datos
-5 a 0%    → Resultados similares, ambas viables
< -5%      → Fase 1 más confiable, Phase 2 necesita optimización
```

### Métrica: Distribución

```
Ideal (después de varios días):
- Phase 1: ~40-50%
- Phase 2: ~50-60%

Señales de problemas:
- Fallback rate > 10%  → Problemas en servicio ML
- Phase 2 % muy bajo   → Muchos errores, fallbacks frecuentes
```

---

## MONITOREO RECOMENDADO

### Diariamente
- ✓ Ver dashboard: `/api/v3/ab-testing/dashboard`
- ✓ Revisar recomendación: `/api/v3/ab-testing/recommendation`
- ✓ Monitorear métricas: `/api/v3/ab-testing/metrics`

### Semanalmente
- ✓ Comparar performance: `/api/v3/ab-testing/comparison`
- ✓ Analizar tendencias históricas
- ✓ Ajustar strategy si es necesario

### Criterios de Decisión

**Pasar a 100% Fase 2 cuando:**
- Confianza Fase 2 > 0.92
- Mejora > 10%
- 7+ días de testing con resultados consistentes
- Fallback rate < 5%

**Volver a Fase 1 si:**
- Confianza cae < 0.75
- Mejora se vuelve negativa
- Errores aumentan significativamente
- Servicio ML inestable

---

## SQL QUERIES ÚTILES

```sql
-- Ver últimas predicciones
SELECT TOP 20 * FROM ml.ab_test_log
ORDER BY created_at DESC

-- Distribución por hora del día
SELECT
    DATEPART(HOUR, created_at) as hour,
    phase_used,
    COUNT(*) as count
FROM ml.ab_test_log
WHERE created_at > DATEADD(day, -7, GETDATE())
GROUP BY DATEPART(HOUR, created_at), phase_used
ORDER BY hour, phase_used

-- Tasa de uso por fase (últimos 7 días)
SELECT
    phase_used,
    COUNT(*) as count,
    COUNT(*) * 100.0 / (SELECT COUNT(*) FROM ml.ab_test_log
        WHERE created_at > DATEADD(day, -7, GETDATE())) as percentage
FROM ml.ab_test_log
WHERE created_at > DATEADD(day, -7, GETDATE())
GROUP BY phase_used
```

---

## TROUBLESHOOTING

### Problema: No hay datos en dashboard
```
Solución:
1. Verificar que predictions_log está siendo poblada
2. Ejecutar: SELECT COUNT(*) FROM ml.ab_test_log
3. Si 0 registros, iniciar logging desde ms-despacho
```

### Problema: Distribución desigual
```
Solución:
1. Si muy pocos Phase 2: aumentar phase2_weight
2. Si muy pocos Phase 1: revisar fallbacks
3. Cambiar strategy a TIME_BASED para mejor control
```

### Problema: Recomendación indefinida
```
Solución:
1. Necesita mínimo 100+ registros por fase
2. Ejecutar al menos 24 horas de testing
3. Verificar que datos son confiables
```

---

**Status:** Fase 3, Paso 2 - A/B Testing Framework COMPLETO
**Archivos:**
- `src/integration/ab_testing.py` (500 líneas)
- `src/api/ab_testing_dashboard.py` (350 líneas)
