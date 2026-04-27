# Implementation Plan: Export Margin and Round Trip Efficiency Levers

## Architecture Changes
- **Configuration Flow**: Extends `config_flow.py` and `const.py` to persist `CONF_ROUND_TRIP_EFFICIENCY` and `CONF_EXPORT_MARGIN`.
- **Coordinator Context**: Extends the FSM context in `coordinator.py` to extract and pass `export_margin` to the solver. (Note: `round_trip_efficiency` is already passed to the FSM context).
- **Solver Objective Function**: Modifies `lin_fsm.py` and `dp_fsm.py` to mathematically penalize grid exports by subtracting `export_margin` from `price_sell`.

## File Modifications

1. `custom_components/house_battery_control/const.py`
   - Define `CONF_ROUND_TRIP_EFFICIENCY` and `CONF_EXPORT_MARGIN`.
   - Set defaults (`0.90` and `0.000` respectively).

2. `custom_components/house_battery_control/config_flow.py`
   - Inject `vol.Optional(CONF_ROUND_TRIP_EFFICIENCY)` and `vol.Optional(CONF_EXPORT_MARGIN)` into `async_step_energy` for both `ConfigFlow` and `HBCOptionsFlowHandler`.
   - Use `NumberSelector` for both.

3. `custom_components/house_battery_control/fsm/lin_fsm.py`
   - Extract `export_margin = float(context.config.get("export_margin", 0.0))`.
   - Update `sell_opp = max(0.001, price_sell[i] - export_margin)`.

4. `custom_components/house_battery_control/fsm/dp_fsm.py`
   - Apply similar mathematical margin subtraction when calculating the reward matrix for grid exports.

## Testing Strategy
- Modify `tests/test_dp.py` or create a new dedicated unit test to verify that the solvers correctly refuse to export when `price_sell < acquisition_cost + export_margin`.
- Run the full test suite (`pytest`) to ensure `config_flow.py` changes do not break legacy configuration loading.
