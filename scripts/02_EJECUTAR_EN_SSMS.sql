-- ============================================
-- MS ML DESPACHO - DATABASE SCHEMA
-- COPIAR TODO ESTO EN SQL SERVER MANAGEMENT STUDIO
-- Y PRESIONAR F5 PARA EJECUTAR
-- ============================================

-- ============================================
-- 1. CREAR SCHEMA ml
-- ============================================

IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'ml')
BEGIN
    EXEC sp_executesql N'CREATE SCHEMA ml'
END
GO

PRINT 'Schema ml creado'
GO

-- ============================================
-- 2. TABLA: assignment_history (PRINCIPAL)
-- ============================================

CREATE TABLE ml.assignment_history (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
    dispatch_id INT NOT NULL,
    request_timestamp DATETIME2 NOT NULL,

    -- EMERGENCIA
    emergency_latitude DECIMAL(10, 8) NOT NULL,
    emergency_longitude DECIMAL(10, 8) NOT NULL,
    emergency_type VARCHAR(100) NOT NULL,
    emergency_description NVARCHAR(500),
    severity_level INT NOT NULL CHECK (severity_level BETWEEN 1 AND 5),

    -- CONTEXTO TEMPORAL
    hour_of_day INT NOT NULL CHECK (hour_of_day BETWEEN 0 AND 23),
    day_of_week INT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    is_weekend BIT NOT NULL,

    -- UBICACION
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(10, 8) NOT NULL,
    zone_code VARCHAR(50),

    -- DISPONIBILIDAD AMBULANCIAS
    available_ambulances_count INT NOT NULL,
    nearest_ambulance_distance_km DECIMAL(8, 3),
    available_ambulances_json NVARCHAR(MAX),

    -- DISPONIBILIDAD PERSONAL
    paramedics_available_count INT NOT NULL,
    paramedics_senior_count INT,
    paramedics_junior_count INT,
    nurses_available_count INT,
    specialists_available NVARCHAR(500),

    -- CARGA SISTEMA
    active_dispatches_count INT NOT NULL,
    ambulances_busy_percentage DECIMAL(5, 2),
    average_response_time_minutes DECIMAL(8, 2),

    -- ASIGNACION REALIZADA
    assigned_ambulance_id INT NOT NULL,
    assigned_paramedic_ids NVARCHAR(MAX),
    assigned_paramedic_levels NVARCHAR(200),

    -- POST-ASIGNACION
    actual_response_time_minutes DECIMAL(8, 2),
    actual_travel_distance_km DECIMAL(8, 3),
    patient_outcome VARCHAR(100),
    hospital_destination_id INT,
    was_optimal BIT,
    optimization_score DECIMAL(5, 4),

    -- FEEDBACK
    paramedic_satisfaction_rating INT CHECK (paramedic_satisfaction_rating BETWEEN 1 AND 5),
    patient_satisfaction_rating INT CHECK (patient_satisfaction_rating BETWEEN 1 AND 5),

    -- METADATA
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE(),
    created_by VARCHAR(100),

    -- INDICES
    INDEX idx_dispatch_id ON ml.assignment_history(dispatch_id),
    INDEX idx_created_at ON ml.assignment_history(created_at),
    INDEX idx_severity ON ml.assignment_history(severity_level),
    INDEX idx_ambulance ON ml.assignment_history(assigned_ambulance_id),
    INDEX idx_optimal ON ml.assignment_history(was_optimal)
)
GO

PRINT 'Tabla assignment_history creada'
GO

-- ============================================
-- 3. TABLA: trained_models
-- ============================================

CREATE TABLE ml.trained_models (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    algorithm_type VARCHAR(50),
    input_features NVARCHAR(MAX),
    target_variable VARCHAR(100),

    -- METRICAS
    accuracy DECIMAL(5, 4),
    precision DECIMAL(5, 4),
    recall DECIMAL(5, 4),
    f1_score DECIMAL(5, 4),

    -- ENTRENAMIENTO
    training_samples_count INT,
    training_date DATETIME2,
    training_duration_seconds INT,
    validation_accuracy DECIMAL(5, 4),
    test_accuracy DECIMAL(5, 4),

    -- MODELO
    hyperparameters NVARCHAR(MAX),
    feature_importance NVARCHAR(MAX),
    model_file_path VARCHAR(500),
    model_file_size_kb INT,

    -- ESTADO
    is_active BIT DEFAULT 0,
    is_production BIT DEFAULT 0,
    last_used_at DATETIME2,

    -- AUDITORIA
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    created_by VARCHAR(100),
    updated_at DATETIME2 DEFAULT GETUTCDATE(),

    CONSTRAINT uk_model_version UNIQUE (model_name, model_version),
    INDEX idx_active ON ml.trained_models(is_active),
    INDEX idx_production ON ml.trained_models(is_production)
)
GO

PRINT 'Tabla trained_models creada'
GO

-- ============================================
-- 4. TABLA: predictions_log
-- ============================================

CREATE TABLE ml.predictions_log (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
    dispatch_id INT NOT NULL,
    model_id INT NOT NULL,
    request_timestamp DATETIME2 NOT NULL,

    -- PREDICCION
    input_features NVARCHAR(MAX) NOT NULL,
    predicted_ambulance_id INT,
    predicted_paramedic_ids NVARCHAR(MAX),
    prediction_confidence DECIMAL(5, 4),
    prediction_timestamp DATETIME2,

    -- REAL
    actual_ambulance_id INT,
    actual_paramedic_ids NVARCHAR(MAX),
    actual_response_time_minutes DECIMAL(8, 2),

    -- EVALUACION
    prediction_correct BIT,
    prediction_accuracy_score DECIMAL(5, 4),
    feedback_score DECIMAL(5, 2),
    feedback_comments NVARCHAR(500),

    -- ESTADO
    execution_status VARCHAR(50),
    error_message NVARCHAR(500),

    -- AUDITORIA
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE(),

    CONSTRAINT fk_predictions_model FOREIGN KEY (model_id) REFERENCES ml.trained_models(id),
    INDEX idx_dispatch ON ml.predictions_log(dispatch_id),
    INDEX idx_model ON ml.predictions_log(model_id),
    INDEX idx_created ON ml.predictions_log(created_at),
    INDEX idx_correct ON ml.predictions_log(prediction_correct)
)
GO

PRINT 'Tabla predictions_log creada'
GO

-- ============================================
-- 5. TABLA: features_cache
-- ============================================

CREATE TABLE ml.features_cache (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
    dispatch_id INT NOT NULL,
    features_json NVARCHAR(MAX) NOT NULL,
    calculated_at DATETIME2 DEFAULT GETUTCDATE(),
    expires_at DATETIME2,

    INDEX idx_dispatch ON ml.features_cache(dispatch_id),
    INDEX idx_expires ON ml.features_cache(expires_at)
)
GO

PRINT 'Tabla features_cache creada'
GO

-- ============================================
-- 6. TABLA: model_configuration
-- ============================================

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
GO

PRINT 'Tabla model_configuration creada'
GO

-- ============================================
-- 7. TABLA: metrics_summary
-- ============================================

CREATE TABLE ml.metrics_summary (
    id INT IDENTITY(1,1) PRIMARY KEY NOT NULL,
    metric_date DATE NOT NULL,
    metric_hour INT,

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

PRINT 'Tabla metrics_summary creada'
GO

-- ============================================
-- 8. TABLA: audit_log
-- ============================================

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
    created_at DATETIME2 DEFAULT GETUTCDATE(),

    INDEX idx_event_type ON ml.audit_log(event_type),
    INDEX idx_created ON ml.audit_log(created_at)
)
GO

PRINT 'Tabla audit_log creada'
GO

-- ============================================
-- 9. VISTAS UTILES
-- ============================================

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

PRINT 'Vista v_assignment_history_summary creada'
GO

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

PRINT 'Vista v_active_models creada'
GO

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

PRINT 'Vista v_predictions_evaluation creada'
GO

-- ============================================
-- 10. INSERTAR CONFIGURACION FASE 1
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
            "high": {"min_paramedics": 2, "levels": ["senior", "junior"], "nurse": true},
            "medium": {"min_paramedics": 2, "levels": ["junior", "junior"], "nurse": false},
            "low": {"min_paramedics": 1, "levels": ["junior"], "nurse": false}
        }
    }',
    '1.0.0',
    'SYSTEM'
)
GO

PRINT 'Configuración Fase 1 insertada'
GO

-- ============================================
-- 11. VERIFICACION FINAL
-- ============================================

PRINT '========================================'
PRINT 'VERIFICACION DE TABLAS CREADAS'
PRINT '========================================'
GO

SELECT 'TABLAS CREADAS:' as status
UNION ALL
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'ml'
GO

SELECT COUNT(*) as 'Total Tablas' FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'ml'
GO

PRINT '========================================'
PRINT '✅ SCHEMA CREADO EXITOSAMENTE'
PRINT '========================================'
