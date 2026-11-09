# Research and decisions

## Approved scope amendment — 2026-10-12

The user approved implementation, then explicitly limited it to calculation changes and required Spec Kit task decomposition followed by SDD/TDD (tests before code). Powerwall mode scripts, executor behaviour, service payloads and command lifecycle remain unchanged. Script capability certification, rate control, watchdogs and new dispatch plumbing are excluded from this feature. Earlier wording requiring those changes is superseded by this amendment. First-state protection belongs in the calculation adapter, using its current price input; this does not claim continuous live enforcement between updates.

Economic policy remains: never recommend deliberate battery export at a nonpositive effective price; allow additional later negative-price solar export when the whole forecast sequence saves money. Forecasts are estimates, not a guarantee of actuator power or realised savings. Existing input price units are retained consistently; no speculative migration of stored accounting values.


## Exact model

Decision: use SciPy MILP with direction/mode binaries and equality balances.
Rationale: current grid balance inequality admits 0.65 kWh import for 0.125 kWh load without charging; negative prices reward the unused slack. Equality alone does not exclude simultaneous charging/discharging or net importing/exporting.
Alternative rejected: coefficient-only patch. It fixes one symptom but leaves impossible energy flows and post-solve inconsistency.
Primary API source: https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html (read 2026-10-12). SciPy supports bounded integer variables and a solve time limit. Compatibility with the repository minimum and deployed hardware remains a verification task.

## Economic policy

Decision: permit extra later negative-price solar export if the complete executable sequence saves money; forbid direct battery export at nonpositive effective prices.
Rationale: user explicitly selected this trade-off on 2026-10-12. Compare with no grid charging in the current command interval and retain future optimisation freedom.
Alternative rejected: lexicographic minimum negative solar spill or rigid reserved headroom. Those would reject profitable sequences the user explicitly allows.

## Existing defects relevant to replacement

- Positive dg coefficient floor at lin_fsm.py:174 reverses the intended incentive at negative sell prices.
- Spill penalty at line 184 already penalises negative solar export correctly; replace with exact meter cash, not a blindly sign-reversed coefficient.
- Acquisition gate at line 328 is missing a nonpositive-price prohibition, not an arithmetic sign inversion.
- Initial running_capacity is an SoC fraction at line 273 but later represents kWh.
- Headroom uses end-of-step B at line 289 and then clips C without reconstructing B.
- Current grid/discharge formulation and post-solve edits do not guarantee a physically consistent reported plan.
- execute.py sends entity_id only; limit_kw is not transmitted.
- context_builder.py pads prices/load/PV and has no trustworthy coverage contract; coordinator also contains a builder path that must remain consistent.

## Incident evidence

The user's CSV supports negative-tariff export timing, not battery attribution. Prior controlled solver experiments reproduced DISCHARGE_GRID with 27 kWh capacity, full initial SoC, 6.3 kW charge, 10 kW discharge, 1.5 kW load, 4.8 kW PV, buy -0.15, sell -0.20, acquisition -0.25 and 24 five-minute intervals. These are synthetic assumptions, not measured incident battery conditions. Preserve them as regression inputs during implementation.

## Actuation and forecast uncertainty

Decision: validate executable script modes and bounded command lifetime before enabling discretionary actions. Missing knowledge means safe fallback, not guessed fractional control.
Alternative rejected: applying an ideal continuous plan and hoping the next poll corrects it. It can consume the headroom the economics relied on.

## Spec Kit discovery

Observed: `.agent/skills/speckit.plan/SKILL.md` is installed for Antigravity; its frontmatter name uses a dot. `.agents/skills` and `.specify/memory/constitution.md` are absent. `.agents/rules/speckit.md` exists, but is not a discoverable skill manifest. `$speckit-plan` is not in this session's available-skill catalog.

OpenAI's repository skill examples use `.agents/skills/`: https://developers.openai.com/blog/skills-agents-sdk (read 2026-10-12). This explains the directory mismatch. The local helper scripts also expect `.specify` templates and numbered branch names, so blindly copying manifests would not fully repair their workflow.

Proposed separate repair: expose validated Codex-compatible skills under `.agents/skills`, align names with intended invocation, correct template/script paths and codex-prefixed feature resolution, and validate discovery in a fresh session. Do not overwrite this repo's Antigravity installation or run a force initialisation as part of the battery plan.


---

## US4 research — solve-time budget, safe fallback, visibility (2026-10-12 evening)

### R-01 Budget value and configurability
Decision: configurable `solver_time_budget`, default 30 s, range 1–60 s, step 1 s. Exposed in initial Energy step and Options → Energy & Metrics.
Rationale: user decision at plan review: "I see no reason for such a low budget, make it 30 s, then at that point I would worry about performance." 30 s is 10 % of the 5-minute cycle; HA's DataUpdateCoordinator serialises refreshes, so a long solve delays but never overlaps the next one. Desktop measurements (3.2 s/288 steps, 8.9 s/576 steps through the full integer path) sit well inside it, so the fallback should only trigger on pathological inputs or very slow hosts. Normal "a few seconds" behaviour is made visible by the dashboard colour rule (data-model) rather than by a tight budget. 1 s minimum allows deliberate fallback testing; 60 s maximum caps executor-thread occupancy.
Alternatives: 5 s default (rejected by user — too low); constant only (rejected — no way to adapt on a slow host without a code change).
Status: confirmed by user 2026-10-12.

### R-02 Where the budget is enforced
Decision: keep the existing `monotonic()` start in `propose_state_of_charge`; replace the literal `15.0` with the controller attribute `time_budget_s` (set by the adapter from config, clamped 1–60). Pass `time_limit` to every HiGHS call as the remaining time minus a fallback reserve.
Rationale: preserves the public `propose_state_of_charge` signature (063 contract) — the adapter sets an attribute rather than adding a parameter. HiGHS honours `time_limit` for both LP and MIP.
Alternative: new keyword argument (acceptable, backward compatible) — rejected only to keep the 063 contract literally unchanged.

### R-03 Non-destructive timeout behaviour (replaces earlier safe-LP fallback proposal)
Decision: do NOT add a fallback reserve or a second "safe LP" solver inside `lin_fsm.py`. When `remaining = self.time_budget_s - (monotonic() - started) <= 0` or HiGHS times out, preserve `lin_fsm.py`'s existing return (`None` → `fallback = (battery.current_charge, 0.0, [])`) and classify the outcome as `"timeout"` in `last_solve_stats`.
Rationale: user explicitly prioritized keeping `lin_fsm.py` non-destructive ("lin_fsm is the key piece of code here, endangering that is a no"). With a 30 s budget against 1–9 s solves, a fallback LP inside `lin_fsm.py` would add invasive branching that rarely executes.

### R-04 Amber spike pre-charge (80% SoC by 16:00)
Finding: Live HA inspection on 2026-11-09 showed an AEMO evening spike (`19:00–19:30`, `spot_per_kwh = $10.74/kWh`, `spike_status = "spike"`, `descriptor = "spike"`). Because Amber Express `advanced_price_predicted` smooths `per_kwh` to `$0.59/$0.27` and `RenewablesGuard` only checks the 12-hour mean renewables (`88.2%` vs `5%` threshold in `AND` mode), HBC did not top up for the spike. Furthermore, forcing 100% right at 19:00 would force charging during the expensive 16:00–19:00 ramp, while forcing 05:00 tomorrow morning to 100% locks the battery overnight and prevents evening export.
Decision:
1. `RatesManager` records `"spike": interval.get("spike_status") in ("potential_spike", "spike") or interval.get("descriptor") == "spike"` on each rate interval.
2. `RenewablesGuard.evaluate` checks the next 12 hours (`rates[:144]`) for any `r.get("spike") is True`. If found, it activates (`self.spike_triggered = True`, reason `"Amber Spike Forecast"`), independent of the `AND`/`OR` low-renewables/Solcast gate.
3. `DEFAULT_GUARD_DAYTIME_DEADLINE` is updated to `"16:00"`. When active *only* via `spike_triggered` (`not low_energy_triggered`), the coordinator resolves only `[guard_daytime_deadline]` (`"16:00"` default, skipping `"05:00"`) and passes `guard_target_soc = 80.0` to the FSM.
4. `LinearBatteryController` uses `target_cap = capacity * (getattr(self, "guard_target_soc", 100.0) / 100.0)` in the existing `guard_deadline_steps` loop (one-line change, default `100.0`).

### R-05 Statistics transport
Decision: controller stores `last_solve_stats` (dict) after every call, including early-exit paths. Adapter copies it into a new optional `FSMResult.solver_stats: dict | None = None` field. Coordinator adds it to `data`, the debug snapshot and the telemetry payload, and keeps a 24 h deque of `(timestamp, solve_seconds)` to compute `solve_seconds_max_24h`.
Rationale: optional dataclass field is backward compatible for all FSMResult constructors and tests. Telemetry payload is what the production panel actually renders.

### R-06 Production panel data path (discovered gap)
Finding: the registered production panel is `hbc-panel-lite.js` (`__init__.py`, `?v=56`). It renders `hbc-dashboard` from `/hbc/api/telemetry`, whose payload (`_build_telemetry_payload`) omits `last_update`, `observation_mode`, `no_import_periods` and guard fields. Consequently "Plan last ran" shows "—" and constraint badges never appear on the production panel.
Decision: add `last_update`, `solver_stats`, `solve_seconds_max_24h` and the four constraint-badge fields to the telemetry payload (small, required for FR-15 to be visible). The zero "24-Hour Forecast Summary" on the lite panel (needs `plan`) is a separate known issue, out of scope.

### R-07 Front-end cache busting
Decision: bump `?v=56` → `?v=57` for both panel registrations in `__init__.py` whenever dashboard JS changes; static path is registered without cache headers so the relative `hbc-dashboard.js` import refreshes with the page.

### R-08 Sensor naming
Finding: no `entity` translations exist in `strings.json`/`en.json`; existing sensors rely on `translation_key` without strings.
Decision: new `HBCSolveTimeSensor` (`unique_id`/`translation_key` `hbc_solve_time`, device class DURATION, unit seconds, state class MEASUREMENT, entity category DIAGNOSTIC) plus an `entity.sensor.hbc_solve_time.name` translation ("Solver solve time"). Existing sensors untouched.

### R-09 Adjacent config gap (optional)
Finding: `reserve_soc`, `round_trip_efficiency` and `export_margin` have no labels in either energy step of `strings.json`/`en.json` (UI shows raw keys). Optional low-risk fix in the same step as the new budget field.
