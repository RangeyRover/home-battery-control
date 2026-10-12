# Tasks: Negative-tariff calculations

Approved scope: calculation only. No executor, script, command lifetime or service payload changes. SDD/TDD required by user on 2026-10-12.

## Phase 1 — Setup

- [x] T001 Record approval and calculation-only scope in specs/063-negative-tariff-dispatch/spec.md and plan.md.
- [x] T002 Run local Spec Kit prerequisite checks and trace solver consumers; record blast radius in specs/063-negative-tariff-dispatch/validation.md.
- [x] T003 Establish existing solver-test baseline and record results in specs/063-negative-tariff-dispatch/validation.md.

## Phase 2 — Foundation

- [x] T004 Write permanent failing regression tests for exact balances and tariff policy against the existing controller in tests/test_negative_tariffs.py; capture RED before production edits.
- [x] T005 Record in-place compatibility boundary and compatibility contract in docs/architecture.md before implementing custom_components/house_battery_control/fsm/lin_fsm.py.

## Phase 3 — US1 (P1): Physically valid flows and no negative battery export

Independent acceptance: all tariff sign combinations, full battery and surplus PV conserve energy, respect limits and never recommend prohibited battery export; unavoidable solar export remains feasible.

- [x] T006 [US1] Implement exact sparse MILP, direction constraints, input checks and independent solution validation in custom_components/house_battery_control/fsm/lin_fsm.py after T004 is RED.
- [x] T007 [US1] Run tests/test_negative_tariffs.py physical/policy cases against the corrected controller, record GREEN and check positive-price/export-margin compatibility.

## Phase 4 — US2 (P1): Paid charging includes future solar-export cost

Independent acceptance: equal-terminal two-step cases reject a 10-cent credit causing 30-cent spill and accept a 40-cent credit causing the same spill; retain valid paid charging with spare capacity.

- [x] T008 [US2] Add and run failing hand-calculated candidate/reference, tie and loss tests in tests/test_negative_tariffs.py before comparison implementation.
- [x] T009 [US2] Implement same-horizon candidate/reference economics, truthful cash/terminal diagnostics and tie preference in custom_components/house_battery_control/fsm/lin_fsm.py.
- [x] T010 [US2] Run economic regressions, reconcile cash independently and record GREEN in specs/063-negative-tariff-dispatch/validation.md.

## Phase 5 — US3 (P1): Consistent calculation output and safe fallback

Independent acceptance: first target matches first plan row, every row obeys battery dynamics, invalid/infeasible/timed-out results return no forced action, live row-zero tariff cannot yield prohibited export.

- [x] T011 [US3] Write and run adapter, malformed result, reserve, deadline and timeout regressions; record missing-behaviour failures in tests/test_negative_tariffs.py before implementing the adapter.
- [x] T012 [US3] Implement FSM-compatible adapter and trajectory-derived accounting in custom_components/house_battery_control/fsm/lin_fsm.py; preserve existing mode command interface.
- [x] T013 [US3] Verify unchanged calculation imports in custom_components/house_battery_control/coordinator.py and preserve the existing controller/FSM signatures in custom_components/house_battery_control/fsm/lin_fsm.py.
- [x] T014 [US3] Verify offline tests/test_fsm_lin.py and tests/test_solver_replay.py; check unchanged imports and verify execute.py has no diff. HA integration tests excluded by user direction.

## Phase 6 — Cross-cutting verification

- [x] T015 Verify finite/equal-length/nonnegative solver inputs in tests/test_negative_tariffs.py; document that source staleness and padded-forecast provenance remain outside the calculation-only boundary; make no metadata/API changes.
- [x] T016 Run focused regressions and representative 288/576-step benchmarks; record failures and timings in specs/063-negative-tariff-dispatch/validation.md.
- [x] T017 Reconcile approved scope, architecture, completed tasks and remaining deployment limitations in specs/063-negative-tariff-dispatch/plan.md and docs/architecture.md.

## Dependencies and execution rules

T001–T005 precede production edits. US1 precedes US2 and US3. Within each story: RED test evidence, implementation, GREEN evidence, then compatibility checks. T013 depends on T007, T010 and T012. T014–T017 follow integration. T015 preserves input-builder interfaces and records the limit of calculation-only validation.

Permanent tests serve as the skill's reproduction scripts and are retained. Do not mark a test task complete on collection/import failure: RED must demonstrate the expected missing behaviour. Do not weaken assertions to preserve a known bug. Separate unrelated existing failures from regressions with a baseline.

Parallel opportunities: after US1, independent review of US2 economic fixtures and US3 adapter fixtures can occur in separate files; implementation touching lin_fsm.py remains serial. No agent delegation is required.

MVP is US1, but this approved implementation includes all three stories. There are 17 tasks: 5 setup/foundation, 2 US1, 3 US2, 4 US3 and 3 cross-cutting. Work stops at a documented failed gate, not at an unsupported completion claim.
