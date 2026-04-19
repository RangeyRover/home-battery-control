# Implementation Plan: 039-frontend-testing

**Branch**: `039-frontend-testing` | **Date**: 2026-04-19 | **Spec**: [specs/039-frontend-testing/spec.md](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/specs/039-frontend-testing/spec.md)
**Input**: Feature specification from `/specs/039-frontend-testing/spec.md`

## Summary

This plan outlines the implementation of a rigorous JavaScript testing stack (`@web/test-runner` + `@open-wc/testing`) to apply Test-Driven Development against the newly modularized LitElement frontend components (`hbc-dashboard`, `hbc-sensors`, `hbc-plan-table`). Furthermore, it mandates integrating these reverse-engineered component behaviors directly into the persistent `system_requirements.md`.

## Technical Context

**Language/Version**: JavaScript (ES6+), Node.js v18+  
**Primary Dependencies**: `@web/test-runner`, `@open-wc/testing`, `mocha`, `chai`  
**Storage**: N/A (Mocked `localStorage` used in tests)  
**Testing**: `@web/test-runner` executing headless browser tests  
**Target Platform**: Browser (Web Components)  
**Project Type**: Single project (adding JS testing to an existing Python/HA integration)  
**Performance Goals**: Test suite executes in under 10 seconds.  
**Constraints**: Must not break existing Python `pytest` backend tests.  
**Scale/Scope**: 3 core LitElement Web Components.

## Constitution Check

*GATE: Passed*
- The plan adheres strictly to the requirement of documenting system behavior before coding.
- The plan aligns with the project's goal of ensuring high reliability and testing coverage.

## Project Structure

### Documentation (this feature)

```text
specs/039-frontend-testing/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (to be generated)
```

### Source Code (repository root)

```text
# Single project (DEFAULT)
custom_components/house_battery_control/
├── frontend/
│   ├── hbc-dashboard.js
│   ├── hbc-sensors.js
│   └── hbc-plan-table.js

tests/
├── js/
│   ├── hbc-dashboard.test.js
│   ├── hbc-sensors.test.js
│   └── hbc-plan-table.test.js

package.json
web-test-runner.config.js
system_requirements.md
```

**Structure Decision**: The frontend code remains untouched in `custom_components/house_battery_control/frontend/`. The test suite will be isolated in `tests/js/` to cleanly separate it from the Python backend test suite (`tests/`). A `package.json` and a `web-test-runner.config.js` will be created in the repository root to facilitate test execution.

## Complexity Tracking

No violations. The setup is the industry standard for testing Lit web components.
