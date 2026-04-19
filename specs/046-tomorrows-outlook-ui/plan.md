# Implementation Plan: Tomorrow's Outlook UI

**Branch**: `046-tomorrows-outlook-ui` | **Date**: 2026-04-20 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/046-tomorrows-outlook-ui/spec.md`

## Summary

Implement a new "Tomorrow's Outlook" UI component for the House Battery Control Home Assistant panel. The component will render a collapsible section displaying the 5 historical analog dates used for synthesis, and a set of collapsible graphs plotting the 288-element synthesized arrays for Import Price, Export Price, and Load.

## Technical Context

**Language/Version**: JavaScript (ES6+), LitElement (HTML/CSS)
**Primary Dependencies**: LitElement, Custom-card-helpers (HA frontend), Plotly.js / Chart.js / Recharts (Whatever HA's standard graphing library is, or we use HTML5 Canvas/SVG if simple enough, or HA's built-in `ha-chart` or simple SVG rendering like the existing plan table). Wait, Home Assistant custom panels usually use Chart.js if bundled, but building simple SVG polyline graphs is lightweight and reliable. Let's use simple SVG for the curves like the current codebase likely does or HTML Canvas.
**Storage**: N/A (Frontend only, reads from HA Websocket API)
**Testing**: None specified for JS currently.
**Target Platform**: Home Assistant Frontend Panel
**Project Type**: Web Application Component
**Performance Goals**: Renders instantly without blocking the main HA UI thread.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

No constitution violations detected. Fits perfectly into the newly modularized Lit component structure (Feature 038).

## Project Structure

### Documentation (this feature)

```text
specs/046-tomorrows-outlook-ui/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
custom_components/house_battery_control/
├── web.py               # Will need to register the new js file
└── frontend/
    ├── hbc-panel.js     # Will add the new tab navigation
    └── hbc-outlook.js   # [NEW] The new LitElement web component for Tomorrow's Outlook
```

**Structure Decision**: Standard Web Component architecture integrating seamlessly with the existing `hbc-panel.js` navigation structure.
