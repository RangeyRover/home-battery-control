# Implementation Tasks: Server-Side Plan Matrix Aggregation

- `[x]` **T001**: Modify `custom_components/house_battery_control/coordinator.py` to add `resolution` argument to `_build_plan_matrix` and implement the 30-min chunking algorithm if `resolution == "30min"`.
- `[x]` **T002**: Modify `custom_components/house_battery_control/web.py` to parse the `resolution` query parameter in `HBCApiPlanView.get` and pass it to `_build_plan_matrix`.
- `[x]` **T003**: Modify `custom_components/house_battery_control/frontend/hbc-plan-table-lite.js` to append `?resolution=` to the fetch URL.
- `[x]` **T004**: Refactor `_switchResolution` in `hbc-plan-table-lite.js` to trigger a new backend fetch.
- `[x]` **T005**: Remove local 30-min chunking logic from `hbc-plan-table-lite.js` `render()` function.
- `[x]` **T006**: Update `tests/test_web.py` to verify that `?resolution=30min` returns a chunked matrix and `?resolution=5min` returns the full matrix.
