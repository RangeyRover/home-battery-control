# SDD/TDD execution evidence

## Initial state

Branch: codex/063-negative-tariff-dispatch. Production files unchanged at task decomposition. User approved calculation-only implementation with tests before code.

Local speckit.tasks prerequisites passed using SPECIFY_FEATURE override because the Antigravity helper assumes unprefixed numbered branches. Constitution remains absent. Scope amendments precede tasks and production edits.

## Blast radius

Existing LinearBatteryController/LinearBatteryStateMachine are consumed by coordinator.py, test_fsm_lin.py, test_export_margin.py, test_solver_replay.py and test_lazy_import.py. context_builder.py uses only parsing helpers from lin_fsm.py. Risk: HIGH. User explicitly rejected a split. Make in-place changes in lin_fsm.py with unchanged imports, class names and method signatures; the user instruction overrides the skill splitting rule. No execute.py modification.

## Baseline

An initial unisolated pytest test_execute.py run stalled after one test and was interrupted. This is not a passed baseline and is not evidence of a controller failure. Repeat with unrelated auto-loaded plugins disabled before interpreting results.

## Evidence ledger

Pending: baseline, RED, GREEN, compatibility and performance results. Record exact commands and meaningful failure assertions here as tasks execute.

## Pre-edit gates

Offline baseline: test_fsm_lin.py + test_solver_replay.py, 41 passed and 2 expected failures (3.91 s), with package-only import bootstrap and plugin autoload disabled. No HA runtime used.

RED: tests/test_negative_tariffs.py, 15 failed and 3 passed (3.74 s). Includes prohibited battery export, paid-charge/spill decision, invalid inputs and invalid successful results. Full output: red-tests.txt. Production source unchanged at this point.

User explicitly excluded HA integration verification. Keep offline execution and replay as acceptance evidence.

## Completed results

- Initial new-suite RED: 15 failed, 3 passed, before lin_fsm.py edits.
- First GREEN: 18 passed.
- Added reference-timeout regression: 1 failed/22 passed, corrected to 23 passed.
- Added historical tariff scenarios: 26 passed.
- Representative-day performance regression initially failed the 15-second budget. Selective integer constraints alone did not resolve it. A 0.1% MIP gap plus conservative reference dual-bound comparison resolved it without relaxing physical validation.
- Added uncertainty-bound regression: RED before comparison-bound change; GREEN afterward.
- Independent adapter protection: RED before guard; GREEN afterward.
- Final combined offline run: **71 passed, 2 xfailed**, 23.97 seconds. The two expected failures existed in the baseline. No HA integration execution.
- Lint: `py -m ruff check --no-cache custom_components/house_battery_control/fsm/lin_fsm.py tests/test_negative_tariffs.py` passed.
- Physical fixtures: all tariff signs, full/empty batteries, loss accounting, cash comparison, reserve/no-import, invalid inputs/results, timeout, tie, spare capacity, 24 observed-price samples with synthetic energy, 288-step horizon.
- Benchmarks: benchmark.json records 288 steps / 3.152 seconds and 576 steps / 8.902 seconds, complete valid plans.
- Runtime source diff confined to lin_fsm.py. No coordinator, execute.py, base interface, script or consumer import change; no new solver module.

## Reproduce the combined offline suite

Set `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. In Python, register a package-only module named `custom_components.house_battery_control` with `__path__` set to the repository's corresponding directory. This skips the package's HA bootstrap but imports the real calculation files. Then run pytest with:

```
tests/test_fsm_lin.py tests/test_solver_replay.py tests/test_negative_tariffs.py tests/test_export_margin.py::test_export_margin_blocks_lin_export -q -o addopts=
```

The new suite alone is directly runnable with plugin autoload disabled:

```
py -m pytest tests/test_negative_tariffs.py -q -o addopts=
```

The local Python launcher prints a path warning and pyreadline emits a shutdown error after the pytest summary. Pytest completed with the above passing outcomes; these environment messages also appeared before source edits. No claim of HA/deployment verification is made.
