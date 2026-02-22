import asyncio
from datetime import datetime, timedelta
import zoneinfo
import json
import os

from custom_components.house_battery_control.load import LoadPredictor

class DummyCoordinator:
    def __init__(self):
        self.fsm = None
    
    # Copy the method logic directly
    def _build_diagnostic_plan_table(self, rates, solar_forecast, load_forecast, weather, current_soc, current_state):
        from custom_components.house_battery_control.fsm.base import FSMContext
        from homeassistant.util import dt as dt_util

        # Pre-parse Load
        parsed_loads = []
        for lf in load_forecast:
            if not isinstance(lf, dict):
                continue
            start_str = lf.get("start", "")
            if not start_str:
                continue
            st = dt_util.parse_datetime(start_str) if isinstance(start_str, str) else start_str
            if st:
                parsed_loads.append({"start": st, "kw": float(lf.get("kw", 0.0))})

        table = []
        simulated_soc = current_soc

        for rate in rates:
            start = rate["start"]
            end = rate.get("end", start)

            # --- 2. Load Interpolation (The Fixed Version) ---
            matched_loads = []
            for lf in parsed_loads:
                lf_start = lf["start"]
                lf_end = lf_start + timedelta(minutes=5)
                # Overlap detection
                if lf_start < end and lf_end > start:
                    matched_loads.append(lf["kw"])
            
            # Fallback to nearest neighbor if no strict geometric overlap
            if not matched_loads and parsed_loads:
                 closest = min(parsed_loads, key=lambda l: abs((start - l["start"]).total_seconds()))
                 matched_loads.append(closest["kw"])

            load_kw_avg = sum(matched_loads) / len(matched_loads) if matched_loads else 0.0
            
            # To compare against the Old Version:
            old_matched_loads = [lf["kw"] for lf in parsed_loads if start <= lf["start"] < end]
            old_load_kw_avg = sum(old_matched_loads) / len(old_matched_loads) if old_matched_loads else 0.0

            table.append({
                "Time": start,
                "Old Load Forecast": f"{old_load_kw_avg:.2f}",
                "New Load Forecast": f"{load_kw_avg:.2f}",
            })

        return table

async def main():
    adelaide_tz = zoneinfo.ZoneInfo("Australia/Adelaide")
    
    # We will offset the starting time by 2 minutes to simulate real world jitter
    # (where the HA clock ticking the FSM doesn't exactly match the 00:00:00 boundary of the forecast)
    fsm_start_time = datetime(2025, 2, 22, 0, 2, 0, tzinfo=adelaide_tz)
    
    # The load predictor starts exactly at midnight
    predictor_start_time = datetime(2025, 2, 22, 0, 0, 0, tzinfo=adelaide_tz)
    
    # 1. Get raw load forecast
    class MockState:
        def __init__(self):
            self.attributes = {"unit_of_measurement": "kWh"}
    
    class MockStates:
        def get(self, entity_id):
            return MockState()
            
    class MockHass:
        def __init__(self):
            self.states = MockStates()
            
    predictor = LoadPredictor(MockHass())
    predictor.testing_bypass_history = True
    base_dir = os.path.dirname(os.path.abspath(__file__))
    history_path = os.path.join(base_dir, "tests", "load_history.json")
    
    if not os.path.exists(history_path):
        # try root just in case
        history_path = os.path.join(base_dir, "load_history.json")
        
    with open(history_path, "r") as f:
        predictor.last_history_raw = json.load(f)
        
    print("Generating load forecast from predictor...")
    load_forecast = await predictor.async_predict(
        start_time=predictor_start_time,
        temp_forecast=[], 
        load_entity_id="sensor.powerwall_2_home_usage",
        max_load_kw=10.0
    )
    
    # Print the very first item so we can see what the array keys are exactly 
    print("\\nSample LoadPredictor Payload:")
    print(load_forecast[0])

    # 2. Build mock rates to drive the table
    # 5 min intervals for 24h, starting at fsm_start_time (00:02:00)
    rates = []
    current = fsm_start_time
    for _ in range(24): # just check first 2 hours
        rates.append({
            "start": current,
            "end": current + timedelta(minutes=5),
            "import_price": 10.0,
            "export_price": 10.0
        })
        current += timedelta(minutes=5)
        
    # 3. Build diagnostic table
    print("\\nGenerating plan table...")
    dummy = DummyCoordinator()
    plan_table = dummy._build_diagnostic_plan_table(
        rates=rates,
        solar_forecast=[],
        load_forecast=load_forecast,
        weather=[],
        current_soc=50.0,
        current_state="IDLE"
    )
    
    print("\\nComparing Array Mapping Behavior \\n(FSM Time is offset by +2 minutes from Predictor Time):")
    print(f"{'FSM Time':<25} | {'Old Logic (UI Issue)':<20} | {'New Logic (Plan)':<20}")
    print("-" * 75)
    
    for pt in plan_table:
        print(f"{str(pt['Time']):<25} | {pt['Old Load Forecast']:<20} | {pt['New Load Forecast']:<20}")

if __name__ == "__main__":
    asyncio.run(main())
