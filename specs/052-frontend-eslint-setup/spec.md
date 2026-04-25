# Feature: Frontend ESLint Setup (Feature 052)

## Background
The HBC project relies heavily on a Python backend but also serves a robust frontend interface via LitElement Javascript modules in `custom_components/house_battery_control/frontend/`. While the Python backend has strict static analysis (`ruff`) and test coverage (`pytest`), the frontend JS files are completely untested and lack static analysis. This recently led to a syntax error (duplicate variable declaration) being shipped in a beta release, causing a white screen for users. This feature will introduce a formal ESLint toolchain to prevent frontend syntax regressions.

## User Scenarios
1. **As a developer**, when I modify Javascript files in the frontend directory, I want to run a local linter to instantly catch syntax errors, unused variables, and logical flaws before committing.
2. **As a release manager**, when I trigger the release workflow, I want the build to automatically fail if the frontend Javascript contains fatal syntax errors, preventing broken UI modules from reaching users.

## Functional Requirements
1. The repository MUST include a root-level `package.json` defining development dependencies for `eslint`.
2. The project MUST include an ESLint configuration file enforcing ES6 browser standards and allowing LitElement globals (e.g., `customElements`, `html`, `css`).
3. An `npm run lint:js` script MUST be defined to target specifically `custom_components/house_battery_control/frontend/**/*.js`.
4. All existing `.js` files MUST be cleaned to pass the new strict linting rules.
5. The `release.md` workflow MUST be updated to enforce `npm run lint:js` alongside `ruff check`.

## Success Criteria
- Running `npm run lint:js` completes with a `0` exit code.
- Injecting a deliberate syntax error (e.g., `let x = 1; let x = 2;`) into any JS file in the frontend directory causes `npm run lint:js` to fail with a non-zero exit code.
- No frontend files generate runtime white-screen syntax errors upon load.

## Assumptions & Boundaries
- **No Build Step Required**: We will *only* use Node/NPM for linting. The Javascript will still be served as raw static ES6 modules directly by Home Assistant. We are NOT introducing Webpack, Vite, or a transpile step.
- The end-user running Home Assistant will not need Node.js installed.
