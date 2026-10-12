# Implementation Plan: Negative-tariff calculations

Date: 2026-10-12. Status: implemented and verified offline.
Branch: `codex/063-negative-tariff-dispatch`.
Spec: [spec.md](spec.md). Tasks: [tasks.md](tasks.md). Evidence: [validation.md](validation.md).

## Approved scope and process

The user approved implementation, explicitly required Spec Kit tasks followed by SDD/TDD, rejected splitting the solver, and limited the change to calculations. Those decisions supersede the earlier draft's separate-module, actuator, watchdog and HA-integration proposals. Public controller/FSM signatures, calculation consumers and Powerwall mode controls remain unchanged.

Spec Kit's local Antigravity helpers were used with a feature-name override because they do not understand the codex/ branch prefix. The missing constitution and Codex skill discovery are documented in research.md; no force reinitialisation was performed.

## Implemented design

All production edits are in `custom_components/house_battery_control/fsm/lin_fsm.py`.

1. Keep the existing signed discharge variables and SciPy `linprog`/HiGHS entry point. Replace the inequality balance with exact sparse site and battery equations. Solar export is explicit and cannot be curtailed. Bound combined discharge, battery capacity and import/export flows.
2. Prohibit battery export when raw sell <= 0 or effective sell <= 0. Add an independent rejection check in the existing calculation adapter; do not change executor calls or claim enforcement between calculations.
3. Use signed meter cash once. Negative imports earn credits, negative solar exports incur charges. Preserve the existing terminal-inventory policy without the positive epsilon floor. Keep the positive-price acquisition gate by re-solving prohibited intervals rather than editing a solved trajectory.
4. Validate every successful solution against bounds, equalities, inequalities and physical direction rules. Add integer direction restrictions when the relaxation uses opposing flows. Never clip a violating solution into apparent feasibility.
5. Use a 0.1% relative MIP optimality gap and a shared 15-second solve budget. This is a bounded approximate optimum, not a guarantee of exact global optimality. For current negative-price grid charging, require its feasible objective to beat the no-current-grid-charge reference's proven lower bound. Uncertain savings choose the reference. Timeout or invalid results return no forced plan. A genuinely infeasible reference due to reserve/deadline is distinguished from timeout and labelled as a constraint action.
6. Build first target, plan states, inventory and cash from one validated trajectory. Initialise acquisition inventory in stored kWh, include charging efficiency, and remove post-solve charge clipping and SoC patching.
7. Preserve all existing plan fields and add flow diagnostics in kWh. `projected_cost` is actual horizon meter cash, excluding terminal credit and export-margin policy preference. Comparison score and cash savings are distinct fields.

## Verification

Tests preceded production code. Initial RED: 15 failed, 3 passed. Existing offline baseline: 41 passed, 2 expected failures. Additional RED/GREEN cycles covered reference timeout, optimisation-bound uncertainty, independent adapter protection and horizon performance. Final combined run: 71 passed, 2 unchanged expected failures. Lint and diff whitespace checks pass.

Recorded representative desktop timings: 288 steps 3.152 s; 576 steps 8.902 s. These are workload-specific desktop measurements, not a guarantee for every price sequence or deployment machine.

## Boundaries

Price numbers retain their existing input units consistently; no speculative provider/persisted-data migration. Reject non-finite/mismatched/negative-energy inputs. The calculation cannot infer whether an already-padded array is stale, or guarantee realised savings from forecast inputs; source provenance and live control are unchanged by user direction. The CSV replay uses observed tariff values with explicitly synthetic load/PV/SoC, not a reconstruction of measured battery behaviour.

No HA runtime validation, deployment, script changes, branch merge or remote publication was performed.
