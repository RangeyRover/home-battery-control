import sqlite3
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import os

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
target_kwh = 24.0

print(f"Target PV Yield: {target_kwh} kWh")

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

print("\nTop 5 Matching Days:")
for d, y in top_5_days:
    print(f"  {d}: {y:.2f} kWh (Difference: {abs(y - target_kwh):.2f} kWh)")

# 3. Extract curves for all 5 days
def get_lts_curve(entity_id, day_start_ts):
    meta_id = get_meta_id(entity_id)
    if not meta_id: return [0.0]*288
    
    day_end_ts = day_start_ts + 86400
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
                for m in range(12):
                    curve[hour_idx * 12 + m] = float(val)
                    
    current = 0.0
    for i in range(288):
        if curve[i] != 0.0: current = curve[i]
        else: curve[i] = current
    return curve

def average_curves(curves):
    if not curves: return [0.0] * 288
    num_curves = len(curves)
    return [sum(points) / num_curves for points in zip(*curves)]

all_import_curves = []
all_export_curves = []
all_load_curves = []

for d, _ in top_5_days:
    day_start_ts = datetime(d.year, d.month, d.day).timestamp()
    all_import_curves.append(get_lts_curve(import_price_entity, day_start_ts))
    all_export_curves.append(get_lts_curve(export_price_entity, day_start_ts))
    all_load_curves.append(get_lts_curve(load_entity, day_start_ts))

synthetic_import = average_curves(all_import_curves)
synthetic_export = average_curves(all_export_curves)
synthetic_load = average_curves(all_load_curves)

print("\nSynthesis complete.")

# Generate plot
fig, ax1 = plt.subplots(figsize=(12, 6))

time_axis = [f"{str(i//12).zfill(2)}:{str((i%12)*5).zfill(2)}" for i in range(288)]

ax1.set_xlabel('Time of Day')
ax1.set_ylabel('Price ($/kWh)', color='tab:red')
ax1.plot(time_axis, synthetic_import, color='tab:red', linewidth=2, label='Import Price (Avg)')
ax1.plot(time_axis, synthetic_export, color='tab:orange', linewidth=2, linestyle='--', label='Export Price (Avg)')
ax1.tick_params(axis='y', labelcolor='tab:red')
# Sparse x-ticks
ax1.set_xticks(range(0, 288, 24))

ax2 = ax1.twinx()
ax2.set_ylabel('Load Power (kW)', color='tab:blue')
ax2.plot(time_axis, synthetic_load, color='tab:blue', linewidth=2, label='Load Profile (Avg)')
ax2.tick_params(axis='y', labelcolor='tab:blue')

# Legends
lines_1, labels_1 = ax1.get_legend_handles_labels()
lines_2, labels_2 = ax2.get_legend_handles_labels()
ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left')

title_days = ", ".join([str(d[0]) for d in top_5_days])
plt.title(f"Synthesized Forecast for 24kWh PV\n(Averaged from: {title_days})")
fig.tight_layout()

# Save directly to the artifacts directory
artifact_dir = r"C:\Users\markn\.gemini\antigravity\brain\80951761-3793-4eb4-8fc7-f40923457f58\artifacts"
os.makedirs(artifact_dir, exist_ok=True)
plot_path = os.path.join(artifact_dir, "synthetic_forecast_proof.png")
plt.savefig(plot_path)
print(f"Saved plot to: {plot_path}")

conn.close()
