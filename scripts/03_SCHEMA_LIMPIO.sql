-- ============================================
-- MS ML DESPACHO - SCHEMA LIMPIO Y SIMPLE
-- COPIAR TODO EN SSMS Y EJECUTAR F5
-- ============================================

-- Primero, DROP de todas las tablas si existen (OPCIONAL - descomentar si necesitas limpiar)
-- DROP TABLE IF EXISTS ml.audit_log
-- DROP TABLE IF EXISTS ml.metrics_summary
-- DROP TABLE IF EXISTS ml.features_cache
-- DROP TABLE IF EXISTS ml.predictions_log
-- DROP TABLE IF EXISTS ml.trained_models
-- DROP TABLE IF EXISTS ml.assignment_history
-- DROP TABLE IF EXISTS ml.model_configuration
-- DROP SCHEMA IF EXISTS ml
-- GO

-- ============================================
-- 1. CREAR SCHEMA
-- ============================================

IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'ml')
BEGIN
    EXEC sp_executesql N'CREATE SCHEMA ml'
END
GO

PRINT '>>> Schema ml creado'
GO

-- ============================================
-- 2. TABLA PRINCIPAL: assignment_history
-- ============================================

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'assignment_history' AND TABLE_SCHEMA = 'ml')
BEGIN

CREATE TABLE ml.assignment_history (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,

    -- Referencia
    dispatch_id INT NOT NULL,
    request_timestamp DATETIME2 NOT NULL,

    -- Ubicacion emergencia
    emergency_latitude DECIMAL(10, 8) NOT NULL,
    emergency_longitude DECIMAL(10, 8) NOT NULL,
    emergency_type VARCHAR(100) NOT NULL,
    emergency_description NVARCHAR(500),
    severity_level INT NOT NULL CHECK (severity_level BETWEEN 1 AND 5),

    -- Contexto temporal
    hour_of_day INT NOT NULL CHECK (hour_of_day BETWEEN 0 AND 23),
    day_of_week INT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    is_weekend BIT NOT NULL,

    -- Ubicacion
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(10, 8) NOT NULL,
    zone_code VARCHAR(50),

    -- Disponibilidad ambulancias
    available_ambulances_count INT NOT NULL,
    nearest_ambulance_distance_km DECIMAL(8, 3),
    available_ambulances_json NVARCHAR(MAX),

    -- Disponibilidad personal
    paramedics_available_count INT NOT NULL,
    paramedics_senior_count INT,
    paramedics_junior_count INT,
    nurses_available_count INT,
    specialists_available NVARCHAR(500),

    -- Carga sistema
    active_dispatches_count INT NOT NULL,
    ambulances_busy_percentage DECIMAL(5, 2),
    average_response_time_minutes DECIMAL(8, 2),

    -- Asignacion realizada
    assigned_ambulance_id INT NOT NULL,
    assigned_paramedic_ids NVARCHAR(MAX),
    assigned_paramedic_levels NVARCHAR(200),

    -- Post-asignacion
    actual_response_time_minutes DECIMAL(8, 2),
    actual_travel_distance_km DECIMAL(8, 3),
    patient_outcome VARCHAR(100),
    hospital_destination_id INT,
    was_optimal BIT,
    optimization_score DECIMAL(5, 4),

    -- Feedback
    paramedic_satisfaction_rating INT CHECK (paramedic_satisfaction_rating BETWEEN 1 AND 5),
    patient_satisfaction_rating INT CHECK (patient_satisfaction_rating BETWEEN 1 AND 5),

    -- Metadata
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE(),
    created_by VARCHAR(100)
)

CREATE INDEX idx_dispatch_id ON ml.assignment_history(dispatch_id)
CREATE INDEX idx_created_at ON ml.assignment_history(created_at)
CREATE INDEX idx_severity ON ml.assignment_history(severity_level)
CREATE INDEX idx_ambulance ON ml.assignment_history(assigned_ambulance_id)
CREATE INDEX idx_optimal ON ml.assignment_history(was_optimal)

PRINT '>>> Tabla assignment_history creada'

END
GO

-- ============================================
-- 3. TABLA: trained_models
-- ============================================

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'trained_models' AND TABLE_SCHEMA = 'ml')
BEGIN

CREATE TABLE ml.trained_models (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    algorithm_type VARCHAR(50),
    input_features NVARCHAR(MAX),
    target_variable VARCHAR(100),

    -- Metricas
    accuracy DECIMAL(5, 4),
    precision DECIMAL(5, 4),
    recall DECIMAL(5, 4),
    f1_score DECIMAL(5, 4),

    -- Entrenamiento
    training_samples_count INT,
    training_date DATETIME2,
    training_duration_seconds INT,
    validation_accuracy DECIMAL(5, 4),
    test_accuracy DECIMAL(5, 4),

    -- Modelo
    hyperparameters NVARCHAR(MAX),
    feature_importance NVARCHAR(MAX),
    model_file_path VARCHAR(500),
    model_file_size_kb INT,

    -- Estado
    is_active BIT DEFAULT 0,
    is_production BIT DEFAULT 0,
    last_used_at DATETIME2,

    -- Auditoria
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    created_by VARCHAR(100),
    updated_at DATETIME2 DEFAULT GETUTCDATE(),

    CONSTRAINT uk_model_version UNIQUE (model_name, model_version)
)

CREATE INDEX idx_active ON ml.trained_models(is_active)
CREATE INDEX idx_production ON ml.trained_models(is_production)

PRINT '>>> Tabla trained_models creada'

END
GO

-- ============================================
-- 4. TABLA: predictions_log
-- ============================================

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'predictions_log' AND TABLE_SCHEMA = 'ml')
BEGIN

CREATE TABLE ml.predictions_log (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
    dispatch_id INT NOT NULL,
    model_id INT NOT NULL,
    request_timestamp DATETIME2 NOT NULL,

    -- Prediccion
    input_features NVARCHAR(MAX) NOT NULL,
    predicted_ambulance_id INT,
    predicted_paramedic_ids NVARCHAR(MAX),
    prediction_confidence DECIMAL(5, 4),
    prediction_timestamp DATETIME2,

    -- Real
    actual_ambulance_id INT,
    actual_paramedic_ids NVARCHAR(MAX),
    actual_response_time_minutes DECIMAL(8, 2),

    -- Evaluacion
    prediction_correct BIT,
    prediction_accuracy_score DECIMAL(5, 4),
    feedback_score DECIMAL(5, 2),
    feedback_comments NVARCHAR(500),

    -- Estado
    execution_status VARCHAR(50),
    error_message NVARCHAR(500),

    -- Auditoria
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE(),

    CONSTRAINT fk_predictions_model FOREIGN KEY (model_id) REFERENCES ml.trained_models(id)
)

CREATE INDEX idx_dispatch ON ml.predictions_log(dispatch_id)
CREATE INDEX idx_model ON ml.predictions_log(model_id)
CREATE INDEX idx_created ON ml.predictions_log(created_at)
CREATE INDEX idx_correct ON ml.predictions_log(prediction_correct)

PRINT '>>> Tabla predictions_log creada'

END
GO

-- ============================================
-- 5. TABLA: features_cache
-- ============================================

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'features_cache' AND TABLE_SCHEMA = 'ml')
BEGIN

CREATE TABLE ml.features_cache (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
    dispatch_id INT NOT NULL,
    features_json NVARCHAR(MAX) NOT NULL,
    calculated_at DATETIME2 DEFAULT GETUTCDATE(),
    expires_at DATETIME2
)

CREATE INDEX idx_dispatch ON ml.features_cache(dispatch_id)
CREATE INDEX idx_expires ON ml.features_cache(expires_at)

PRINT '>>> Tabla features_cache creada'

END
GO

-- ============================================
-- 6. TABLA: model_configuration
-- ============================================

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'model_configuration' AND TABLE_SCHEMA = 'ml')
BEGIN

CREATE TABLE ml.model_configuration (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
    config_name VARCHAR(100) NOT NULL UNIQUE,
    config_type VARCHAR(50),
    configuration_json NVARCHAR(MAX) NOT NULL,
    is_active BIT DEFAULT 1,
    version VARCHAR(50),
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE(),
    created_by VARCHAR(100)
)

PRINT '>>> Tabla model_configuration creada'

END
GO

-- ============================================
-- 7. TABLA: metrics_summary
-- ============================================

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'metrics_summary' AND TABLE_SCHEMA = 'ml')
BEGIN

CREATE TABLE ml.metrics_summary (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
    metric_date DATE NOT NULL,
    metric_hour INT,

    -- Volumen
    total_dispatches INT,
    dispatches_completed INT,
    dispatches_optimal INT,

    -- Desempeño
    average_response_time DECIMAL(8, 2),
    average_travel_distance DECIMAL(8, 3),
    optimization_score DECIMAL(5, 4),

    -- Modelos
    model_accuracy DECIMAL(5, 4),
    model_f1_score DECIMAL(5, 4),
    prediction_confidence_avg DECIMAL(5, 4),

    -- Ambulancias
    ambulances_utilization_rate DECIMAL(5, 2),
    ambulances_busy_percentage DECIMAL(5, 2),

    -- Personal
    paramedics_utilization_rate DECIMAL(5, 2),
    average_team_size DECIMAL(4, 2),

    -- Calidad
    patient_satisfaction_avg INT,
    paramedic_satisfaction_avg INT,

    created_at DATETIME2 DEFAULT GETUTCDATE(),

    CONSTRAINT uk_metrics UNIQUE (metric_date, metric_hour)
)

CREATE INDEX idx_date ON ml.metrics_summary(metric_date)

PRINT '>>> Tabla metrics_summary creada'

END
GO

-- ============================================
-- 8. TABLA: audit_log
-- ============================================

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'audit_log' AND TABLE_SCHEMA = 'ml')
BEGIN

CREATE TABLE ml.audit_log (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id INT,
    action VARCHAR(100),
    old_values NVARCHAR(MAX),
    new_values NVARCHAR(MAX),
    user_id INT,
    ip_address VARCHAR(50),
    status VARCHAR(50),
    error_message NVARCHAR(500),
    created_at DATETIME2 DEFAULT GETUTCDATE()
)

CREATE INDEX idx_event_type ON ml.audit_log(event_type)
CREATE INDEX idx_created ON ml.audit_log(created_at)

PRINT '>>> Tabla audit_log creada'

END
GO

-- ============================================
-- 9. VISTAS
-- ============================================

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_NAME = 'v_assignment_history_summary' AND TABLE_SCHEMA = 'ml')
BEGIN

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

PRINT '>>> Vista v_assignment_history_summary creada'

END
GO

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_NAME = 'v_active_models' AND TABLE_SCHEMA = 'ml')
BEGIN

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

PRINT '>>> Vista v_active_models creada'

END
GO

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_NAME = 'v_predictions_evaluation' AND TABLE_SCHEMA = 'ml')
BEGIN

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

PRINT '>>> Vista v_predictions_evaluation creada'

END
GO

-- ============================================
-- 10. INSERTAR CONFIGURACION FASE 1
-- ============================================

IF NOT EXISTS (SELECT * FROM ml.model_configuration WHERE config_name = 'phase1_deterministic_rules')
BEGIN

INSERT INTO ml.model_configuration (config_name, config_type, configuration_json, version, created_by)
VALUES (
    'phase1_deterministic_rules',
    'phase',
    N'{"phase": 1, "enabled": true, "algorithm": "deterministic_rules", "rules": [{"name": "assign_nearest_ambulance", "priority": 1, "description": "Asigna la ambulancia mas cercana disponible"}, {"name": "validate_availability", "priority": 2, "description": "Valida que la ambulancia este disponible"}, {"name": "assign_paramedics_by_severity", "priority": 3, "description": "Asigna personal segun severidad"}], "paramedic_assignment": {"critical": {"min_paramedics": 3, "levels": ["senior", "senior", "junior"], "nurse": true}, "high": {"min_paramedics": 2, "levels": ["senior", "junior"], "nurse": true}, "medium": {"min_paramedics": 2, "levels": ["junior", "junior"], "nurse": false}, "low": {"min_paramedics": 1, "levels": ["junior"], "nurse": false}}}',
    '1.0.0',
    'SYSTEM'
)

PRINT '>>> Configuracion Fase 1 insertada'

END
GO

-- ============================================
-- 11. VERIFICACION FINAL
-- ============================================

PRINT ''
PRINT '========================================='
PRINT 'TABLAS CREADAS EN SCHEMA ML:'
PRINT '========================================='
GO

SELECT
    TABLE_NAME as 'Nombre Tabla',
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = t.TABLE_NAME AND TABLE_SCHEMA = 'ml') as 'Columnas'
FROM INFORMATION_SCHEMA.TABLES t
WHERE TABLE_SCHEMA = 'ml'
ORDER BY TABLE_NAME
GO

PRINT ''
PRINT '========================================='
PRINT 'VISTAS CREADAS:'
PRINT '========================================='
GO

SELECT TABLE_NAME as 'Vista' FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_SCHEMA = 'ml'
GO

PRINT ''
PRINT '========================================='
PRINT 'CONFIGURACION FASE 1:'
PRINT '========================================='
GO

SELECT config_name, version, is_active FROM ml.model_configuration
GO

PRINT ''
PRINT '========================================='
PRINT 'SCHEMA CREADO EXITOSAMENTE!'
PRINT '========================================='
PRINT ''
