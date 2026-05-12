# quantbit_facility_management/api/iot.py
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
        user=conf.get("tsdb_user", "fm_iot_user"),
        password=conf.get("tsdb_password", "iot_pass_123"),
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
    """Aggregate KPIs across all machines."""
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
    """Failure type distribution."""
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
    """Machines with high downtime risk."""
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
        return sorted(rows, key=lambda r: r["downtime_risk"], reverse=True)


# ══════════════════════════════════════════════
# ENDPOINT 7: Energy consumption trend
# ══════════════════════════════════════════════
@frappe.whitelist()
def get_energy_trend(days=30):
    """Daily energy totals."""
    with get_tsdb() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    time_bucket('1 day', time)  AS day,
                    SUM(energy_consumption)      AS total_kwh,
                    AVG(energy_consumption)      AS avg_kwh_per_reading
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
    """Returns all anomaly events for a machine."""
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
                    predicted_remaining_life
                FROM sensor_readings
                WHERE
                    machine_id = %s
                    AND anomaly_flag = TRUE
                    AND time > NOW() - (%s || ' days')::INTERVAL
                ORDER BY time DESC
                LIMIT 100
            """, (int(machine_id), str(int(days))))
            return cur.fetchall()
