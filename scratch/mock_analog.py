import sqlite3
from datetime import datetime, timedelta

db_path = r"C:\Users\markn\Downloads\home-assistant_v2.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Get the metadata ID for Solcast
cursor.execute("SELECT id FROM statistics_meta WHERE statistic_id = ?", ("sensor.solcast_pv_forecast_forecast_tomorrow",))
meta_row = cursor.fetchone()
if not meta_row:
    print("Meta ID not found!")
    exit(1)
meta_id = meta_row[0]

# 2. Get all statistics for the last 365 days
end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
start_date = end_date - timedelta(days=365)

# Convert to timestamps
start_ts = start_date.timestamp()
end_ts = end_date.timestamp()

cursor.execute("""
    SELECT start_ts, state, sum, mean, max, min 
    FROM statistics 
    WHERE metadata_id = ? AND start_ts >= ? AND start_ts < ?
    ORDER BY start_ts ASC
""", (meta_id, start_ts, end_ts))

rows = cursor.fetchall()
print(f"Fetched {len(rows)} rows from statistics table.")

# 3. Replicate the HA logic
daily_yields = {}

for row in rows:
    start_time, state, sum_val, mean_val, max_val, min_val = row
    row_start = datetime.fromtimestamp(start_time)
    
    # In HA code: forecast_date = (row_start + timedelta(days=1)).date()
    forecast_date = (row_start + timedelta(days=1)).date()
    
    if forecast_date < end_date.date():
        val = max_val or mean_val or state
        if val is not None:
            daily_yields[forecast_date] = max(val, daily_yields.get(forecast_date, 0))

print(f"\nExtracted {len(daily_yields)} unique days.")
if daily_yields:
    print("\nSample of daily yields:")
    # Print the last 10
    sorted_days = sorted(daily_yields.items())
    for d, y in sorted_days[-10:]:
        print(f"  {d}: {y:.2f} kWh")
else:
    print("\nNO DAILY YIELDS EXTRACTED!")

conn.close()
