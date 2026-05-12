# load_csv.py — loads 100k rows efficiently using COPY
import psycopg2
import csv
from io import StringIO
from datetime import datetime
import os

# Configuration
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "fm_iot",
    "user": "fm_iot_user",
    "password": "iot_pass_123"
}

STATUS_MAP = {"0": 0, "1": 1, "2": 2}  # Idle / Running / Fault

def load_data():
    csv_file = "/home/erpnext/facility-bench/apps/quantbit_facility_management/smart_manufacturing_data.csv"
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found.")
        return

    conn = psycopg2.connect(**DB_CONFIG)
    
    print("Loading CSV into TimescaleDB...")
    start = datetime.now()

    buffer = StringIO()
    count = 0

    with open(csv_file) as f:
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
                str(STATUS_MAP.get(row["machine_status"], 1)),
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
    conn.autocommit = True
    with conn.cursor() as cur:
        try:
            cur.execute("CALL refresh_continuous_aggregate('sensor_hourly', NULL, NULL);")
            cur.execute("CALL refresh_continuous_aggregate('sensor_daily', NULL, NULL);")
            print("Continuous aggregates refreshed.")
        except Exception as e:
            print(f"Warning: Could not refresh aggregates: {e}")
    conn.close()

if __name__ == "__main__":
    load_data()
