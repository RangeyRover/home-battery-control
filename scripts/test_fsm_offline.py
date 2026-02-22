import json
import os
import sys
from datetime import datetime, timedelta, timezone

# Add the project root to the python path so we can import House Battery Control components
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from custom_components.house_battery_control.fsm.base import FSMContext
from custom_components.house_battery_control.fsm.default import DefaultBatteryStateMachine

def load_json(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)

def construct_mock_rates(start_midnight: datetime):
    """
    Build 24h worth of mock rates. 288 x 5 min slots.
    Base Rate: 11c
    Morning Peak (7am-9am): 20c
    Evening Peak (5pm-9pm): 35c
    """
    rates = []
    current = start_midnight
    for _ in range(288):
        h = current.hour
        price = 11.0 # 11 cents base
        if 17 <= h < 21:
            price = 35.0  # Evening Peak
        elif 7 <= h < 9:
            price = 20.0  # Morning Peak
            
        rate = {
            "start": current,
            "end": current + timedelta(minutes=5),
            "import_price": price,
            "export_price": round(price * 0.8, 2)
        }
        rates.append(rate)
        current += timedelta(minutes=5)
    return rates

def construct_mock_solar(start_midnight: datetime):
    """
    Build 24h solar curve. Peaks at midday (4kW), zero before 07:00 and after 18:00.
    """
    solar = []
    current = start_midnight
    for _ in range(288):
        h = current.hour
        m = current.minute
        time_decimal = h + (m / 60.0)
        
        kw = 0.0
        if 7.0 <= time_decimal <= 18.0:
            # Simple parabolic curve peaking at 12.5 (12:30 PM) -> max 4kW
            # normalized: max is when t=12.5, min is t=7 or t=18 (dist 5.5)
            # kw = 4.0 * (1 - ((time_decimal - 12.5) / 5.5)**2)
            # Cap at 0 to prevent negative solar
            dist = abs(time_decimal - 12.5)
            if dist < 5.5:
                kw = 4.0 * (1 - (dist / 5.5)**2)
                
        kw = max(0.0, kw)
                
        solar.append({
            "start": current,
            "end": current + timedelta(minutes=5),
            "kw": round(kw, 2)
        })
        current += timedelta(minutes=5)
    return solar

def get_forecast_from(index, data_list):
    """Return the remaining tail of the list for forecasting."""
    return data_list[index:]

def main():
    print("========================================")
    print(" FSM Independent Validation Framework")
    print("========================================\\n")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    forecast_path = os.path.join(base_dir, "average_24hr_forecast.json")
    
    if not os.path.exists(forecast_path):
        print(f"Error: Could not find {forecast_path}")
        sys.exit(1)
        
    raw_loads = load_json(forecast_path)
    if len(raw_loads) != 288:
        print(f"Warning: Expected 288 load slots, found {len(raw_loads)}.")
        
    start_time = datetime(2025, 2, 22, 0, 0, tzinfo=timezone.utc)
    
    # 1. Structure Inputs
    rates = construct_mock_rates(start_time)
    solar = construct_mock_solar(start_time)
    
    # Structure Load array (convert avg_kwh to kW (* 12) )
    loads = []
    current = start_time
    for item in raw_loads:
        loads.append({
            "start": current,
            "end": current + timedelta(minutes=5),
            "kw": round(item["avg_kwh_usage"] * 12.0, 2)
        })
        current += timedelta(minutes=5)
        
    # 2. Setup FSM
    fsm = DefaultBatteryStateMachine()
    
    # Physics Tracking
    soc = 20.0  # Start day emptyish
    capacity_kwh = 13.5 # Standard Powerwall
    
    # 3. Execution Ticks
    print(f"{'Time':<6} | {'Price':<6} | {'Load':<5} | {'PV':<5} | {'FSM State':<15} | {'Limit(kW)':<10} | {'SoC':<5}")
    print("-" * 70)
    
    current_time = start_time
    for i in range(288):
        # Current status
        current_price = rates[i]["import_price"]
        current_load = loads[i]["kw"]
        current_pv = solar[i]["kw"]
        
        # Forecast data available at this instant (the rest of the day)
        f_rates = get_forecast_from(i, rates)
        f_load = get_forecast_from(i, loads)
        f_solar = get_forecast_from(i, solar)
        
        ctx = FSMContext(
            soc=soc,
            solar_production=current_pv,
            load_power=current_load,
            grid_voltage=240.0,
            current_price=current_price,
            forecast_solar=f_solar,
            forecast_load=f_load,
            forecast_price=f_rates,
            config={}
        )
        
        # Determine State
        result = fsm.calculate_next_state(ctx)
        
        # Output Row formatting
        t_str = current_time.strftime("%H:%M")
        state_str = result.state
        lim_str = f"{result.limit_kw:.1f}"
        
        # Simulation Step (5 minutes = 1/12 hour)
        sim_battery_kw = 0.0
        if state_str == "CHARGE_GRID" or state_str == "CHARGE_SOLAR":
            sim_battery_kw = result.limit_kw # positive into battery
        elif state_str == "DISCHARGE_HOME":
            sim_battery_kw = -result.limit_kw # negative out of battery
            
        kwh_diff = sim_battery_kw * (1.0 / 12.0)
        soc_delta = (kwh_diff / capacity_kwh) * 100.0
        
        # Prevent physical impossibility
        next_soc = max(0.0, min(100.0, soc + soc_delta))
        
        print(f"{t_str:<6} | {current_price:<6.1f} | {current_load:<5.2f} | {current_pv:<5.2f} | {state_str:<15} | {lim_str:<10} | {soc:>5.1f}%")
        
        # Advance clock
        soc = next_soc
        current_time += timedelta(minutes=5)

if __name__ == "__main__":
    main()
