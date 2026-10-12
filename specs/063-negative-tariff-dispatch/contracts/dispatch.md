# Existing calculation interface

No new API or dispatch contract. Preserve LinearBatteryController.propose_state_of_charge and LinearBatteryStateMachine.calculate_next_state signatures and return shape. The controller returns first target fraction, projected meter cash and future-plan rows. The adapter returns the existing FSMResult fields and rejects a contradictory nonpositive-price battery-export recommendation with an empty plan and SELF_CONSUMPTION.

Existing plan fields remain. Add grid_import_kwh, grid_export_kwh, charge_kwh, discharge_kwh, battery_export_kwh, solar_export_kwh and grid_charge_kwh. Negative-price charge comparisons may add charge_comparison_saving, charge_comparison_cash_saving or charge_reason for reserve/deadline action. No executor, script payload, mode behaviour, expiry or live-recheck changes.
