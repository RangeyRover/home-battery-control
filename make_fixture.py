import json

with open(r'API Data\hbc_status_2026-03-08T03-16-57-981Z.json') as f:
    d = json.load(f)

plan = d.get('plan', [])
rates = d.get('rates', [])

fixture = {
    "soc": d.get("soc"),
    "capacity": d.get("capacity"),
    "charge_rate_max": d.get("charge_rate_max"),
    "inverter_limit": d.get("inverter_limit"),
    "acquisition_cost": d.get("acquisition_cost", 0.09),
    "current_price": d.get("current_price"),
    "no_import_periods": d.get("no_import_periods", ""),
    "rates": rates[:len(plan)],  # match length to plan
    "load_kw": [float(row["Load Forecast"]) for row in plan],
    "pv_kw": [float(row["PV Forecast"]) for row in plan],
    "soc_forecast": [float(row["SoC Forecast"].replace('%','')) for row in plan],
    "states": [row["FSM State"] for row in plan],
    "net_grid": [float(row["Net Grid"]) for row in plan]
}

with open(r'tests\fixtures\solver_replay_20260308_bug034.json', 'w') as f:
    json.dump(fixture, f, indent=2)

print("Created fixture tests\fixtures\\solver_replay_20260308_bug034.json")
