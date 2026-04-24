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
load_entity = "sensor.powerwall_2_load_power"
target_kwh = 20.0

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

print(f"Historical Solcast days extracted: {len(daily_yields)}")

candidate_days = [
    (d_date, d_yield) for d_date, d_yield in daily_yields.items()
    if abs(d_yield - target_kwh) <= max(2.0, target_kwh * 0.15)
]

candidate_days.sort(key=lambda x: x[0], reverse=True)
top_5_days = candidate_days[:5]

print(f"\nTop 5 analog days for {target_kwh} kWh:")
for d, y in top_5_days: print(f"  {d}: {y:.2f} kWh")

if top_5_days:
    sample_day = top_5_days[0][0]
    print(f"\nMocking Curve Extraction for {sample_day} using HOURLY LTS -> 288 point array")
    
    day_start_ts = datetime(sample_day.year, sample_day.month, sample_day.day).timestamp()
    day_end_ts = day_start_ts + 86400

    def get_lts_curve(entity_id):
        meta_id = get_meta_id(entity_id)
        if not meta_id: return None
        
        cursor.execute("""
            SELECT start_ts, mean, state, max FROM statistics 
            WHERE metadata_id = ? AND start_ts >= ? AND start_ts < ?
            ORDER BY start_ts ASC
        """, (meta_id, day_start_ts, day_end_ts))
        
        curve = [0.0] * 288
        for ts, mean_val, state_val, max_val in cursor.fetchall():
            hour_idx = int((ts - day_start_ts) / 3600)
            if 0 <= hour_idx < 24:
                val = mean_val if mean_val is not None else (state_val if state_val is not None else max_val)
                if val is not None:
                    # Step interpolation: fill 12 slots for this hour
                    for m in range(12):
                        curve[hour_idx * 12 + m] = val
                        
        # Forward fill
        current = 0.0
        for i in range(288):
            if curve[i] != 0.0:
                current = curve[i]
            else:
                curve[i] = current
        return curve

    import_curve = get_lts_curve(import_price_entity)
    export_curve = get_lts_curve(export_price_entity)
    load_curve = get_lts_curve(load_entity)
    
    print(f"\nResults for {sample_day}:")
    print(f"Import Price: {len([x for x in import_curve if x != 0.0]) if import_curve else 0} non-zero points.")
    print(f"Export Price: {len([x for x in export_curve if x != 0.0]) if export_curve else 0} non-zero points.")
    print(f"Load Curve:   {len([x for x in load_curve if x != 0.0]) if load_curve else 0} non-zero points.")

conn.close()
