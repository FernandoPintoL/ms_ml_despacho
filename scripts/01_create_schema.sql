-- ============================================
-- MS ML DESPACHO - Database Schema
-- SQL Server 2019+
-- ============================================

-- ============================================
-- 1. SCHEMA PRINCIPAL
-- ============================================

IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'ml')
BEGIN
    EXEC sp_executesql N'CREATE SCHEMA ml'
END
GO

-- ============================================
-- 2. TABLA: HISTÓRICO DE ASIGNACIONES
-- ============================================
-- Propósito: Recolectar datos para entrenar modelos ML
-- Records: Se inserta un registro cada vez que se hace una asignación

CREATE TABLE ml.assignment_history (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,

    -- REFERENCIA A DESPACHO
    dispatch_id INT NOT NULL,
    request_timestamp DATETIME2 NOT NULL,

    -- ============================================
    -- FEATURES: INFORMACIÓN DEL EMERGENCIA
    -- ============================================
    emergency_latitude DECIMAL(10, 8) NOT NULL,
    emergency_longitude DECIMAL(10, 8) NOT NULL,
    emergency_type VARCHAR(100) NOT NULL,              -- 'trauma', 'paro_cardiaco', 'quemadura', 'intoxicacion', etc
    emergency_description NVARCHAR(500),

    -- SEVERIDAD (calculada por MS ML Decision)
    severity_level INT NOT NULL CHECK (severity_level BETWEEN 1 AND 5),  -- 1=bajo, 2=medio, 3=alto, 4=crítico, 5=extremo

    -- CONTEXTO TEMPORAL
    hour_of_day INT NOT NULL CHECK (hour_of_day BETWEEN 0 AND 23),
    day_of_week INT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),      -- 0=domingo, 6=sábado
    is_weekend BIT NOT NULL,

    -- UBICACIÓN Y ZONA
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(10, 8) NOT NULL,
    zone_code VARCHAR(50),                             -- Código de zona/sector de la ciudad

    -- ============================================
    -- FEATURES: AMBULANCIAS DISPONIBLES
    -- ============================================
    available_ambulances_count INT NOT NULL,
    nearest_ambulance_distance_km DECIMAL(8, 3),
    available_ambulances_json NVARCHAR(MAX),           -- JSON con: [{"id": 1, "distance_km": 2.5, "crew_experience": "senior", ...}]

    -- ============================================
    -- FEATURES: PERSONAL DISPONIBLE
    -- ============================================
    paramedics_available_count INT NOT NULL,
    paramedics_senior_count INT,
    paramedics_junior_count INT,
    nurses_available_count INT,
    specialists_available NVARCHAR(500),               -- JSON: ["cardiologo", "traumatologo", ...]

    -- ============================================
    -- FEATURES: CARGA DEL SISTEMA
    -- ============================================
    active_dispatches_count INT NOT NULL,              -- Cuántos despachos activos hay en ese momento
    ambulances_busy_percentage DECIMAL(5, 2),         -- % de ambulancias ocupadas
    average_response_time_minutes DECIMAL(8, 2),      -- Promedio histórico de respuesta en la zona

    -- ============================================
    -- TARGET: ASIGNACIÓN REALIZADA (LO QUE QUEREMOS PREDECIR)
    -- ============================================
    assigned_ambulance_id INT NOT NULL,
    assigned_paramedic_ids NVARCHAR(MAX),              -- JSON: [1, 5, 8] - IDs de paramédicos
    assigned_paramedic_levels NVARCHAR(200),           -- JSON: ["senior", "junior", "nurse"]

    -- ============================================
    -- FEATURES POST-ASIGNACIÓN: MÉTRICAS DE ÉXITO
    -- ============================================
    actual_response_time_minutes DECIMAL(8, 2),        -- Tiempo real de respuesta
    actual_travel_distance_km DECIMAL(8, 3),           -- Distancia real recorrida
    patient_outcome VARCHAR(100),                      -- 'treated_on_site', 'transferred_to_hospital', 'referido', 'cancelado'
    hospital_destination_id INT,                       -- Hospital al que se trasladó (si aplica)

    -- CALIDAD DE LA ASIGNACIÓN
    was_optimal BIT,                                   -- ¿Fue la opción óptima? (calculado post-despacho)
    optimization_score DECIMAL(5, 4),                  -- Score 0-1 de cuán óptima fue la asignación

    -- FEEDBACK
    paramedic_satisfaction_rating INT CHECK (paramedic_satisfaction_rating BETWEEN 1 AND 5),
    patient_satisfaction_rating INT CHECK (patient_satisfaction_rating BETWEEN 1 AND 5),

    -- ============================================
    -- METADATOS
    -- ============================================
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE(),
    created_by VARCHAR(100),

    INDEX idx_dispatch_id ON ml.assignment_history(dispatch_id),
    INDEX idx_created_at ON ml.assignment_history(created_at),
    INDEX idx_severity ON ml.assignment_history(severity_level),
    INDEX idx_ambulance ON ml.assignment_history(assigned_ambulance_id),
    INDEX idx_optimal ON ml.assignment_history(was_optimal)
)
GO

-- ============================================
-- 3. TABLA: MODELOS ML ENTRENADOS
-- ============================================
-- Propósito: Mantener registro de todos los modelos y sus versiones

CREATE TABLE ml.trained_models (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,

    model_name VARCHAR(100) NOT NULL,                  -- 'ambulance_selector_v1', 'paramedic_assignment_v1'
    model_type VARCHAR(50) NOT NULL,                   -- 'xgboost', 'random_forest', 'decision_tree', 'rules'
    model_version VARCHAR(50) NOT NULL,                -- '1.0.0', '1.1.0'

    -- CARACTERÍSTICAS DEL MODELO
    algorithm_type VARCHAR(50),                        -- 'supervised', 'unsupervised', 'deterministic'
    input_features NVARCHAR(MAX),                      -- JSON: ["distance", "severity_level", "hour_of_day", ...]
    target_variable VARCHAR(100),                      -- 'ambulance_id' o 'paramedic_ids'

    -- MÉTRICAS DE DESEMPEÑO
    accuracy DECIMAL(5, 4),
    precision DECIMAL(5, 4),
    recall DECIMAL(5, 4),
    f1_score DECIMAL(5, 4),

    -- DATOS DE ENTRENAMIENTO
    training_samples_count INT,
    training_date DATETIME2,
    training_duration_seconds INT,

    -- VALIDACIÓN
    validation_accuracy DECIMAL(5, 4),
    test_accuracy DECIMAL(5, 4),

    -- INFORMACIÓN DEL MODELO
    hyperparameters NVARCHAR(MAX),                     -- JSON con params del modelo
    feature_importance NVARCHAR(MAX),                  -- JSON: {"distance": 0.35, "severity": 0.28, ...}
    model_file_path VARCHAR(500),                      -- Ruta al archivo .pkl o .joblib
    model_file_size_kb INT,

    -- ESTADO
    is_active BIT DEFAULT 0,
    is_production BIT DEFAULT 0,
    last_used_at DATETIME2,

    -- AUDITORÍA
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    created_by VARCHAR(100),
    updated_at DATETIME2 DEFAULT GETUTCDATE(),

    CONSTRAINT uk_model_version UNIQUE (model_name, model_version),
    INDEX idx_active ON ml.trained_models(is_active),
    INDEX idx_production ON ml.trained_models(is_production)
)
GO

-- ============================================
-- 4. TABLA: PREDICCIONES REALIZADAS
-- ============================================
-- Propósito: Auditoría y evaluación de predicciones vs realidad

CREATE TABLE ml.predictions_log (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,

    -- REFERENCIA
    dispatch_id INT NOT NULL,
    model_id INT NOT NULL,
    request_timestamp DATETIME2 NOT NULL,

    -- INPUT: FEATURES USADAS PARA PREDICCIÓN
    input_features NVARCHAR(MAX) NOT NULL,             -- JSON con todos los features usados

    -- OUTPUT: PREDICCIÓN DEL MODELO
    predicted_ambulance_id INT,
    predicted_paramedic_ids NVARCHAR(MAX),             -- JSON: [1, 5, 8]
    prediction_confidence DECIMAL(5, 4),               -- 0-1, confianza del modelo
    prediction_timestamp DATETIME2,

    -- REAL: LO QUE PASÓ EN LA REALIDAD
    actual_ambulance_id INT,
    actual_paramedic_ids NVARCHAR(MAX),
    actual_response_time_minutes DECIMAL(8, 2),

    -- EVALUACIÓN: ¿QUÉ TAN CORRECTA FUE?
    prediction_correct BIT,                            -- ¿Se asignó la ambulancia predicha?
    prediction_accuracy_score DECIMAL(5, 4),           -- 0-1, accuracy específica de esta predicción

    -- FEEDBACK POST-DESPACHO
    feedback_score DECIMAL(5, 2),                      -- Score general de la predicción
    feedback_comments NVARCHAR(500),

    -- ESTADO
    execution_status VARCHAR(50),                      -- 'pending', 'executed', 'failed', 'cancelled'
    error_message NVARCHAR(500),

    -- METADATOS
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE(),

    CONSTRAINT fk_predictions_model FOREIGN KEY (model_id) REFERENCES ml.trained_models(id),
    INDEX idx_dispatch ON ml.predictions_log(dispatch_id),
    INDEX idx_model ON ml.predictions_log(model_id),
    INDEX idx_created ON ml.predictions_log(created_at),
    INDEX idx_correct ON ml.predictions_log(prediction_correct)
)
GO

-- ============================================
-- 5. TABLA: FEATURES ENGINEERING
-- ============================================
-- Propósito: Cache de features calculadas para optimizar predicciones

CREATE TABLE ml.features_cache (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,

    dispatch_id INT NOT NULL,

    -- FEATURES CALCULADAS (JSON COMPLETO)
    features_json NVARCHAR(MAX) NOT NULL,

    -- METADATA
    calculated_at DATETIME2 DEFAULT GETUTCDATE(),
    expires_at DATETIME2,                              -- TTL para limpiar cache

    INDEX idx_dispatch ON ml.features_cache(dispatch_id),
    INDEX idx_expires ON ml.features_cache(expires_at)
)
GO

-- ============================================
-- 6. TABLA: MODELO CONFIGURATION
-- ============================================
-- Propósito: Configuración de parámetros para Phase 1 (reglas determinísticas)

CREATE TABLE ml.model_configuration (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,

    config_name VARCHAR(100) NOT NULL UNIQUE,         -- 'phase1_rules', 'phase2_xgboost'
    config_type VARCHAR(50),                           -- 'phase', 'algorithm', 'feature'

    -- CONFIGURACIÓN
    configuration_json NVARCHAR(MAX) NOT NULL,         -- JSON con toda la configuración

    -- ESTADO
    is_active BIT DEFAULT 1,
    version VARCHAR(50),

    -- AUDITORÍA
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE(),
    created_by VARCHAR(100)
)
GO

-- ============================================
-- 7. TABLA: MÉTRICAS Y ESTADÍSTICAS
-- ============================================
-- Propósito: KPIs y métricas agregadas por período

CREATE TABLE ml.metrics_summary (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,

    metric_date DATE NOT NULL,
    metric_hour INT,                                   -- NULL = día completo, 0-23 = hora específica

    -- VOLUMEN
    total_dispatches INT,
    dispatches_completed INT,
    dispatches_optimal INT,

    -- DESEMPEÑO
    average_response_time DECIMAL(8, 2),
    average_travel_distance DECIMAL(8, 3),
    optimization_score DECIMAL(5, 4),

    -- MODELOS
    model_accuracy DECIMAL(5, 4),
    model_f1_score DECIMAL(5, 4),
    prediction_confidence_avg DECIMAL(5, 4),

    -- AMBULANCIAS
    ambulances_utilization_rate DECIMAL(5, 2),
    ambulances_busy_percentage DECIMAL(5, 2),

    -- PERSONAL
    paramedics_utilization_rate DECIMAL(5, 2),
    average_team_size DECIMAL(4, 2),

    -- CALIDAD
    patient_satisfaction_avg INT,
    paramedic_satisfaction_avg INT,

    created_at DATETIME2 DEFAULT GETUTCDATE(),

    CONSTRAINT uk_metrics UNIQUE (metric_date, metric_hour),
    INDEX idx_date ON ml.metrics_summary(metric_date)
)
GO

-- ============================================
-- 8. TABLA: AUDITORÍA Y LOGS
-- ============================================

CREATE TABLE ml.audit_log (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,

    event_type VARCHAR(100) NOT NULL,                  -- 'model_trained', 'prediction_made', 'assignment_recorded'
    entity_type VARCHAR(50),                           -- 'model', 'prediction', 'assignment'
    entity_id INT,

    action VARCHAR(100),                               -- 'CREATE', 'UPDATE', 'DELETE'
    old_values NVARCHAR(MAX),
    new_values NVARCHAR(MAX),

    user_id INT,
    ip_address VARCHAR(50),

    status VARCHAR(50),                                -- 'SUCCESS', 'FAILED'
    error_message NVARCHAR(500),

    created_at DATETIME2 DEFAULT GETUTCDATE(),

    INDEX idx_event_type ON ml.audit_log(event_type),
    INDEX idx_created ON ml.audit_log(created_at)
)
GO

-- ============================================
-- 9. VISTAS ÚTILES
-- ============================================

-- Vista: Histórico con información resumida
CREATE VIEW ml.v_assignment_history_summary AS
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

-- Vista: Modelos activos
CREATE VIEW ml.v_active_models AS
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

-- Vista: Predicciones con evaluación
CREATE VIEW ml.v_predictions_evaluation AS
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

-- ============================================
-- 10. STORED PROCEDURES ÚTILES
-- ============================================

-- SP: Insertar histórico de asignación
CREATE PROCEDURE ml.sp_insert_assignment_history
    @dispatch_id INT,
    @emergency_latitude DECIMAL(10, 8),
    @emergency_longitude DECIMAL(10, 8),
    @emergency_type VARCHAR(100),
    @severity_level INT,
    @zone_code VARCHAR(50),
    @available_ambulances_count INT,
    @nearest_ambulance_distance_km DECIMAL(8, 3),
    @available_ambulances_json NVARCHAR(MAX),
    @paramedics_available_count INT,
    @assigned_ambulance_id INT,
    @assigned_paramedic_ids NVARCHAR(MAX),
    @created_by VARCHAR(100) = 'SYSTEM'
AS
BEGIN
    SET NOCOUNT ON

    INSERT INTO ml.assignment_history (
        dispatch_id,
        request_timestamp,
        emergency_latitude,
        emergency_longitude,
        emergency_type,
        severity_level,
        hour_of_day,
        day_of_week,
        is_weekend,
        latitude,
        longitude,
        zone_code,
        available_ambulances_count,
        nearest_ambulance_distance_km,
        available_ambulances_json,
        paramedics_available_count,
        active_dispatches_count,
        assigned_ambulance_id,
        assigned_paramedic_ids,
        created_by
    )
    VALUES (
        @dispatch_id,
        GETUTCDATE(),
        @emergency_latitude,
        @emergency_longitude,
        @emergency_type,
        @severity_level,
        DATEPART(HOUR, GETUTCDATE()),
        DATEPART(WEEKDAY, GETUTCDATE()) - 1,
        CASE WHEN DATEPART(WEEKDAY, GETUTCDATE()) IN (1, 7) THEN 1 ELSE 0 END,
        @emergency_latitude,
        @emergency_longitude,
        @zone_code,
        @available_ambulances_count,
        @nearest_ambulance_distance_km,
        @available_ambulances_json,
        @paramedics_available_count,
        0,
        @assigned_ambulance_id,
        @assigned_paramedic_ids,
        @created_by
    )

    SELECT SCOPE_IDENTITY() AS id
END
GO

-- SP: Obtener Features para Predicción
CREATE PROCEDURE ml.sp_get_features_for_prediction
    @dispatch_id INT
AS
BEGIN
    SET NOCOUNT ON

    SELECT TOP 1
        dispatch_id,
        emergency_latitude,
        emergency_longitude,
        emergency_type,
        severity_level,
        hour_of_day,
        day_of_week,
        zone_code,
        available_ambulances_count,
        nearest_ambulance_distance_km,
        paramedics_available_count,
        active_dispatches_count
    FROM ml.assignment_history
    WHERE dispatch_id = @dispatch_id
    ORDER BY created_at DESC
END
GO

-- ============================================
-- 11. SEED DATA - Configuración Fase 1
-- ============================================

INSERT INTO ml.model_configuration (config_name, config_type, configuration_json, version, created_by)
VALUES (
    'phase1_deterministic_rules',
    'phase',
    N'{
        "phase": 1,
        "enabled": true,
        "algorithm": "deterministic_rules",
        "rules": [
            {
                "name": "assign_nearest_ambulance",
                "priority": 1,
                "description": "Asigna la ambulancia más cercana disponible"
            },
            {
                "name": "validate_availability",
                "priority": 2,
                "description": "Valida que la ambulancia esté disponible"
            },
            {
                "name": "assign_paramedics_by_severity",
                "priority": 3,
                "description": "Asigna personal según severidad"
            }
        ],
        "paramedic_assignment": {
            "critical": {"min_paramedics": 3, "levels": ["senior", "senior", "junior"], "nurse": true},
            "high": {"min_paramedics": 2, "levels": ["senior", "junior"], "nurse": false},
            "medium": {"min_paramedics": 2, "levels": ["junior", "junior"], "nurse": false},
            "low": {"min_paramedics": 1, "levels": ["junior"], "nurse": false}
        }
    }',
    '1.0.0',
    'SYSTEM'
)
GO

PRINT 'Schema creation completed successfully!'
