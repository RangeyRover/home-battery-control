import sqlite3
import datetime
import json

db_path = r"C:\Users\markn\Downloads\home-assistant_v2.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def get_meta(entity_id):
    cursor.execute("SELECT id, statistic_id, source, unit_of_measurement, has_mean, has_sum FROM statistics_meta WHERE statistic_id = ?", (entity_id,))
    return cursor.fetchone()

def print_stats(entity_id):
    print(f"\n--- Analyzing {entity_id} ---")
    meta = get_meta(entity_id)
    if not meta:
        print(f"NOT FOUND in statistics_meta!")
        # Let's search for similar names
        cursor.execute("SELECT statistic_id FROM statistics_meta WHERE statistic_id LIKE ?", (f"%{entity_id.split('.')[-1]}%",))
        similar = cursor.fetchall()
        if similar:
            print(f"Similar entities found: {[s[0] for s in similar]}")
        return
        
    meta_id, stat_id, source, unit, has_mean, has_sum = meta
    print(f"Meta ID: {meta_id} | Source: {source} | Unit: {unit} | has_mean: {has_mean} | has_sum: {has_sum}")
    
    # Check Long Term Statistics (Hourly)
    cursor.execute("SELECT COUNT(*), MIN(start_ts), MAX(start_ts) FROM statistics WHERE metadata_id = ?", (meta_id,))
    lts_count, lts_min, lts_max = cursor.fetchone()
    if lts_count:
        min_date = datetime.datetime.fromtimestamp(lts_min) if lts_min else None
        max_date = datetime.datetime.fromtimestamp(lts_max) if lts_max else None
        print(f"LTS (Hourly) Count: {lts_count} | Range: {min_date} to {max_date}")
        
        # Check an actual row
        cursor.execute("SELECT state, sum, mean, max, min FROM statistics WHERE metadata_id = ? ORDER BY start_ts DESC LIMIT 1", (meta_id,))
        row = cursor.fetchone()
        print(f"Sample LTS Row (state, sum, mean, max, min): {row}")
    else:
        print("LTS (Hourly): NO DATA")
        
    # Check Short Term Statistics (5-min)
    cursor.execute("SELECT COUNT(*), MIN(start_ts), MAX(start_ts) FROM statistics_short_term WHERE metadata_id = ?", (meta_id,))
    sts_count, sts_min, sts_max = cursor.fetchone()
    if sts_count:
        min_date = datetime.datetime.fromtimestamp(sts_min) if sts_min else None
        max_date = datetime.datetime.fromtimestamp(sts_max) if sts_max else None
        print(f"STS (5-min) Count: {sts_count} | Range: {min_date} to {max_date}")
        
        # Check an actual row
        cursor.execute("SELECT state, sum, mean, max, min FROM statistics_short_term WHERE metadata_id = ? ORDER BY start_ts DESC LIMIT 1", (meta_id,))
        row = cursor.fetchone()
        print(f"Sample STS Row (state, sum, mean, max, min): {row}")
    else:
        print("STS (5-min): NO DATA")

entities_to_check = [
    "sensor.solcast_pv_forecast_forecast_tomorrow",
    "sensor.solcast_pv_forecast_tomorrow",
    "sensor.powerwall_2_solar_generated",
    "sensor.4_rosella_feed_in_price",
    "sensor.4_rosella_general_price",
    "sensor.powerwall_2_load_export"
]

for e in entities_to_check:
    print_stats(e)
    
conn.close()
