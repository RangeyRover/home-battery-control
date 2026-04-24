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

import_price_entity = "sensor.4_rosella_general_price"
load_entity = "sensor.powerwall_2_load_power"
# We will use March 25th 2026 as the mock analog day
sample_day = datetime(2026, 3, 25)
day_start_ts = sample_day.timestamp()
day_end_ts = day_start_ts + 86400

def get_lts_curve(entity_id):
    meta_id = get_meta_id(entity_id)
    if not meta_id: return [0.0]*288
    
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

import_curve = get_lts_curve(import_price_entity)
load_curve = get_lts_curve(load_entity)

# Generate plot
fig, ax1 = plt.subplots(figsize=(10, 5))

time_axis = [f"{str(i//12).zfill(2)}:{str((i%12)*5).zfill(2)}" for i in range(288)]

color = 'tab:red'
ax1.set_xlabel('Time of Day (March 25th)')
ax1.set_ylabel('Import Price ($/kWh)', color=color)
ax1.plot(time_axis, import_curve, color=color, linewidth=2, drawstyle='steps-post')
ax1.tick_params(axis='y', labelcolor=color)
# Sparse x-ticks
ax1.set_xticks(range(0, 288, 24))

ax2 = ax1.twinx()
color = 'tab:blue'
ax2.set_ylabel('Load Power (kW)', color=color)
ax2.plot(time_axis, load_curve, color=color, linewidth=2, drawstyle='steps-post', alpha=0.7)
ax2.tick_params(axis='y', labelcolor=color)

fig.tight_layout()
plt.title("Step-Interpolated Analog Curves from Hourly LTS")

# Save directly to the artifacts directory using the absolute path we know
artifact_dir = r"C:\Users\markn\.gemini\antigravity\brain\80951761-3793-4eb4-8fc7-f40923457f58\artifacts"
os.makedirs(artifact_dir, exist_ok=True)
plot_path = os.path.join(artifact_dir, "analog_curve_proof.png")
plt.savefig(plot_path)
print(f"Saved plot to: {plot_path}")

conn.close()
