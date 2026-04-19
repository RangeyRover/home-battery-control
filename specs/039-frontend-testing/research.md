# Phase 0: Research

## Frontend Testing Framework
**Decision**: Use `@web/test-runner` with `@open-wc/testing` and `mocha`/`chai`.
**Rationale**: This is the official testing stack recommended by the Lit team. It runs tests in a real headless browser (via Playwright or Puppeteer) ensuring accurate custom element and shadow DOM behavior, which JSDOM often struggles with.
**Alternatives considered**: `vitest` with `happy-dom` (fast, but simulated DOM can cause false negatives/positives with Web Components). Jest with JSDOM (similar issues, heavier).

## Persistent System Requirements
**Decision**: Ensure `system_requirements.md` is updated in every PR/Feature branch.
**Rationale**: Acts as a single source of truth for all components (backend and frontend) rather than relying on disparate spec files over time.
**Alternatives considered**: Generating a separate `frontend_requirements.md`. Rejected to maintain a single monolithic source of truth.
