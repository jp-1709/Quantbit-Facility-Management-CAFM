# IoT Time-Series Implementation Guide
## From CSV Data → TimescaleDB → Node-RED → Frappe API → React Dashboard

### Your Data At a Glance
- 100,000 readings · 50 machines · 70 days (Jan 1 – Mar 11, 2025)
- Metrics: temperature, vibration, humidity, pressure, energy_consumption
- ML fields: anomaly_flag, predicted_remaining_life, downtime_risk, failure_type
- Machine status: 0=Idle, 1=Running, 2=Fault
- Failure types: Normal, Overheating, Vibration Issue, Pressure Drop, Electrical Fault
- 8.9% anomaly rate · 19.7% need maintenance · 10% in fault state

---

## PHASE 1 — TimescaleDB Setup & Data Loading

### 1.1 Install TimescaleDB (Ubuntu 22.04)

```bash
# Add TimescaleDB repo
sudo apt install -y gnupg postgresql-common apt-transport-https lsb-release wget
sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh

# Install PostgreSQL 16 + TimescaleDB
sudo apt install -y postgresql-16 timescaledb-2-postgresql-16

# Auto-tune PostgreSQL for time-series
sudo timescaledb-tune --quiet --yes

# Restart
sudo systemctl restart postgresql
```

### 1.2 Create Database and Schema

```bash
sudo -u postgres psql
```

```sql
-- Create database and user
CREATE DATABASE fm_iot;
CREATE USER fm_iot_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE fm_iot TO fm_iot_user;

\c fm_iot
GRANT ALL ON SCHEMA public TO fm_iot_user;

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ══════════════════════════════════════════════════
-- CORE TIME-SERIES TABLE
-- Stores every sensor reading from every machine
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
-- COMPRESSION — saves ~90% storage for data > 7 days
-- ══════════════════════════════════════════════════
ALTER TABLE sensor_readings SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'time DESC',
    timescaledb.compress_segmentby = 'machine_id'
);

SELECT add_compression_policy('sensor_readings', INTERVAL '7 days');

-- ══════════════════════════════════════════════════
-- CONTINUOUS AGGREGATES (pre-computed rollups)
-- These run automatically as new data arrives
-- ══════════════════════════════════════════════════

-- Hourly averages per machine (for trend charts)
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

-- Daily summaries (for KPI dashboard)
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
-- THRESHOLD CONFIG TABLE (no hardcoding in code)
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

-- Seed thresholds from your data analysis
-- Temperature: avg 75°C, max observed 122°C
INSERT INTO machine_thresholds VALUES
-- machine_id=0 means "applies to all machines"
(0, 'temperature',        70, 90,   90, 999,  '°C',    TRUE, 'P2 - High'),
(0, 'temperature',        -999, 40, -999, 40,  '°C',    TRUE, 'P3 - Medium'),
(0, 'vibration',          60, 80,   80, 999,   'mm/s',  TRUE, 'P2 - High'),
(0, 'pressure',           -999, 1.2,-999, 1.0, 'bar',   TRUE, 'P1 - Critical'),
(0, 'energy_consumption', 4.0, 4.5, 4.5, 999,  'kWh',  TRUE, 'P3 - Medium'),
(0, 'downtime_risk',      0.7, 0.9, 0.9, 1.0,  '',     TRUE, 'P1 - Critical');
```

### 1.3 Load the CSV Data

```bash
# Install psycopg2
pip3 install psycopg2-binary

# Run loader script
python3 load_csv.py
```

```python
# load_csv.py — loads your 100k rows efficiently using COPY
import psycopg2
import csv
from io import StringIO
from datetime import datetime

conn = psycopg2.connect(
    host="localhost", port=5432,
    database="fm_iot", user="fm_iot_user", password="your_secure_password"
)

STATUS_MAP = {"0": 0, "1": 1, "2": 2}  # Idle / Running / Fault

print("Loading CSV into TimescaleDB...")
start = datetime.now()

buffer = StringIO()
count = 0

with open("smart_manufacturing_data.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Build tab-separated line for COPY
        line = "\t".join([
            row["timestamp"],
            row["machine_id"],
            row["temperature"],
            row["vibration"],
            row["humidity"],
            row["pressure"],
            row["energy_consumption"],
            STATUS_MAP.get(row["machine_status"], "1"),
            "true" if row["anomaly_flag"] == "1" else "false",
            row["predicted_remaining_life"],
            row["failure_type"],
            row["downtime_risk"],
            "true" if row["maintenance_required"] == "1" else "false",
            "csv"
        ])
        buffer.write(line + "\n")
        count += 1

        # Flush every 10,000 rows
        if count % 10000 == 0:
            buffer.seek(0)
            with conn.cursor() as cur:
                cur.copy_from(
                    buffer,
                    "sensor_readings",
                    columns=[
                        "time", "machine_id", "temperature", "vibration",
                        "humidity", "pressure", "energy_consumption",
                        "machine_status", "anomaly_flag", "predicted_remaining_life",
                        "failure_type", "downtime_risk", "maintenance_required", "source"
                    ],
                    sep="\t"
                )
            conn.commit()
            buffer = StringIO()
            print(f"  Loaded {count:,} rows...")

# Flush remainder
if buffer.tell() > 0:
    buffer.seek(0)
    with conn.cursor() as cur:
        cur.copy_from(buffer, "sensor_readings",
            columns=["time","machine_id","temperature","vibration",
                     "humidity","pressure","energy_consumption","machine_status",
                     "anomaly_flag","predicted_remaining_life","failure_type",
                     "downtime_risk","maintenance_required","source"],
            sep="\t")
    conn.commit()

elapsed = (datetime.now() - start).total_seconds()
print(f"Done! Loaded {count:,} rows in {elapsed:.1f}s")

# Refresh continuous aggregates immediately
with conn.cursor() as cur:
    cur.execute("CALL refresh_continuous_aggregate('sensor_hourly', NULL, NULL);")
    cur.execute("CALL refresh_continuous_aggregate('sensor_daily', NULL, NULL);")
conn.commit()
print("Continuous aggregates refreshed.")
conn.close()
```

### 1.4 Verify Load

```sql
\c fm_iot

-- Count rows
SELECT COUNT(*) FROM sensor_readings;
-- Expected: 100,000

-- Check date range
SELECT MIN(time), MAX(time) FROM sensor_readings;

-- Confirm per-machine counts
SELECT machine_id, COUNT(*) as readings
FROM sensor_readings
GROUP BY machine_id
ORDER BY machine_id
LIMIT 5;

-- Test a time-bucket query (should be fast)
SELECT
    time_bucket('1 day', time) as day,
    machine_id,
    AVG(temperature)::NUMERIC(5,2) as avg_temp,
    MAX(temperature)::NUMERIC(5,2) as max_temp,
    SUM(CASE WHEN anomaly_flag THEN 1 ELSE 0 END) as anomalies
FROM sensor_readings
WHERE machine_id = 1
GROUP BY day, machine_id
ORDER BY day;
```

---

## PHASE 2 — Node-RED: Simulate IoT Replay + Alert Routing

### 2.1 Install Node-RED and Packages

```bash
npm install -g --unsafe-perm node-red
cd ~/.node-red
npm install node-red-contrib-postgres  # TimescaleDB writes
npm install node-red-contrib-moment    # Time formatting
node-red
# Access: http://localhost:1880
```

### 2.2 Configure Environment in settings.js

```javascript
// ~/.node-red/settings.js — add inside module.exports:
process.env.TSDB_HOST     = "localhost";
process.env.TSDB_PORT     = "5432";
process.env.TSDB_DATABASE = "fm_iot";
process.env.TSDB_USER     = "fm_iot_user";
process.env.TSDB_PASS     = "your_secure_password";
process.env.FRAPPE_URL    = "http://localhost:8000";
process.env.FRAPPE_API    = "token your_key:your_secret";
```

### 2.3 Import This Flow JSON into Node-RED

Go to Node-RED UI → ☰ Menu → Import → paste this JSON:

```json
[
  {
    "id": "inject-replay",
    "type": "inject",
    "name": "Tick every 2 seconds (simulates live feed)",
    "repeat": "2",
    "once": true,
    "wires": [["query-next-batch"]]
  },
  {
    "id": "query-next-batch",
    "type": "function",
    "name": "Build next-window query",
    "func": "
      const cursor = flow.get('replay_cursor') || '2025-01-01T00:00:00';
      const windowEnd = new Date(new Date(cursor).getTime() + 120000).toISOString();
      flow.set('replay_cursor', windowEnd);
      msg.payload = {
        text: `SELECT * FROM sensor_readings
               WHERE time >= $1 AND time < $2
               ORDER BY time, machine_id`,
        values: [cursor, windowEnd]
      };
      return msg;
    ",
    "wires": [["tsdb-read"]]
  },
  {
    "id": "tsdb-read",
    "type": "postgresql",
    "name": "Read from TimescaleDB",
    "host": "localhost",
    "port": "5432",
    "database": "fm_iot",
    "user": "fm_iot_user",
    "password": "your_secure_password",
    "wires": [["split-rows"]]
  },
  {
    "id": "split-rows",
    "type": "split",
    "name": "One message per row",
    "wires": [["enrich-and-route"]]
  },
  {
    "id": "enrich-and-route",
    "type": "function",
    "name": "Enrich + Route",
    "outputs": 3,
    "func": "
      const r = msg.payload;
      const enriched = {
        machine_id: r.machine_id,
        timestamp: r.time,
        metrics: {
          temperature:        r.temperature,
          vibration:          r.vibration,
          humidity:           r.humidity,
          pressure:           r.pressure,
          energy_consumption: r.energy_consumption
        },
        status: r.machine_status,
        anomaly_flag: r.anomaly_flag,
        predicted_remaining_life: r.predicted_remaining_life,
        failure_type: r.failure_type,
        downtime_risk: r.downtime_risk,
        maintenance_required: r.maintenance_required
      };
      msg.payload = enriched;

      if (r.anomaly_flag || r.downtime_risk >= 0.9) {
        return [null, msg, null];  // → Alert path
      } else if (r.maintenance_required) {
        return [null, null, msg];  // → Maintenance path
      } else {
        return [msg, null, null];  // → Normal path
      }
    ",
    "wires": [
      ["publish-live-ui"],
      ["create-wo-alert"],
      ["create-maintenance-wr"]
    ]
  },
  {
    "id": "publish-live-ui",
    "type": "function",
    "name": "Push to Frappe Realtime",
    "func": "
      msg.method = 'POST';
      msg.url = process.env.FRAPPE_URL + 
        '/api/method/your_app.api.iot.publish_sensor_update';
      msg.headers = {
        'Content-Type': 'application/json',
        'Authorization': process.env.FRAPPE_API
      };
      msg.payload = JSON.stringify(msg.payload);
      return msg;
    ",
    "wires": [["http-frappe-realtime"]]
  },
  {
    "id": "http-frappe-realtime",
    "type": "http request",
    "name": "POST to Frappe",
    "method": "use",
    "wires": [[]]
  },
  {
    "id": "create-wo-alert",
    "type": "function",
    "name": "Build WO payload",
    "func": "
      const r = msg.payload;
      msg.method = 'POST';
      msg.url = process.env.FRAPPE_URL + '/api/resource/Work Orders';
      msg.headers = {
        'Content-Type': 'application/json',
        'Authorization': process.env.FRAPPE_API
      };
      const failureLabel = r.failure_type !== 'Normal' ? r.failure_type : 'Anomaly Detected';
      msg.payload = JSON.stringify({
        wo_title: `[AUTO] ${failureLabel} — Machine ${r.machine_id}`,
        asset_code: `MACHINE-${String(r.machine_id).padStart(3,'0')}`,
        actual_priority: r.downtime_risk >= 0.9 ? 'P1 - Critical' : 'P2 - High',
        status: 'Open',
        wo_source: 'IoT Alert',
        description: [
          `Failure Type: ${r.failure_type}`,
          `Anomaly Flag: ${r.anomaly_flag}`,
          `Downtime Risk: ${(r.downtime_risk * 100).toFixed(0)}%`,
          `Predicted Life Remaining: ${r.predicted_remaining_life}h`,
          `Temperature: ${r.metrics.temperature}°C`,
          `Vibration: ${r.metrics.vibration} mm/s`,
          `Pressure: ${r.metrics.pressure} bar`,
          `Timestamp: ${r.timestamp}`
        ].join('\\n')
      });
      return msg;
    ",
    "wires": [["http-frappe-realtime"]]
  }
]
```

---

## PHASE 3 — Frappe Backend API

### 3.1 Add psycopg2 to Frappe env

```bash
cd /home/frappe/frappe-bench
./env/bin/pip install psycopg2-binary
```

### 3.2 Add to site_config.json

```json
{
  "tsdb_host": "localhost",
  "tsdb_port": 5432,
  "tsdb_database": "fm_iot",
  "tsdb_user": "fm_iot_user",
  "tsdb_password": "your_secure_password"
}
```

### 3.3 Create API file — your_app/api/iot.py

```python
# your_app/api/iot.py
import frappe
import psycopg2
import psycopg2.extras
from contextlib import contextmanager

# ══════════════════════════════════════════════
# CONNECTION HELPER
# ══════════════════════════════════════════════
@contextmanager
def get_tsdb():
    """Context manager for TimescaleDB connections."""
    conf = frappe.conf
    conn = psycopg2.connect(
        host=conf.get("tsdb_host", "localhost"),
        port=conf.get("tsdb_port", 5432),
        database=conf.get("tsdb_database", "fm_iot"),
        user=conf.get("tsdb_user"),
        password=conf.get("tsdb_password"),
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    try:
        yield conn
    finally:
        conn.close()


# ══════════════════════════════════════════════
# ENDPOINT 1: Live sensor push from Node-RED
# ══════════════════════════════════════════════
@frappe.whitelist(allow_guest=False)
def publish_sensor_update(**kwargs):
    """
    Called by Node-RED for every sensor reading.
    Publishes to Frappe Realtime so React dashboard updates live.
    """
    payload = frappe.local.form_dict
    machine_id = payload.get("machine_id")

    frappe.publish_realtime(
        "sensor_update",
        {
            "machine_id":                machine_id,
            "timestamp":                 payload.get("timestamp"),
            "metrics":                   payload.get("metrics", {}),
            "machine_status":            payload.get("status"),
            "anomaly_flag":              payload.get("anomaly_flag"),
            "failure_type":              payload.get("failure_type"),
            "downtime_risk":             payload.get("downtime_risk"),
            "predicted_remaining_life":  payload.get("predicted_remaining_life"),
            "maintenance_required":      payload.get("maintenance_required"),
        },
        room=f"machine_{machine_id}"
    )

    # Also publish to global feed for the overview dashboard
    frappe.publish_realtime("machine_feed", {
        "machine_id":     machine_id,
        "failure_type":   payload.get("failure_type"),
        "downtime_risk":  payload.get("downtime_risk"),
        "anomaly_flag":   payload.get("anomaly_flag"),
        "timestamp":      payload.get("timestamp"),
    })

    return {"status": "ok"}


# ══════════════════════════════════════════════
# ENDPOINT 2: Machine list with latest status
# ══════════════════════════════════════════════
@frappe.whitelist()
def get_machine_overview():
    """
    Returns latest reading per machine — used for the machine grid dashboard.
    """
    with get_tsdb() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ON (machine_id)
                    machine_id,
                    time                      AS last_seen,
                    temperature,
                    vibration,
                    humidity,
                    pressure,
                    energy_consumption,
                    machine_status,
                    anomaly_flag,
                    failure_type,
                    downtime_risk,
                    predicted_remaining_life,
                    maintenance_required
                FROM sensor_readings
                ORDER BY machine_id, time DESC
            """)
            return cur.fetchall()


# ══════════════════════════════════════════════
# ENDPOINT 3: Time-series for charts
# ══════════════════════════════════════════════
@frappe.whitelist()
def get_machine_history(machine_id, metric_name, bucket="1 hour", days=7):
    """
    Returns bucketed time-series for a specific machine and metric.
    Used by the sparkline and full trend charts.
    """
    ALLOWED_METRICS = {
        "temperature", "vibration", "humidity",
        "pressure", "energy_consumption", "downtime_risk"
    }
    if metric_name not in ALLOWED_METRICS:
        frappe.throw(f"Invalid metric: {metric_name}")

    ALLOWED_BUCKETS = {"1 minute", "5 minutes", "15 minutes", "1 hour", "1 day"}
    if bucket not in ALLOWED_BUCKETS:
        bucket = "1 hour"

    with get_tsdb() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT
                    time_bucket(%s, time)         AS bucket_time,
                    AVG({metric_name})::NUMERIC(8,3) AS avg_val,
                    MAX({metric_name})::NUMERIC(8,3) AS max_val,
                    MIN({metric_name})::NUMERIC(8,3) AS min_val,
                    STDDEV({metric_name})::NUMERIC(8,3) AS std_val,
                    COUNT(*)                       AS reading_count,
                    SUM(CASE WHEN anomaly_flag THEN 1 ELSE 0 END) AS anomalies
                FROM sensor_readings
                WHERE
                    machine_id = %s
                    AND time > NOW() - (%s || ' days')::INTERVAL
                GROUP BY bucket_time
                ORDER BY bucket_time ASC
            """, (bucket, int(machine_id), str(int(days))))
            return cur.fetchall()


# ══════════════════════════════════════════════
# ENDPOINT 4: Fleet-wide KPI summary
# ══════════════════════════════════════════════
@frappe.whitelist()
def get_fleet_kpis(days=7):
    """
    Aggregate KPIs across all machines for the top stats bar.
    """
    with get_tsdb() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(DISTINCT machine_id)                         AS total_machines,
                    SUM(CASE WHEN machine_status=1 THEN 1 ELSE 0 END)  AS running,
                    SUM(CASE WHEN machine_status=2 THEN 1 ELSE 0 END)  AS in_fault,
                    SUM(CASE WHEN machine_status=0 THEN 1 ELSE 0 END)  AS idle,
                    SUM(CASE WHEN anomaly_flag THEN 1 ELSE 0 END)       AS anomalies,
                    SUM(CASE WHEN maintenance_required THEN 1 ELSE 0 END) AS need_maintenance,
                    AVG(temperature)::NUMERIC(5,2)                      AS fleet_avg_temp,
                    SUM(energy_consumption)::NUMERIC(10,2)              AS total_energy_kwh,
                    AVG(downtime_risk)::NUMERIC(5,3)                    AS avg_downtime_risk
                FROM sensor_readings
                WHERE time > NOW() - (%s || ' days')::INTERVAL
            """, (str(int(days)),))
            return cur.fetchone()


# ══════════════════════════════════════════════
# ENDPOINT 5: Failure analysis
# ══════════════════════════════════════════════
@frappe.whitelist()
def get_failure_breakdown(machine_id=None, days=30):
    """
    Failure type distribution — for the pie chart / breakdown panel.
    Pass machine_id for per-machine view, omit for fleet-wide.
    """
    with get_tsdb() as conn:
        with conn.cursor() as cur:
            if machine_id:
                cur.execute("""
                    SELECT
                        failure_type,
                        COUNT(*) AS count,
                        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
                    FROM sensor_readings
                    WHERE
                        machine_id = %s
                        AND time > NOW() - (%s || ' days')::INTERVAL
                    GROUP BY failure_type
                    ORDER BY count DESC
                """, (int(machine_id), str(int(days))))
            else:
                cur.execute("""
                    SELECT
                        failure_type,
                        COUNT(*) AS count,
                        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
                    FROM sensor_readings
                    WHERE time > NOW() - (%s || ' days')::INTERVAL
                    GROUP BY failure_type
                    ORDER BY count DESC
                """, (str(int(days)),))
            return cur.fetchall()


# ══════════════════════════════════════════════
# ENDPOINT 6: Critical machines (high risk)
# ══════════════════════════════════════════════
@frappe.whitelist()
def get_critical_machines(risk_threshold=0.7):
    """
    Machines with high downtime risk — sorted worst-first.
    Used for the alert/priority panel.
    """
    with get_tsdb() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ON (machine_id)
                    machine_id,
                    time                      AS last_seen,
                    downtime_risk,
                    predicted_remaining_life,
                    failure_type,
                    temperature,
                    vibration,
                    machine_status
                FROM sensor_readings
                WHERE
                    downtime_risk >= %s
                    AND time > NOW() - INTERVAL '24 hours'
                ORDER BY machine_id, time DESC
            """, (float(risk_threshold),))
            rows = cur.fetchall()

        # Sort by risk descending
        return sorted(rows, key=lambda r: r["downtime_risk"], reverse=True)


# ══════════════════════════════════════════════
# ENDPOINT 7: Energy consumption trend
# ══════════════════════════════════════════════
@frappe.whitelist()
def get_energy_trend(days=30):
    """Daily energy totals for all machines — for energy dashboard."""
    with get_tsdb() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    time_bucket('1 day', time)  AS day,
                    SUM(energy_consumption)      AS total_kwh,
                    AVG(energy_consumption)      AS avg_kwh_per_reading,
                    COUNT(*)                     AS readings
                FROM sensor_readings
                WHERE time > NOW() - (%s || ' days')::INTERVAL
                GROUP BY day
                ORDER BY day ASC
            """, (str(int(days)),))
            return cur.fetchall()


# ══════════════════════════════════════════════
# ENDPOINT 8: Anomaly timeline for one machine
# ══════════════════════════════════════════════
@frappe.whitelist()
def get_anomaly_timeline(machine_id, days=7):
    """
    Returns all anomaly events for a machine — for the timeline view.
    """
    with get_tsdb() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    time,
                    temperature,
                    vibration,
                    pressure,
                    energy_consumption,
                    failure_type,
                    downtime_risk,
                    predicted_remaining_life,
                    maintenance_required
                FROM sensor_readings
                WHERE
                    machine_id = %s
                    AND anomaly_flag = TRUE
                    AND time > NOW() - (%s || ' days')::INTERVAL
                ORDER BY time DESC
                LIMIT 200
            """, (int(machine_id), str(int(days))))
            return cur.fetchall()
```

### 3.4 Register API in hooks.py

```python
# your_app/hooks.py
app_include_js = []
app_include_css = []

# No changes needed — @frappe.whitelist() registers routes automatically
```

---

## PHASE 4 — React Frontend

### 4.1 useMachineData Hook

```typescript
// src/hooks/useMachineData.ts
import { useState, useEffect, useCallback } from "react";

const API_BASE = "/api/method/your_app.api.iot";

async function apiGet<T>(method: string, params: Record<string, any> = {}): Promise<T> {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`${API_BASE}.${method}?${qs}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`API error: ${res.statusText}`);
  const json = await res.json();
  return json.message as T;
}

export interface MachineOverview {
  machine_id: number;
  last_seen: string;
  temperature: number;
  vibration: number;
  humidity: number;
  pressure: number;
  energy_consumption: number;
  machine_status: 0 | 1 | 2;
  anomaly_flag: boolean;
  failure_type: string;
  downtime_risk: number;
  predicted_remaining_life: number;
  maintenance_required: boolean;
}

export interface FleetKPIs {
  total_machines: number;
  running: number;
  in_fault: number;
  idle: number;
  anomalies: number;
  need_maintenance: number;
  fleet_avg_temp: number;
  total_energy_kwh: number;
  avg_downtime_risk: number;
}

export interface TimeSeriesPoint {
  bucket_time: string;
  avg_val: number;
  max_val: number;
  min_val: number;
  std_val: number;
  reading_count: number;
  anomalies: number;
}

export interface FailureBreakdown {
  failure_type: string;
  count: number;
  pct: number;
}

// ── Hook: Fleet overview grid
export function useMachineOverview() {
  const [data, setData] = useState<MachineOverview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch_ = useCallback(async () => {
    setLoading(true);
    try {
      const result = await apiGet<MachineOverview[]>("get_machine_overview");
      setData(result);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch_(); }, [fetch_]);

  // Live update via Frappe realtime
  useEffect(() => {
    const rt = (window as any).frappe?.realtime;
    if (!rt) return;
    const handler = (update: any) => {
      setData((prev) =>
        prev.map((m) =>
          m.machine_id === Number(update.machine_id)
            ? {
                ...m,
                machine_status:            update.machine_status ?? m.machine_status,
                anomaly_flag:              update.anomaly_flag    ?? m.anomaly_flag,
                failure_type:              update.failure_type    ?? m.failure_type,
                downtime_risk:             update.downtime_risk   ?? m.downtime_risk,
                predicted_remaining_life:  update.predicted_remaining_life ?? m.predicted_remaining_life,
                last_seen:                 update.timestamp       ?? m.last_seen,
                ...update.metrics,
              }
            : m
        )
      );
    };
    rt.on("machine_feed", handler);
    return () => rt.off("machine_feed", handler);
  }, []);

  return { data, loading, error, refetch: fetch_ };
}

// ── Hook: Fleet KPIs
export function useFleetKPIs(days = 7) {
  const [kpis, setKpis] = useState<FleetKPIs | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<FleetKPIs>("get_fleet_kpis", { days })
      .then(setKpis)
      .finally(() => setLoading(false));
  }, [days]);

  return { kpis, loading };
}

// ── Hook: Machine time-series for charts
export function useMachineHistory(
  machineId: number,
  metric: string,
  bucket = "1 hour",
  days = 7
) {
  const [data, setData] = useState<TimeSeriesPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!machineId) return;
    setLoading(true);
    apiGet<TimeSeriesPoint[]>("get_machine_history", {
      machine_id: machineId,
      metric_name: metric,
      bucket,
      days,
    })
      .then(setData)
      .finally(() => setLoading(false));
  }, [machineId, metric, bucket, days]);

  return { data, loading };
}

// ── Hook: Failure breakdown
export function useFailureBreakdown(machineId?: number, days = 30) {
  const [data, setData] = useState<FailureBreakdown[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const params: any = { days };
    if (machineId) params.machine_id = machineId;
    apiGet<FailureBreakdown[]>("get_failure_breakdown", params)
      .then(setData)
      .finally(() => setLoading(false));
  }, [machineId, days]);

  return { data, loading };
}

// ── Hook: Critical machines
export function useCriticalMachines(threshold = 0.7) {
  const [data, setData] = useState<MachineOverview[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch_ = useCallback(() => {
    apiGet<MachineOverview[]>("get_critical_machines", {
      risk_threshold: threshold,
    })
      .then(setData)
      .finally(() => setLoading(false));
  }, [threshold]);

  useEffect(() => { fetch_(); }, [fetch_]);

  // Refresh on new alert
  useEffect(() => {
    const rt = (window as any).frappe?.realtime;
    if (!rt) return;
    const h = () => fetch_();
    rt.on("machine_feed", h);
    return () => rt.off("machine_feed", h);
  }, [fetch_]);

  return { data, loading, refetch: fetch_ };
}
```

### 4.2 Machine Status Config (no hardcoding)

```typescript
// src/config/machineConfig.ts

export const MACHINE_STATUS: Record<number, { label: string; color: string; dot: string; bg: string }> = {
  0: { label: "Idle",    color: "#6b7280", dot: "bg-gray-400",    bg: "bg-gray-50"   },
  1: { label: "Running", color: "#10b981", dot: "bg-emerald-500", bg: "bg-emerald-50"},
  2: { label: "Fault",   color: "#ef4444", dot: "bg-red-500",     bg: "bg-red-50"    },
};

export const FAILURE_COLORS: Record<string, string> = {
  Normal:           "#10b981",
  Overheating:      "#ef4444",
  "Vibration Issue":"#f97316",
  "Pressure Drop":  "#8b5cf6",
  "Electrical Fault":"#f59e0b",
};

export const METRIC_CONFIG: Record<string, {
  label: string; unit: string; warningMax: number; criticalMax: number; color: string;
}> = {
  temperature:        { label: "Temperature",   unit: "°C",  warningMax: 90,  criticalMax: 105, color: "#ef4444" },
  vibration:          { label: "Vibration",     unit: "mm/s",warningMax: 70,  criticalMax: 90,  color: "#f97316" },
  humidity:           { label: "Humidity",      unit: "%",   warningMax: 78,  criticalMax: 80,  color: "#3b82f6" },
  pressure:           { label: "Pressure",      unit: "bar", warningMax: 4.5, criticalMax: 5.0, color: "#8b5cf6" },
  energy_consumption: { label: "Energy",        unit: "kWh", warningMax: 4.0, criticalMax: 4.8, color: "#f59e0b" },
  downtime_risk:      { label: "Downtime Risk", unit: "%",   warningMax: 0.7, criticalMax: 0.9, color: "#dc2626" },
};
```

### 4.3 IoT Dashboard Page Component

```tsx
// src/pages/IotDashboard.tsx
import { useState } from "react";
import { AlertTriangle, Activity, Zap, Thermometer,
         RefreshCw, ChevronRight, Clock } from "lucide-react";
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend
} from "recharts";
import {
  useMachineOverview, useFleetKPIs, useCriticalMachines,
  useMachineHistory, useFailureBreakdown
} from "../hooks/useMachineData";
import { MACHINE_STATUS, FAILURE_COLORS, METRIC_CONFIG } from "../config/machineConfig";

/* ─── SMALL HELPERS ─── */

function RiskBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = value >= 0.9 ? "#ef4444" : value >= 0.7 ? "#f59e0b" : "#10b981";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-xs font-bold tabular-nums" style={{ color }}>{pct}%</span>
    </div>
  );
}

function StatusDot({ status }: { status: 0 | 1 | 2 }) {
  const cfg = MACHINE_STATUS[status] || MACHINE_STATUS[0];
  return (
    <span className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${cfg.dot} ${status === 1 ? "animate-pulse" : ""}`} />
      <span className="text-xs font-medium" style={{ color: cfg.color }}>{cfg.label}</span>
    </span>
  );
}

function MetricChip({ label, value, unit, isCritical }: {
  label: string; value: number; unit: string; isCritical?: boolean;
}) {
  return (
    <div className={`px-2.5 py-1.5 rounded-lg border ${isCritical ? "bg-red-50 border-red-200" : "bg-muted/30 border-border/50"}`}>
      <p className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className={`text-sm font-bold tabular-nums ${isCritical ? "text-red-600" : "text-foreground"}`}>
        {value?.toFixed(1)}<span className="text-[10px] font-normal ml-0.5">{unit}</span>
      </p>
    </div>
  );
}

/* ─── MACHINE CARD ─── */
function MachineCard({ m, onClick, selected }: {
  m: any; onClick: () => void; selected: boolean;
}) {
  const cfg = MACHINE_STATUS[m.machine_status as 0|1|2] || MACHINE_STATUS[1];
  const tempCfg = METRIC_CONFIG.temperature;
  const isTempHigh = m.temperature > tempCfg.criticalMax;
  const isVibHigh  = m.vibration   > METRIC_CONFIG.vibration.criticalMax;

  return (
    <button onClick={onClick}
      className={`w-full text-left p-4 rounded-2xl border transition-all duration-200 hover:shadow-md
        ${selected ? "border-primary shadow-md ring-1 ring-primary/20" : "border-border hover:border-primary/30"}
        ${m.anomaly_flag ? "border-l-4 border-l-red-500" : m.maintenance_required ? "border-l-4 border-l-amber-500" : ""}
      `}
      style={{ background: selected ? `${cfg.color}06` : undefined }}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="text-sm font-bold text-foreground">Machine {m.machine_id}</p>
          <StatusDot status={m.machine_status} />
        </div>
        {m.failure_type !== "Normal" && (
          <span className="text-[9px] font-bold px-2 py-0.5 rounded-full text-white"
            style={{ background: FAILURE_COLORS[m.failure_type] || "#6b7280" }}>
            {m.failure_type}
          </span>
        )}
        {m.anomaly_flag && (
          <AlertTriangle className="w-4 h-4 text-red-500 animate-pulse" />
        )}
      </div>

      <div className="grid grid-cols-2 gap-1.5 mb-3">
        <MetricChip label="Temp" value={m.temperature} unit="°C" isCritical={isTempHigh} />
        <MetricChip label="Vibr" value={m.vibration}   unit="mm/s" isCritical={isVibHigh} />
        <MetricChip label="Press" value={m.pressure}    unit="bar" />
        <MetricChip label="Energy" value={m.energy_consumption} unit="kWh" />
      </div>

      <div className="space-y-1">
        <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-0.5">
          <span>Downtime Risk</span>
          <span className="flex items-center gap-1">
            <Clock className="w-2.5 h-2.5" />
            {m.predicted_remaining_life}h left
          </span>
        </div>
        <RiskBar value={m.downtime_risk} />
      </div>
    </button>
  );
}

/* ─── MACHINE DETAIL PANEL ─── */
function MachineDetail({ machineId, onClose }: { machineId: number; onClose: () => void }) {
  const [metric, setMetric] = useState("temperature");
  const [days, setDays] = useState(7);
  const { data: history, loading: histLoading } = useMachineHistory(machineId, metric, "1 hour", days);
  const { data: failures } = useFailureBreakdown(machineId, 30);
  const metricCfg = METRIC_CONFIG[metric];

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-4 border-b border-border bg-card shrink-0">
        <div>
          <h3 className="text-base font-bold text-foreground">Machine {machineId}</h3>
          <p className="text-xs text-muted-foreground">Detailed sensor analysis</p>
        </div>
        <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-muted transition-colors">
          <span className="text-muted-foreground text-lg leading-none">×</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4">
        {/* Metric selector */}
        <div className="flex flex-wrap gap-2 mb-4">
          {Object.entries(METRIC_CONFIG).map(([key, cfg]) => (
            <button key={key}
              onClick={() => setMetric(key)}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all border
                ${metric === key
                  ? "text-white border-transparent shadow-sm"
                  : "border-border text-foreground hover:border-primary/40"}`}
              style={metric === key ? { background: cfg.color, borderColor: cfg.color } : {}}>
              {cfg.label}
            </button>
          ))}
        </div>

        {/* Time range */}
        <div className="flex gap-2 mb-4">
          {[1, 7, 14, 30].map((d) => (
            <button key={d} onClick={() => setDays(d)}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all
                ${days === d ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground"}`}>
              {d}d
            </button>
          ))}
        </div>

        {/* Trend chart */}
        <div className="mb-5">
          <p className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
            {metricCfg.label} Trend — Last {days} days
          </p>
          {histLoading ? (
            <div className="h-48 bg-muted/20 rounded-xl animate-pulse" />
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={history}>
                <defs>
                  <linearGradient id="grad-metric" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={metricCfg.color} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={metricCfg.color} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="bucket_time"
                  tickFormatter={(v) => new Date(v).toLocaleDateString("en-GB", { day: "2-digit", month: "short" })}
                  tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip
                  formatter={(v: any, name: string) => [`${Number(v).toFixed(2)} ${metricCfg.unit}`, name]}
                  labelFormatter={(l) => new Date(l).toLocaleString()} />
                <Area type="monotone" dataKey="avg_val" stroke={metricCfg.color}
                  fill="url(#grad-metric)" strokeWidth={2} name="Average" dot={false} />
                <Area type="monotone" dataKey="max_val" stroke={`${metricCfg.color}60`}
                  fill="none" strokeDasharray="3 3" strokeWidth={1} name="Max" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Anomaly count bar */}
        <div className="mb-5">
          <p className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
            Anomalies per period
          </p>
          <ResponsiveContainer width="100%" height={100}>
            <BarChart data={history}>
              <XAxis dataKey="bucket_time"
                tickFormatter={(v) => new Date(v).toLocaleDateString("en-GB", { day: "2-digit", month: "short" })}
                tick={{ fontSize: 9 }} />
              <YAxis tick={{ fontSize: 9 }} />
              <Tooltip formatter={(v: any) => [v, "Anomalies"]} />
              <Bar dataKey="anomalies" fill="#ef4444" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Failure breakdown */}
        {failures.length > 0 && (
          <div>
            <p className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-3">
              30-day Failure Distribution
            </p>
            <div className="flex items-center gap-4">
              <PieChart width={120} height={120}>
                <Pie data={failures} cx={55} cy={55} innerRadius={30} outerRadius={55}
                  dataKey="count" nameKey="failure_type">
                  {failures.map((entry) => (
                    <Cell key={entry.failure_type}
                      fill={FAILURE_COLORS[entry.failure_type] || "#6b7280"} />
                  ))}
                </Pie>
              </PieChart>
              <div className="flex flex-col gap-1.5">
                {failures.map((f) => (
                  <div key={f.failure_type} className="flex items-center gap-2 text-xs">
                    <span className="w-2.5 h-2.5 rounded-full shrink-0"
                      style={{ background: FAILURE_COLORS[f.failure_type] || "#6b7280" }} />
                    <span className="text-foreground font-medium">{f.failure_type}</span>
                    <span className="text-muted-foreground ml-auto">{f.pct}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── MAIN DASHBOARD ─── */
export default function IotDashboard() {
  const [days, setDays] = useState(7);
  const [selectedMachine, setSelectedMachine] = useState<number | null>(null);
  const [filterStatus, setFilterStatus] = useState<number | null>(null);
  const [filterFailure, setFilterFailure] = useState<string>("");
  const [sortBy, setSortBy] = useState<"risk" | "id" | "temp">("risk");
  const [search, setSearch] = useState("");

  const { data: machines, loading, refetch } = useMachineOverview();
  const { kpis } = useFleetKPIs(days);
  const { data: critical } = useCriticalMachines(0.7);

  /* Filter + sort */
  const filtered = machines
    .filter((m) => {
      if (filterStatus !== null && m.machine_status !== filterStatus) return false;
      if (filterFailure && m.failure_type !== filterFailure) return false;
      if (search && !String(m.machine_id).includes(search)) return false;
      return true;
    })
    .sort((a, b) =>
      sortBy === "risk"  ? b.downtime_risk - a.downtime_risk :
      sortBy === "temp"  ? b.temperature  - a.temperature :
      a.machine_id - b.machine_id
    );

  const statCards = kpis ? [
    { label: "Total Machines",   value: kpis.total_machines,                        icon: <Activity className="w-4 h-4" />, color: "#4f46e5", bg: "#4f46e515" },
    { label: "Running",          value: kpis.running,                               icon: <Activity className="w-4 h-4" />, color: "#10b981", bg: "#10b98115" },
    { label: "In Fault",         value: kpis.in_fault,                              icon: <AlertTriangle className="w-4 h-4" />, color: "#ef4444", bg: "#ef444415" },
    { label: "Need Maintenance", value: kpis.need_maintenance,                      icon: <AlertTriangle className="w-4 h-4" />, color: "#f59e0b", bg: "#f59e0b15" },
    { label: "Anomalies",        value: kpis.anomalies,                             icon: <Zap className="w-4 h-4" />,        color: "#dc2626", bg: "#dc262615" },
    { label: "Avg Temp",         value: `${kpis.fleet_avg_temp}°C`,                icon: <Thermometer className="w-4 h-4" />, color: "#0891b2", bg: "#0891b215" },
    { label: "Total Energy",     value: `${Number(kpis.total_energy_kwh).toFixed(0)} kWh`, icon: <Zap className="w-4 h-4" />, color: "#059669", bg: "#05966915" },
    { label: "Avg Risk",         value: `${(kpis.avg_downtime_risk * 100).toFixed(0)}%`, icon: <AlertTriangle className="w-4 h-4" />, color: "#9333ea", bg: "#9333ea15" },
  ] : [];

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Top bar */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-border bg-card shadow-sm">
        <h1 className="text-2xl font-bold text-foreground">IoT Machine Monitor</h1>
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            {[1, 7, 30].map((d) => (
              <button key={d} onClick={() => setDays(d)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all
                  ${days === d ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground"}`}>
                {d === 1 ? "24h" : `${d}d`}
              </button>
            ))}
          </div>
          <button onClick={refetch} className="p-2 rounded-lg hover:bg-muted transition-colors">
            <RefreshCw className={`w-4 h-4 text-muted-foreground ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* KPI Stats Bar */}
      <div className="grid grid-cols-4 xl:grid-cols-8 border-b border-border bg-card">
        {statCards.map(({ label, value, icon, color, bg }) => (
          <div key={label} className="flex items-center gap-2.5 px-4 py-3 border-r border-border/50 last:border-r-0">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
              style={{ background: bg, color }}>
              {icon}
            </div>
            <div>
              <p className="text-base font-bold text-foreground leading-none">{value ?? "—"}</p>
              <p className="text-[9px] text-muted-foreground font-medium mt-0.5">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: filter + machine grid */}
        <div className={`flex flex-col overflow-hidden border-r border-border ${selectedMachine ? "w-[560px] min-w-[400px]" : "flex-1"}`}>
          {/* Filters */}
          <div className="flex items-center gap-2 px-5 py-2.5 border-b border-border bg-card flex-wrap">
            <input value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="Machine #"
              className="px-3 py-1.5 border border-border rounded-lg text-xs bg-background w-24 focus:outline-none focus:ring-2 focus:ring-ring" />

            {/* Status filter */}
            {Object.entries(MACHINE_STATUS).map(([k, cfg]) => (
              <button key={k}
                onClick={() => setFilterStatus(filterStatus === Number(k) ? null : Number(k))}
                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-full border text-xs font-semibold transition-all
                  ${filterStatus === Number(k) ? "text-white border-transparent" : "border-border text-foreground hover:bg-muted"}`}
                style={filterStatus === Number(k) ? { background: cfg.color } : {}}>
                <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />{cfg.label}
              </button>
            ))}

            {/* Failure filter */}
            <select value={filterFailure} onChange={(e) => setFilterFailure(e.target.value)}
              className="px-2.5 py-1.5 border border-border rounded-full text-xs bg-background focus:outline-none focus:ring-2 focus:ring-ring">
              <option value="">All Failures</option>
              {Object.entries(FAILURE_COLORS).map(([k]) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>

            {/* Sort */}
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value as any)}
              className="px-2.5 py-1.5 border border-border rounded-full text-xs bg-background focus:outline-none focus:ring-2 focus:ring-ring ml-auto">
              <option value="risk">Sort: Risk ↓</option>
              <option value="temp">Sort: Temp ↓</option>
              <option value="id">Sort: Machine ID</option>
            </select>

            <span className="text-xs text-muted-foreground font-medium">
              {filtered.length}/{machines.length}
            </span>
          </div>

          {/* Machine grid */}
          <div className="flex-1 overflow-y-auto p-4">
            {loading ? (
              <div className="grid grid-cols-2 xl:grid-cols-3 gap-3">
                {[...Array(12)].map((_, i) => (
                  <div key={i} className="h-48 rounded-2xl bg-muted animate-pulse" />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-2 xl:grid-cols-3 gap-3">
                {filtered.map((m) => (
                  <MachineCard key={m.machine_id} m={m}
                    selected={selectedMachine === m.machine_id}
                    onClick={() => setSelectedMachine(
                      selectedMachine === m.machine_id ? null : m.machine_id
                    )} />
                ))}
              </div>
            )}

            {!loading && filtered.length === 0 && (
              <div className="flex flex-col items-center justify-center py-20 text-muted-foreground gap-3">
                <Activity className="w-10 h-10 opacity-30" />
                <p className="text-sm font-semibold text-foreground">No machines match filters</p>
                <button onClick={() => { setFilterStatus(null); setFilterFailure(""); setSearch(""); }}
                  className="text-xs text-primary hover:underline">Clear filters</button>
              </div>
            )}
          </div>
        </div>

        {/* Right: Machine detail panel */}
        {selectedMachine && (
          <div className="flex-1 overflow-hidden border-l border-border bg-card">
            <MachineDetail machineId={selectedMachine}
              onClose={() => setSelectedMachine(null)} />
          </div>
        )}

        {/* Right: Critical alert sidebar (when nothing selected) */}
        {!selectedMachine && critical.length > 0 && (
          <div className="w-72 border-l border-border bg-card flex flex-col overflow-hidden">
            <div className="px-4 py-3 border-b border-border">
              <p className="text-xs font-bold uppercase tracking-wider text-red-600 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5" /> Critical Machines ({critical.length})
              </p>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
              {critical.slice(0, 15).map((m: any) => (
                <button key={m.machine_id}
                  onClick={() => setSelectedMachine(m.machine_id)}
                  className="w-full text-left p-3 rounded-xl border border-red-200 bg-red-50/60 hover:bg-red-50 transition-colors">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-bold text-foreground">Machine {m.machine_id}</span>
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full text-white"
                      style={{ background: FAILURE_COLORS[m.failure_type] || "#ef4444" }}>
                      {m.failure_type}
                    </span>
                  </div>
                  <RiskBar value={m.downtime_risk} />
                  <div className="flex items-center justify-between mt-1.5 text-[10px] text-muted-foreground">
                    <span>{m.temperature?.toFixed(1)}°C</span>
                    <span className="flex items-center gap-1"><Clock className="w-2.5 h-2.5" />{m.predicted_remaining_life}h</span>
                    <ChevronRight className="w-3 h-3" />
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

---

## PHASE 5 — Wire It All Together

### 5.1 Add to your React Router

```tsx
// src/App.tsx — add this route
<Route path="/iot-dashboard" element={<IotDashboard />} />
```

### 5.2 Add the nav link to your sidebar

```tsx
// In your sidebar/nav component
{ path: "/iot-dashboard", icon: <Activity />, label: "IoT Monitor" }
```

### 5.3 Start everything

```bash
# Terminal 1: TimescaleDB (already running after apt install)

# Terminal 2: Node-RED
node-red

# Terminal 3: Frappe
cd /home/frappe/frappe-bench
bench start

# Terminal 4: Load data (one-time)
python3 load_csv.py
```

---

## Quick Verification Checklist

```bash
# 1. Data loaded?
psql -U fm_iot_user -d fm_iot -c "SELECT COUNT(*) FROM sensor_readings;"
# Expected: 100000

# 2. Continuous aggregates working?
psql -U fm_iot_user -d fm_iot -c "SELECT COUNT(*) FROM sensor_hourly;"

# 3. Frappe API responding?
curl "http://localhost:8000/api/method/your_app.api.iot.get_fleet_kpis" \
  -H "Authorization: token key:secret"

# 4. Node-RED flow running?
# Open http://localhost:1880 → check flow is deployed

# 5. React dashboard loading?
# Open http://localhost:8000 → navigate to /iot-dashboard
```

---

## Data Field Reference

| CSV Field | TimescaleDB Column | Type | Description |
|---|---|---|---|
| timestamp | time | TIMESTAMPTZ | Reading timestamp |
| machine_id | machine_id | INTEGER | 1–50 |
| temperature | temperature | DOUBLE | °C (35–122) |
| vibration | vibration | DOUBLE | mm/s (-17–114) |
| humidity | humidity | DOUBLE | % (30–80) |
| pressure | pressure | DOUBLE | bar (1–5) |
| energy_consumption | energy_consumption | DOUBLE | kWh (0.5–5) |
| machine_status | machine_status | SMALLINT | 0=Idle 1=Running 2=Fault |
| anomaly_flag | anomaly_flag | BOOLEAN | 8.9% of rows |
| predicted_remaining_life | predicted_remaining_life | INTEGER | hours (1–499) |
| failure_type | failure_type | TEXT | Normal/Overheating/Vibration Issue/Pressure Drop/Electrical Fault |
| downtime_risk | downtime_risk | DOUBLE | 0.0–1.0 |
| maintenance_required | maintenance_required | BOOLEAN | 19.7% of rows |
