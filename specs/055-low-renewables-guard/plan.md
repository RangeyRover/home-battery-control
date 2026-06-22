# Implementation Plan: Low Renewables Guard (055)

## Goal

Implement a proactive battery charging guard that detects low renewable energy penetration from Amber Express forecast data and injects SoC targets into the LP solver at configurable deadlines (05:00, 15:00), preventing high import costs during SA grid price spikes.

## Research Findings

### Solver Target Injection Method

Analysis of [lin_fsm.py L185-200](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/fsm/lin_fsm.py#L185-L200) reveals the cleanest injection: **raise the lower bound** of `bounds[b_off + deadline_step]` from `safe_lb` to `capacity`. This:
- Follows the existing `reserve_kwh` pattern (same loop, same variable)
- Is a single-line change per deadline step
- Lets the solver naturally find the cheapest charge path
- Does NOT require new constraint rows or objective terms

### Renewables Data — Currently Discarded

[rates.py L161](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/rates.py#L161) reads `renewables` from Amber Express but only uses it for price blending. The parsed output (L186-193) does NOT carry the value. Must add `renewables` to `RateInterval` to preserve it.

### Time→Step Mapping Pattern

[coordinator.py L411-437](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/coordinator.py#L411-L437) — the `no_import_steps` resolution iterates `rates_list`, converts each step's UTC start to local time, and checks against configured periods. The guard deadline resolution follows this exact pattern.

### Solver Step Count — Dynamic

`number_step = len(price_buy)` ([lin_fsm.py L121](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/fsm/lin_fsm.py#L121)). When the 48h synthetic horizon is active, N can be 400-576+. Guard deadlines for both today and tomorrow will naturally fall within range.

---

## Proposed Changes

### Component 1: Guard Logic Module

#### [NEW] [renewables_guard.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/renewables_guard.py)

New pure-logic module encapsulating the guard. No HA dependencies — testable in isolation.

```python
@dataclass
class GuardState:
    active: bool
    renewables_avg: float | None     # Current 12h average renewables %
    triggers: list[str]              # ["renewables", "solar"] — which fired
    deadline_steps: list[int] | None # Step indices where b[i] targets capacity

class RenewablesGuard:
    def __init__(self, config: dict):
        self._active = False       # Hysteresis state
        self._config = config

    def evaluate(
        self,
        renewables_timeline: list[float] | None,  # Per-step renewables %
        solcast_tomorrow_kwh: float | None,
    ) -> GuardState:
        """Evaluate triggers, apply hysteresis, return guard state."""

    def resolve_deadline_steps(
        self,
        rates_timeline: list[dict],
        overnight_deadline: time,
        daytime_deadline: time,
    ) -> list[int]:
        """Map configured deadlines to step indices using rates timeline timestamps."""
```

**Key design decisions:**
- `evaluate()` applies the OR/AND trigger mode and hysteresis (activate ≤30%, deactivate only >40%)
- `resolve_deadline_steps()` follows the `no_import_steps` pattern: iterate rates, convert UTC→local, match deadline times
- Returns step indices for BOTH today and tomorrow if 48h data extends that far
- Pure function — takes data in, returns result. No side effects.

---

### Component 2: Rates Pipeline — Preserve Renewables

#### [MODIFY] [rates.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/rates.py)

1. Add `renewables` field to `RateInterval` TypedDict (L11-16)
2. In `_parse_amber_express_entity()` (L186-193): include `renewables` in the parsed dict
3. In `_parse_amber_entity()`: default `renewables` to `None` (standard Amber doesn't provide it)
4. In `_merge_import_export()`: carry `renewables` from import intervals

---

### Component 3: Solver Interface — New Field

#### [MODIFY] [base.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/fsm/base.py)

Add to `SolverInputs` dataclass:
```python
guard_deadline_steps: list[int] | None = None  # Step indices targeting 100% SoC
```

---

### Component 4: LP Solver — Apply Targets

#### [MODIFY] [lin_fsm.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/fsm/lin_fsm.py)

In `propose_state_of_charge()`:
1. Accept `guard_deadline_steps` parameter (from `SolverInputs`)
2. In the battery state bounds loop (L192-200), after computing `safe_lb`:

```python
# Guard deadline: raise lower bound to capacity at target step
if guard_deadline_steps and i in _guard_set:
    bounds[b_off + i] = (capacity, capacity)
else:
    bounds[b_off + i] = (safe_lb, capacity)
```

This is the entire solver change — 3 lines added to the existing bounds loop. The solver naturally finds the cheapest path to fill the battery by each deadline.

In `calculate_next_state()`:
1. Extract `si.guard_deadline_steps` and pass to `propose_state_of_charge()`

---

### Component 5: Coordinator — Orchestration

#### [MODIFY] [coordinator.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/coordinator.py)

In `_async_update_data()`:
1. After `self.rates.update()` — extract renewables timeline from parsed rates
2. Read Solcast tomorrow forecast value
3. Instantiate `RenewablesGuard` with config, call `evaluate()`
4. If active: call `resolve_deadline_steps()` with the extended rates timeline
5. Pass `guard_deadline_steps` into `_build_solver_inputs()`

In `_build_solver_inputs()`:
1. Add `guard_deadline_steps` parameter
2. Include in returned `SolverInputs(...)`

In return data dict (~L693):
1. Add guard state attributes: `renewables_guard_active`, `renewables_avg`, `guard_triggers`

---

### Component 6: Configuration

#### [MODIFY] [const.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/const.py)

Add constants:
```python
CONF_GUARD_RENEWABLES_THRESHOLD = "guard_renewables_threshold"
CONF_GUARD_OVERNIGHT_DEADLINE = "guard_overnight_deadline"
CONF_GUARD_DAYTIME_DEADLINE = "guard_daytime_deadline"
CONF_GUARD_PEAK_SOLAR = "guard_peak_solar"
CONF_GUARD_TRIGGER_MODE = "guard_trigger_mode"
CONF_GUARD_LOW_SOLAR_THRESHOLD = "guard_low_solar_threshold"

DEFAULT_GUARD_RENEWABLES_THRESHOLD = 30.0
DEFAULT_GUARD_OVERNIGHT_DEADLINE = "05:00"
DEFAULT_GUARD_DAYTIME_DEADLINE = "15:00"
DEFAULT_GUARD_PEAK_SOLAR = 40.0
DEFAULT_GUARD_TRIGGER_MODE = "OR"
DEFAULT_GUARD_LOW_SOLAR_THRESHOLD = 50.0
```

#### [MODIFY] [config_flow.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/config_flow.py)

Add guard settings to the `async_step_control()` options step, following the existing `CONF_OBSERVATION_MODE` pattern.

#### [MODIFY] [strings.json](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/strings.json) and [en.json](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/translations/en.json)

Add labels for new config fields.

---

### Component 7: Dashboard

#### [MODIFY] [hbc-dashboard.js](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/frontend/hbc-dashboard.js)

Add guard status badge to the constraints bar:
```javascript
${guardActive ? html`<span class="constraint-badge renewables">
  ⚡ Low Renewables: ${renewablesAvg}% — Targets: ${deadlines}
</span>` : ''}
```

CSS: Orange/amber gradient badge matching the existing `no-import` styling convention.

---

## Verification Plan

### SDD → TDD Approach (Tests BEFORE Code)

> [!IMPORTANT]
> All tests are written and committed BEFORE any production code. The implementation follows red→green→refactor.

### Test Files (written first)

#### [NEW] [test_renewables_guard.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/tests/test_renewables_guard.py)

**Guard evaluation tests:**
- `test_guard_activates_below_threshold` — avg renewables 4.9% → active
- `test_guard_inactive_above_threshold` — avg renewables 65% → inactive
- `test_guard_hysteresis_no_deactivate_at_35` — active, renewables rises to 35% → stays active
- `test_guard_deactivates_above_40` — active, renewables rises to 42% → deactivates
- `test_guard_or_mode_renewables_only` — low renewables + high solar → active (OR mode)
- `test_guard_or_mode_solar_only` — high renewables + low solar → active (OR mode)
- `test_guard_and_mode_both_required` — low renewables + high solar → inactive (AND mode)
- `test_guard_and_mode_both_fire` — low renewables + low solar → active (AND mode)
- `test_guard_no_amber_express_data` — None renewables timeline → inactive (fail-safe)
- `test_guard_empty_renewables` — empty list → inactive

**Deadline resolution tests:**
- `test_resolve_deadlines_today_only` — 24h timeline → finds 05:00 and 15:00 steps
- `test_resolve_deadlines_48h` — 48h timeline → finds 4 steps (today+tomorrow)
- `test_resolve_deadlines_custom_times` — deadline at 04:00 and 14:00 → correct steps
- `test_resolve_deadlines_past_deadline` — if 05:00 has passed, only find tomorrow's

#### Additions to [test_fsm_lin.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/tests/test_fsm_lin.py)

**Solver target injection tests:**
- `test_guard_deadline_raises_battery_lower_bound` — verify `b[deadline_step]` >= capacity
- `test_guard_deadline_solver_charges_cheapest` — cheap overnight prices → solver charges then
- `test_guard_deadline_no_effect_when_none` — `guard_deadline_steps=None` → normal bounds
- `test_guard_deadline_already_full` — battery at 100% → solver doesn't over-charge
- `test_guard_deadline_coexists_with_no_import` — both constraints active simultaneously

#### Additions to [test_rates.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/tests/test_rates.py)

- `test_amber_express_preserves_renewables` — parsed intervals include `renewables` field
- `test_amber_express_renewables_default` — missing field defaults to `None` or `100.0`
- `test_standard_amber_renewables_none` — non-Express intervals have `renewables: None`

### Automated Tests

```bash
pytest tests/test_renewables_guard.py -v
pytest tests/test_fsm_lin.py -v -k "guard"
pytest tests/test_rates.py -v -k "renewables"
pytest tests/ -v  # Full regression
```

### Manual Verification

- Deploy to HA test instance with Amber Express active
- Verify guard badge appears when renewables < 30%
- Verify solver plan shows charging toward 05:00 and 15:00 deadlines
- Verify config flow shows guard settings and changes take effect
