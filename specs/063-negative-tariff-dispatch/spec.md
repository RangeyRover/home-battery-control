# Feature 063: Negative-tariff calculations

Date: 2026-10-12. Status: approved calculation-only scope, implemented offline.

## User decisions

Solar cannot be curtailed. Never deliberately recommend battery export at zero or negative effective prices. Paid charging may cause additional later negative-price solar export ONLY when the whole forecast sequence saves money. Preserve lin_fsm.py and its public interface; no solver split, import switch, Powerwall mode-control or HA integration changes. Use Spec Kit task decomposition and tests before code.

## User stories and requirements

### US1 (P1): Valid flows and protected battery export

FR-01: Exact site/battery energy conservation, finite physical limits, no fictitious imports or simultaneous opposing battery/meter flows.
FR-02: Battery export requires raw sell > 0 and sell > nonnegative margin in optimisation and independently in the calculation adapter. Acquisition credits never override this.
FR-03: Solar serves load and remaining solar is charged or exported; full/rate-limited batteries can export unavoidable solar without invented curtailment.

### US2 (P1): Paid charging includes displaced solar

FR-04: Count signed meter import/export cash once, include losses in dynamics, and keep terminal inventory/export-margin policy separate from cash.
FR-05: Current negative-price grid charging must beat the same-horizon reference without current grid charging, with identical future policy. Include later solar-export penalties. Require improvement beyond numerical tolerance; economic ties and uncertified improvements choose no current charging.
FR-06: Historical acquisition cost remains inventory accounting and the existing positive-export policy; never treat a past credit as a new cash reward. Preserve input units rather than migrating unverified provider data.

### US3 (P1): Consistent output and safe failure

FR-07: First target, state, limits and plan use one validated trajectory. No post-solve flow clipping or patched SoC. Preserve interface signatures and mode-control behaviour.
FR-08: Reject non-finite/unequal-length inputs, negative load/PV, invalid efficiency/capacity and invalid successful solver results.
FR-09: Preserve reserve, no-import and full-charge deadline constraints. Re-solve acquisition-policy restrictions. A comparison timeout cannot be treated as a mandated deadline action.
FR-10: Bound total solve time and reject unsuccessful/invalid results. Permit a documented small optimality gap only with physically valid solutions; use the reference dual bound to avoid asserting uncertain charging savings.
FR-11: Retain truthful flow/cash diagnostics and label reserve/deadline charging when the reference is infeasible. Source staleness cannot be inferred from bare arrays; do not claim realised savings or a full historical replay.

## Acceptance

- Buy -15, sell -20, negative acquisition cost: no battery-export recommendation.
- One kWh space, one kWh later surplus solar, sell -30 cents: reject a 10-cent charge credit; accept a 40-cent credit, yielding 10 cents net benefit at equal terminal energy.
- Paid charging with spare space remains available.
- Full battery and surplus PV: solar export remains feasible without battery export.
- Negative import with only 0.125 kWh demand and no charging: import only 0.125 kWh.
- Every raw/reported row conserves energy and cash; charge/discharge and import/export are mutually exclusive.
- Fault-injected negative-export recommendation is rejected at the calculation adapter.
- Existing offline solver/replay behaviour remains covered.

## Evidence limitations

The supplied history(2).csv contains import forecast, feed-in price and an export counter. It does not contain measured load/PV/SoC or commanded states. The fixture records source timestamps and backward-as-of price alignment; synthetic physical scenarios are explicitly labelled. User excluded HA integration testing and actuator changes.

---

## Amendment 2026-10-12 / 2026-11-09 — US4 (Solve-time budget & visibility) and US5 (Spike pre-charge to 80% by 16:00)

### User decisions

1. **Non-destructive solver boundary (`lin_fsm.py`)**: `lin_fsm.py` is the core asset and must not be endangered. Do NOT add a second "safe LP" fallback solver inside `lin_fsm.py`. Only replace the literal `15.0` s limit with `self.time_budget_s` (default 30 s, configurable 1–60 s), add read-only counters (`passes`, `integer_used`, `reference_solve`), and support an optional `self.guard_target_soc` attribute (default `100.0`) on the existing deadline lower-bound loop. All existing solver trajectories on commit `ed19ee5` must remain identical under default settings.
2. **Spike / High-Volatility Pre-Charge (US5)**: When Amber forecasts a price spike (`spike_status in ("potential_spike", "spike")` or `descriptor == "spike"`) within the next 12 hours, trigger the guard to top up to **80% SoC by 16:00** (when daytime cheap tariffs end and costs start to rise), without forcing 100% or locking the battery overnight until 05:00.

### US4 (P1): Bounded, observable solving (non-destructive)

As the owner, I can see on the dashboard how long the last plan took to calculate, how many passes ran, and whether it completed or timed out.

- FR-12: Every calculation records `solve_seconds`, `budget_seconds`, `passes`, `integer_used`, `reference_solve`, `horizon_steps`, `outcome` (`"optimal"` | `"timeout"` | `"no_plan"`), and `detail`.
- FR-13: Total calculation time is capped by a user-configurable budget (default 30 s, permitted 1–60 s). The 15 s hard-coded budget is removed.
- FR-14: On timeout or invalid/infeasible inputs, preserve `lin_fsm.py`'s existing safe behaviour (empty plan → `SELF_CONSUMPTION`) and flag `outcome = "timeout"` or `"no_plan"` on the dashboard.
- FR-15: The dashboard shows a Solver card with last solve time, budget, pass count, colour-coded outcome chip (green `< min(5 s, 0.5 × budget)`, amber slower optimal, red `timeout`/`no_plan`), and 24 h max, plus a constraints-bar badge when non-optimal and a real "Plan last ran" timestamp on the production panel.
- FR-16: A diagnostic sensor (`hbc_solve_time`) exposes the last solve time in seconds with the remaining stats as attributes.
- FR-17: `solver_time_budget` is editable in initial setup and Options → Energy & Metrics, with labels and descriptions in `strings.json` and `translations/en.json` (plus labels for `reserve_soc`, `round_trip_efficiency`, `export_margin`).
- FR-18: A warning is logged when a solve uses >= 80 % of the budget or returns a non-optimal outcome.

### US5 (P1): Amber spike / volatility pre-charge (80% by 16:00)

As the owner, when Amber predicts a price spike in the upcoming 12 hours, HBC tops the battery up to 80% SoC by 16:00 (before evening costs rise) without forced charging during expensive shoulder periods or locking the battery until 05:00 tomorrow.

- FR-19: `RatesManager` (`_parse_entity` and `_parse_amber_express_entity`) preserves a boolean `spike` flag on each 5-minute interval, set `True` when `spike_status in ("potential_spike", "spike")` or `descriptor == "spike"`.
- FR-20: `RenewablesGuard.evaluate` checks the next 12 hours (up to 144 steps) for any interval with `spike == True`. If present, the guard activates (`spike_triggered = True`, reason `"Amber Spike Forecast"`) independently of the `AND`/`OR` low-renewables/Solcast gate.
- FR-21: Default daytime guard deadline (`DEFAULT_GUARD_DAYTIME_DEADLINE`) is `"16:00"`. When the guard is active *only* due to a spike (low-renewables/Solcast gate not triggered), only the daytime deadline (`16:00` default) is resolved — not the `05:00` overnight deadline — and `guard_target_soc` is set to `80.0` (80% SoC). When the low-renewables/Solcast gate triggers, existing behaviour (both deadlines, 100% target SoC) is preserved.
- FR-22: `LinearBatteryController` applies `target_cap = capacity * (getattr(self, "guard_target_soc", 100.0) / 100.0)` in the existing `guard_deadline_steps` bound calculation, defaulting to `100.0` so all existing callers and tests remain unchanged.

### US4 & US5 acceptance

- Snapshot invariance test proves `LinearBatteryController.propose_state_of_charge` returns identical trajectories before and after the US4/US5 edits across positive, negative, inverted, reserve, deadline, and no-import cases.
- Patched `monotonic` exhausting the budget returns an empty plan with `outcome == "timeout"` (`passes >= 1`) and `SELF_CONSUMPTION` in the adapter.
- Invalid inputs return `outcome == "no_plan"` and `passes == 0`.
- When a rate interval within 12 hours has `spike_status == "spike"` or `descriptor == "spike"`, `RenewablesGuard` activates even in `"AND"` mode with high renewables/solar, resolves only the daytime deadline (`16:00`), and caps the deadline lower bound at `80%` of capacity.
- Production dashboard renders Solver card, outcome chip, 24 h max, and "Plan last ran" timestamp from `/hbc/api/telemetry`; `hbc_solve_time` sensor and `solver_time_budget` config option exist with translations.
