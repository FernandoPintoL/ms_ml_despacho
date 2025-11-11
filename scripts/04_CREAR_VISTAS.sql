-- ============================================
-- CREAR VISTAS - EJECUTAR EN SSMS
-- ============================================

-- Vista 1: assignment_history_summary
GO
IF OBJECT_ID('ml.v_assignment_history_summary', 'V') IS NOT NULL
    DROP VIEW ml.v_assignment_history_summary
GO

CREATE VIEW ml.v_assignment_history_summary
AS
SELECT
    ah.id,
    ah.dispatch_id,
    ah.request_timestamp,
    ah.emergency_type,
    ah.severity_level,
    ah.zone_code,
    ah.assigned_ambulance_id,
    ah.actual_response_time_minutes,
    ah.was_optimal,
    ah.optimization_score,
    ah.patient_satisfaction_rating,
    ah.created_at
FROM ml.assignment_history ah
GO

PRINT '>>> Vista v_assignment_history_summary creada'
GO

-- Vista 2: active_models
GO
IF OBJECT_ID('ml.v_active_models', 'V') IS NOT NULL
    DROP VIEW ml.v_active_models
GO

CREATE VIEW ml.v_active_models
AS
SELECT
    id,
    model_name,
    model_version,
    model_type,
    accuracy,
    f1_score,
    is_active,
    is_production,
    last_used_at
FROM ml.trained_models
WHERE is_active = 1
GO

PRINT '>>> Vista v_active_models creada'
GO

-- Vista 3: predictions_evaluation
GO
IF OBJECT_ID('ml.v_predictions_evaluation', 'V') IS NOT NULL
    DROP VIEW ml.v_predictions_evaluation
GO

CREATE VIEW ml.v_predictions_evaluation
AS
SELECT
    p.id,
    p.dispatch_id,
    m.model_name,
    p.prediction_confidence,
    p.prediction_correct,
    p.prediction_accuracy_score,
    p.actual_response_time_minutes,
    p.feedback_score,
    p.created_at
FROM ml.predictions_log p
JOIN ml.trained_models m ON p.model_id = m.id
GO

PRINT '>>> Vista v_predictions_evaluation creada'
GO

PRINT ''
PRINT '========================================='
PRINT 'VISTAS CREADAS EXITOSAMENTE'
PRINT '========================================='
GO

SELECT * FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_SCHEMA = 'ml'
GO
