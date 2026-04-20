# Tasks: Fix Timezone Offset in Synthetic Array Integration

- [x] Modify `coordinator.py` temporal lookup loop for `tod_idx` to use `dt_util.as_local(current)` instead of `current`.
- [x] Add `from homeassistant.util import dt as dt_util` to the appropriate scope if not already imported.
- [x] Ensure that `test_coordinator.py` tests pass after the change.
- [x] Run test suite (`pytest tests/`) to ensure no regressions.
- [x] Provide user with plan of action to test via HACS release (`v1.6.0-beta.20`).
