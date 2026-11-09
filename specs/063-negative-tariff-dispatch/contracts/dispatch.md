# Existing calculation interface

No new API or dispatch contract. Preserve LinearBatteryController.propose_state_of_charge and LinearBatteryStateMachine.calculate_next_state signatures and return shape. The controller returns first target fraction, projected meter cash and future-plan rows. The adapter returns the existing FSMResult fields and rejects a contradictory nonpositive-price battery-export recommendation with an empty plan and SELF_CONSUMPTION.

Existing plan fields remain. Add grid_import_kwh, grid_export_kwh, charge_kwh, discharge_kwh, battery_export_kwh, solar_export_kwh and grid_charge_kwh. Negative-price charge comparisons may add charge_comparison_saving, charge_comparison_cash_saving or charge_reason for reserve/deadline action. No executor, script payload, mode behaviour, expiry or live-recheck changes.


## US4 & US5 contract additions (2026-10-12 / 2026-11-09)

Non-breaking additions only; existing signatures and return shapes are unchanged.

- `LinearBatteryController.time_budget_s: float` (attribute, default 30.0). `propose_state_of_charge` signature unchanged.
- `LinearBatteryController.guard_target_soc: float` (attribute, default 100.0).
- `LinearBatteryController.last_solve_stats: dict` (attribute) — SolverStats, set on every return path.
- `FSMResult.solver_stats: dict | None = None` — new optional dataclass field; populated by `LinearBatteryStateMachine`, `None` for other FSMs.
- Adapter reads `context.config["solver_time_budget"]` (default 30.0, clamped 1–60) and `context.config.get("guard_target_soc", 100.0)`.

### Telemetry API (`GET /hbc/api/telemetry`) — added keys

```json
{
  "last_update": "2026-10-12T11:05:00+00:00",
  "solver_stats": {
    "solve_seconds": 1.243, "budget_seconds": 30.0, "passes": 2,
    "integer_used": false, "reference_solve": false,
    "outcome": "optimal", "detail": "", "horizon_steps": 426
  },
  "solve_seconds_max_24h": 3.104,
  "observation_mode": false,
  "no_import_periods": "",
  "renewables_guard_active": false,
  "renewables_avg": null,
  "guard_triggers": []
}
```

Missing/older payloads must render safely (dashboard treats absent `solver_stats` as "—").

### Sensor

`sensor` with unique_id `hbc_solve_time`: state = `solve_seconds` (s, DURATION, MEASUREMENT, DIAGNOSTIC); attributes = remaining SolverStats fields + `solve_seconds_max_24h`.
