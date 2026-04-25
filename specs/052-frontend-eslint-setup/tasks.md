# Implementation Tasks: Frontend ESLint Setup

- `[x]` **T001**: Initialize `package.json` at root with `eslint` and `eslint-plugin-lit` dependencies, and a `lint:js` script.
- `[x]` **T002**: Create `eslint.config.js` (or `.eslintrc.json`) configured for ES6 Browser environment, allowing LitElement globals.
- `[x]` **T003**: Run `npm install` to setup the environment.
- `[x]` **T004**: Run the linter over `custom_components/house_battery_control/frontend/*.js` and fix any identified code quality issues (e.g., unused variables, implicit globals, etc.).
- `[x]` **T005**: Inject a deliberate error in a frontend script, ensure `npm run lint:js` fails, then revert it.
- `[x]` **T006**: Update `.agent/workflows/release.md` to make `npm run lint:js` a mandatory step prior to cutting a release tag.
