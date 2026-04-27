# Tasks

- `[x]` **T001**: Add `CONF_ROUND_TRIP_EFFICIENCY` and `CONF_EXPORT_MARGIN` constants with defaults to `const.py`.
- `[x]` **T002**: Update `config_flow.py` to expose the new configuration levers in `async_step_energy`.
- `[x]` **T003**: Update `lin_fsm.py` to extract `export_margin` and apply it to the `sell_opp` grid discharge calculation.
- `[x]` **T004**: Update `dp_fsm.py` to extract `export_margin` and apply it to the DP reward matrix for grid exports.
- `[x]` **T005**: Add unit tests validating that the FSM respects the `export_margin`.
- `[x]` **T006**: Run `pytest tests/ -v`, `ruff check`, and `npm run lint:js`. to verify zero regressions.
