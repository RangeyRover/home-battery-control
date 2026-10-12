# Offline validation

See validation.md for exact RED/GREEN results and offline package bootstrap. Run the new regression suite with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1:

```
py -m pytest tests/test_negative_tariffs.py -q -o addopts=
```

The combined offline suite includes existing test_fsm_lin.py, test_solver_replay.py and the linear export-margin test. Avoid invoking HA integration or the unrelated DP performance test. Benchmark evidence is in benchmark.json. No live deployment is included.
