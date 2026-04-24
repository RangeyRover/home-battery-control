import sqlite3
from datetime import datetime, timedelta

db_path = r"C:\Users\markn\Downloads\home-assistant_v2.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def get_meta_id(entity_id):
    cursor.execute("SELECT id FROM statistics_meta WHERE statistic_id = ?", (entity_id,))
    row = cursor.fetchone()
    return row[0] if row else None

# --- CONFIGURATION ---
solcast_entity = "sensor.solcast_pv_forecast_forecast_tomorrow"
import_price_entity = "sensor.4_rosella_general_price"
export_price_entity = "sensor.4_rosella_feed_in_price"
load_entity = "sensor.powerwall_2_home_usage"
target_kwh = 20.0

# 1. Fetch Daily Yields for Solcast
solcast_meta_id = get_meta_id(solcast_entity)
end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
start_date = end_date - timedelta(days=365)

cursor.execute("""
    SELECT start_ts, state, sum, mean, max, min 
    FROM statistics 
    WHERE metadata_id = ? AND start_ts >= ? AND start_ts < ?
    ORDER BY start_ts ASC
""", (solcast_meta_id, start_date.timestamp(), end_date.timestamp()))

daily_yields = {}
for row in cursor.fetchall():
    start_time, state, sum_val, mean_val, max_val, min_val = row
    row_start = datetime.fromtimestamp(start_time)
    forecast_date = (row_start + timedelta(days=1)).date()
    
    if forecast_date < end_date.date():
        val = max_val or mean_val or state
        if val is not None:
            daily_yields[forecast_date] = max(val, daily_yields.get(forecast_date, 0))

print(f"Extracted {len(daily_yields)} historical daily yields for {solcast_entity}.")

# 2. Find closest 5 days to target_kwh
tolerance = max(2.0, target_kwh * 0.15)
candidate_days = [
    (d_date, d_yield) for d_date, d_yield in daily_yields.items()
    if abs(d_yield - target_kwh) <= tolerance
]

if candidate_days:
    candidate_days.sort(key=lambda x: x[0], reverse=True)
    top_5_days = candidate_days[:5]
else:
    sorted_by_error = sorted(daily_yields.items(), key=lambda x: abs(x[1] - target_kwh))
    top_5_days = sorted_by_error[:5]

print(f"\nTop 5 matching days for {target_kwh} kWh:")
for d, y in top_5_days:
    print(f"  {d}: {y:.2f} kWh (Difference: {abs(y - target_kwh):.2f} kWh)")

# 3. Extract 5-minute curves for one of the matching days
if top_5_days:
    sample_day = top_5_days[0][0]
    print(f"\nExtracting curves for {sample_day}...")
    
    day_start_ts = datetime(sample_day.year, sample_day.month, sample_day.day).timestamp()
    day_end_ts = day_start_ts + 86400

    def extract_curve(entity_id):
        meta_id = get_meta_id(entity_id)
        if not meta_id:
            return None
        
        # Try 5-minute stats first
        cursor.execute("""
            SELECT start_ts, mean, state FROM statistics_short_term 
            WHERE metadata_id = ? AND start_ts >= ? AND start_ts < ?
            ORDER BY start_ts ASC
        """, (meta_id, day_start_ts, day_end_ts))
        
        rows = cursor.fetchall()
        curve = [0.0] * 288
        
        for r in rows:
            ts, mean_val, state_val = r
            step = int((ts - day_start_ts) / 300)
            if 0 <= step < 288:
                val = mean_val if mean_val is not None else state_val
                if val is not None:
                    curve[step] = val
                    
        # Forward fill
        current = 0.0
        for i in range(288):
            if curve[i] != 0.0:
                current = curve[i]
            else:
                curve[i] = current
        return curve

    import_curve = extract_curve(import_price_entity)
    export_curve = extract_curve(export_price_entity)
    load_curve = extract_curve(load_entity)
    
    print(f"  Import Price points: {len([x for x in import_curve if x != 0.0]) if import_curve else 0}")
    print(f"  Export Price points: {len([x for x in export_curve if x != 0.0]) if export_curve else 0}")
    print(f"  Load Profile points: {len([x for x in load_curve if x != 0.0]) if load_curve else 0}")

conn.close()
