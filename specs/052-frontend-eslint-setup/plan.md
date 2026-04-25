# Implementation Plan: Frontend ESLint Setup

## Technical Context
We are introducing ESLint static analysis to the HA custom component `frontend` Javascript files. 
- **Language**: Javascript (ES6)
- **Framework**: LitElement / Native Web Components
- **Target**: `custom_components/house_battery_control/frontend/*.js`
- **Toolchain**: `package.json` with `eslint` and `eslint-plugin-lit`.

## Constitution Check
- **Compliance**: This adheres to robust integration practices by implementing strict static analysis to prevent regressions. It does not introduce any compiled/transpiled frontend pipelines that violate HA ecosystem simplicity (HA continues to serve raw ES6).

## Proposed Implementation

### 1. Root Setup
- **`package.json`**: Initialize at the project root with exactly two devDependencies: `eslint` and `eslint-plugin-lit`. Add an `npm run lint:js` script.
- **`eslint.config.js`** (or `.eslintrc.json` depending on ESLint version):
  - Environment: `browser: true`, `es2021: true`
  - Extends: `eslint:recommended`, `plugin:lit/recommended`
  - Globals: `customElements`, `html`, `css` (if imported directly, though Lit provides them usually).
  - Rules: Prevent duplicate variables, unused vars, undefined variables.

### 2. File Cleaning
- Run the linter over the 8 JS files in the `frontend` folder.
- Fix all warnings/errors.
- *Anticipated Issues*: Implicit global variables, `let` redeclarations, missing trailing commas or unused imports.

### 3. Release Pipeline Update
- Modify `.agent/workflows/release.md` Step 4 to run `npm run lint:js` alongside `ruff check`.
- This creates an ironclad pre-release gate for JS files.

## Verification
- Linter must pass successfully.
- Inject a deliberate syntax error and confirm that `npm run lint:js` fails with exit code 1.
