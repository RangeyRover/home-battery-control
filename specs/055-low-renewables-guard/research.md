# Research: Low Renewables Guard (055)

## Decision Log

### D1: Target Injection Method

**Decision**: Raise the lower bound of `bounds[b_off + deadline_step]` to `capacity`.

**Rationale**: This is the simplest possible change (one conditional in the existing bounds loop at `lin_fsm.py:192-200`). It follows the same pattern as `reserve_kwh` (which already sets the lower bound). The solver naturally finds the cheapest charging path to meet the raised floor. No new constraint rows, no objective function changes, no re-solve logic.

**Alternatives considered**:
- Equality constraint row (`a_eq` addition) — over-constrains the problem and adds matrix complexity
- Objective function penalty — doesn't guarantee the target is met, harder to reason about
- Hard constraint with fallback re-solve — overengineered, user rejected

### D2: Data Source for Renewables %

**Decision**: Use Amber Express `renewables` field from existing forecast data (Path B).

**Rationale**: Zero new dependencies. The data is already flowing through `rates.py` at L161 but being discarded after price blending. We just need to preserve it.

**Alternatives considered**:
- AEMO NEM scraping (Path A) — stronger signal but requires new HTTP infrastructure, daily scheduling, external dependency. Deferred to future enhancement.

### D3: Guard Module Architecture

**Decision**: New standalone `renewables_guard.py` module with pure functions.

**Rationale**: Keeps the coordinator from growing further (strangler pattern principle). The guard logic is self-contained, stateless (except hysteresis flag), and testable in complete isolation without HA mocking.

**Alternatives considered**:
- Embed in coordinator — violates strangler pattern, adds complexity to already-large coordinator
- Embed in lin_fsm.py — mixes detection logic with solver logic

### D4: Hysteresis Implementation

**Decision**: Instance-level `self._active` flag on `RenewablesGuard`. Activate at ≤30%, deactivate only above 40%.

**Rationale**: Simplest stateful implementation. The coordinator instantiates `RenewablesGuard` once and reuses it across cycles, preserving the hysteresis state.

### D5: Trigger Mode

**Decision**: OR as default (either renewables OR solar triggers the guard independently). Configurable to AND.

**Rationale**: User explicitly requested this — OR is the aggressive defensive posture for spike protection. AND reduces false positives if the user finds OR too sensitive.

## Key File References

| File | What | Lines |
|------|------|-------|
| `rates.py` | Renewables read + discard | L161, L186-193 |
| `rates.py` | `RateInterval` TypedDict | L11-16 |
| `coordinator.py` | `_build_solver_inputs()` | L355-445 |
| `coordinator.py` | `no_import_steps` resolution pattern | L411-437 |
| `coordinator.py` | Return data dict | L693 |
| `base.py` | `SolverInputs` dataclass | L6-13 |
| `lin_fsm.py` | Battery state bounds loop | L192-200 |
| `lin_fsm.py` | Variable offsets | L135-142 |
| `lin_fsm.py` | `propose_state_of_charge()` signature | L84 |
| `const.py` | Config constants pattern | L1-83 |
| `config_flow.py` | Control step options | L560-643 |
| `rates_predictor.py` | Solcast state reading | L53-62 |
| `hbc-dashboard.js` | Badge rendering | L167-172, L380-401 |
