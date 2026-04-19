import os
import sqlite3
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta
import zoneinfo
import homeassistant.util.dt as dt_util
import sys

# Add custom components to path so we can import rates_predictor
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from custom_components.house_battery_control.rates_predictor import SyntheticRatesPredictor

# We need a mock HomeAssistant and MockEngine similar to tests
from unittest.mock import MagicMock

class MockResult:
    def __init__(self, rows):
        self._rows = rows
    def fetchall(self):
        return self._rows
    def fetchone(self):
        return self._rows[0] if self._rows else None

class MockConnection:
    def __init__(self, sqlite_conn):
        self.sqlite_conn = sqlite_conn

    def execute(self, stmt, params=None):
        cur = self.sqlite_conn.cursor()
        query = stmt.text if hasattr(stmt, "text") else str(stmt)
        if params is None:
            params = {}
        cur.execute(query, params)
        return MockResult(cur.fetchall())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

class MockEngine:
    def __init__(self, sqlite_conn):
        self.sqlite_conn = sqlite_conn

    def connect(self):
        return MockConnection(self.sqlite_conn)

DB_PATH = os.path.abspath("tests/test_data/home-assistant_v2.db")
output_dir = r"C:\Users\markn\.gemini\antigravity\brain\7d170da6-7325-4e43-8a72-923da1173bea\scratch"
os.makedirs(output_dir, exist_ok=True)

def generate_graphs():
    dt_util.set_default_time_zone(zoneinfo.ZoneInfo("Australia/Adelaide"))
    conn = sqlite3.connect(DB_PATH)
    hass = MagicMock()
    
    import custom_components.house_battery_control.rates_predictor as rp
    rp.get_instance = lambda h: MagicMock(engine=MockEngine(conn))
    # Mock history to return empty states dict so it falls back to LTS query which is what the test DB has
    rp.history.get_significant_states = lambda hass, start, end, entity_ids=None: {}

    predictor = SyntheticRatesPredictor(
        hass,
        solcast_entity_id="sensor.solcast_pv_forecast_forecast_tomorrow",
        import_price_entity_id="sensor.4_rosella_general_price",
        export_price_entity_id="sensor.4_rosella_feed_in_price",
        load_entity_id="sensor.powerwall_2_load_power"
    )

    targets = [28, 26, 24, 22, 20, 18, 16, 14]
    
    # We want 288 steps on X axis (from 0:00 to 23:55)
    time_labels = [f"{h:02d}:{m:02d}" for h in range(24) for m in range(0, 60, 5)]
    x_ticks = np.arange(0, 288, 24) # Every 2 hours
    x_ticklabels = [time_labels[i] for i in x_ticks]

    for target in targets:
        analog_days = predictor._run_analog_search(target)
        
        syn_import = predictor._average_curves(analog_days, "pricing_curve")
        syn_export = predictor._average_curves(analog_days, "export_curve")
        syn_load = predictor._average_curves(analog_days, "load_curve")
        
        # Plot
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
        
        fig.suptitle(f"Synthetic Outlook - Target PV Yield: {target} kWh\nDays selected: {[d.date.strftime('%Y-%m-%d') for d in analog_days]}", fontsize=14)
        
        # Pricing Subplot
        ax1.plot(syn_import, label='Import Price (c/kWh)', color='red')
        ax1.plot(syn_export, label='Export Price (c/kWh)', color='green')
        ax1.set_ylabel('Price (c/kWh)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.set_title("Synthesized Pricing Curves (288-step array)")
        
        # Load Subplot
        ax2.plot(syn_load, label='Load Profile (kW)', color='blue')
        ax2.set_ylabel('Load (kW)')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        ax2.set_title("Synthesized Load Curve (288-step array)")
        
        plt.xticks(x_ticks, x_ticklabels, rotation=45)
        plt.xlabel("Time of Day")
        plt.tight_layout()
        
        save_path = os.path.join(output_dir, f"sweep_{target}.png")
        plt.savefig(save_path, dpi=150)
        plt.close(fig)
        print(f"Generated {save_path}")

    conn.close()

if __name__ == "__main__":
    generate_graphs()
