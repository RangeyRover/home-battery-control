# Offline validation

See validation.md for exact RED/GREEN results and offline package bootstrap. Run the new regression suite with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1:

```
py -m pytest tests/test_negative_tariffs.py -q -o addopts=
```

The combined offline suite includes existing test_fsm_lin.py, test_solver_replay.py and the linear export-margin test. Avoid invoking HA integration or the unrelated DP performance test. Benchmark evidence is in benchmark.json. No live deployment is included.


## US4 verification (solve budget and visibility)

Offline:

```
pytest tests/test_solver_budget.py tests/test_negative_tariffs.py tests/test_sensor.py tests/test_web.py tests/test_config_flow.py -q
pytest tests/ -q
ruff check custom_components/ tests/
npm run lint:js
```

Manual in Home Assistant (after installing the beta):

1. Open the HBC panel → Dashboard. A "Solver" card shows last solve time, budget, passes, a green/amber/red outcome chip and the 24 h max. "Plan last ran" shows a timestamp, not "—".
2. Settings → Devices → House Battery Control: diagnostic sensor "Solver solve time" exists; its history graph updates each cycle.
3. Options → Energy & Metrics: "Solver time budget (seconds)" field present, default 30.
4. Temporarily set the budget to 1 s on a negative-price period: a red "Solver budget reached — safe plan used" badge appears, the plan table remains populated, and the log contains the FR-18 warning. Restore the budget afterwards.
