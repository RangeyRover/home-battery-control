# Tasks: Amber Express Forecast Attribute Resilience

**Input**: Design documents from `/specs/062-amber-express-forecast-keys/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

## Phase 1: Setup (Shared Infrastructure)

- No setup tasks required for this feature.

---

## Phase 2: Foundational (Blocking Prerequisites)

- No foundational tasks required.

---

## Phase 3: User Story 1 - Amber Express Forecast Keys Resilience (Priority: P1)

**Goal**: Amber Express sensor state parsing checks all candidate forecast attribute keys (`detailedForecast`, `detailed_forecast`, `forecasts`, `forecast`, `future_prices`, `variable_intervals`) and supports calculating `end_time` from `duration` when `end_time` is missing.

**Independent Test**: Run unit tests in `tests/test_rates.py` covering all candidate attribute key names and missing `end_time` with `duration`.

### Tests for User Story 1 (TDD)

- [x] T001 [US1] Write unit tests in `tests/test_rates.py` verifying Amber Express parsing with `detailedForecast` (camelCase), `detailed_forecast` (snake_case), and missing `end_time` with `duration`.

### Implementation for User Story 1

- [x] T002 [US1] Update `_parse_amber_express_entity` in `custom_components/house_battery_control/rates.py` to iterate candidate attribute keys and handle missing `end_time` with `duration`.

**Checkpoint**: User Story 1 is fully implemented and tested.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [x] T003 Run `pytest tests/test_rates.py -v` to ensure 100% test pass rate.
