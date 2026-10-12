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
