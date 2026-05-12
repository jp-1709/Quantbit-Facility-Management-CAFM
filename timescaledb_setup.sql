-- ══════════════════════════════════════════════════
-- Phase 1: TimescaleDB Setup
-- ══════════════════════════════════════════════════

-- Create database (run this manually or via psql -c)
-- CREATE DATABASE fm_iot;

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ══════════════════════════════════════════════════
-- CORE TIME-SERIES TABLE
-- ══════════════════════════════════════════════════
CREATE TABLE sensor_readings (
    time                      TIMESTAMPTZ       NOT NULL,
    machine_id                INTEGER           NOT NULL,
    temperature               DOUBLE PRECISION,
    vibration                 DOUBLE PRECISION,
    humidity                  DOUBLE PRECISION,
    pressure                  DOUBLE PRECISION,
    energy_consumption        DOUBLE PRECISION,
    machine_status            SMALLINT,         -- 0=Idle 1=Running 2=Fault
    anomaly_flag              BOOLEAN           DEFAULT FALSE,
    predicted_remaining_life  INTEGER,          -- hours
    failure_type              TEXT              DEFAULT 'Normal',
    downtime_risk             DOUBLE PRECISION, -- 0.0 to 1.0
    maintenance_required      BOOLEAN           DEFAULT FALSE,
    source                    TEXT              DEFAULT 'csv'
);

-- Convert to hypertable (partitioned by time automatically)
SELECT create_hypertable('sensor_readings', 'time', chunk_time_interval => INTERVAL '7 days');

-- Indexes for fast queries
CREATE INDEX ON sensor_readings (machine_id, time DESC);
CREATE INDEX ON sensor_readings (failure_type, time DESC) WHERE failure_type != 'Normal';
CREATE INDEX ON sensor_readings (anomaly_flag, time DESC) WHERE anomaly_flag = TRUE;
CREATE INDEX ON sensor_readings (downtime_risk, time DESC) WHERE downtime_risk > 0.7;

-- ══════════════════════════════════════════════════
-- COMPRESSION
-- ══════════════════════════════════════════════════
ALTER TABLE sensor_readings SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'time DESC',
    timescaledb.compress_segmentby = 'machine_id'
);

SELECT add_compression_policy('sensor_readings', INTERVAL '7 days');

-- ══════════════════════════════════════════════════
-- CONTINUOUS AGGREGATES
-- ══════════════════════════════════════════════════

-- Hourly averages per machine
CREATE MATERIALIZED VIEW sensor_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time)  AS bucket,
    machine_id,
    AVG(temperature)             AS avg_temp,
    MAX(temperature)             AS max_temp,
    MIN(temperature)             AS min_temp,
    AVG(vibration)               AS avg_vib,
    MAX(vibration)               AS max_vib,
    AVG(humidity)                AS avg_humidity,
    AVG(pressure)                AS avg_pressure,
    SUM(energy_consumption)      AS total_energy,
    AVG(downtime_risk)           AS avg_risk,
    MIN(predicted_remaining_life) AS min_remaining_life,
    COUNT(*)                     AS reading_count,
    SUM(CASE WHEN anomaly_flag THEN 1 ELSE 0 END) AS anomaly_count,
    MODE() WITHIN GROUP (ORDER BY failure_type)   AS dominant_failure
FROM sensor_readings
GROUP BY bucket, machine_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('sensor_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset   => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour'
);

-- Daily summaries
CREATE MATERIALIZED VIEW sensor_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time)   AS day,
    machine_id,
    AVG(temperature)             AS avg_temp,
    MAX(temperature)             AS max_temp,
    AVG(vibration)               AS avg_vib,
    MAX(vibration)               AS max_vib,
    SUM(energy_consumption)      AS total_energy,
    AVG(downtime_risk)           AS avg_risk,
    MIN(predicted_remaining_life) AS min_remaining_life,
    COUNT(*)                     AS reading_count,
    SUM(CASE WHEN anomaly_flag THEN 1 ELSE 0 END)        AS anomaly_count,
    SUM(CASE WHEN machine_status = 2 THEN 1 ELSE 0 END)  AS fault_count,
    SUM(CASE WHEN maintenance_required THEN 1 ELSE 0 END) AS maintenance_count
FROM sensor_readings
GROUP BY day, machine_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('sensor_daily',
    start_offset => INTERVAL '2 days',
    end_offset   => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day'
);

-- ══════════════════════════════════════════════════
-- THRESHOLD CONFIG TABLE
-- ══════════════════════════════════════════════════
CREATE TABLE machine_thresholds (
    machine_id        INTEGER,
    metric_name       TEXT,
    warning_min       DOUBLE PRECISION,
    warning_max       DOUBLE PRECISION,
    critical_min      DOUBLE PRECISION,
    critical_max      DOUBLE PRECISION,
    unit              TEXT,
    auto_create_wo    BOOLEAN DEFAULT TRUE,
    wo_priority       TEXT    DEFAULT 'P2 - High',
    PRIMARY KEY (machine_id, metric_name)
);

-- Seed thresholds
INSERT INTO machine_thresholds VALUES
(0, 'temperature',        70, 90,   90, 999,  '°C',    TRUE, 'P2 - High'),
(0, 'temperature',        -999, 40, -999, 40,  '°C',    TRUE, 'P3 - Medium'),
(0, 'vibration',          60, 80,   80, 999,   'mm/s',  TRUE, 'P2 - High'),
(0, 'pressure',           -999, 1.2,-999, 1.0, 'bar',   TRUE, 'P1 - Critical'),
(0, 'energy_consumption', 4.0, 4.5, 4.5, 999,  'kWh',  TRUE, 'P3 - Medium'),
(0, 'downtime_risk',      0.7, 0.9, 0.9, 1.0,  '',     TRUE, 'P1 - Critical');
