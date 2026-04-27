---
feature_id: 054
title: Export Margin and Round Trip Efficiency Config Levers
status: Draft
---

# Feature Specification: Export Margin and Round Trip Efficiency Levers

## 1. Overview
The solver currently makes marginal, zero-profit decisions to export power during the day. Because the battery loses a percentage of energy to conversion inefficiencies (round-trip efficiency), these marginal exports empty the battery, subsequently forcing the house to import power overnight at a higher cost. 

To give the user control over the solver's willingness to export and accurately model physical losses, this feature exposes two new levers in the UI configuration flow: "Round Trip Efficiency" and "Export Margin".

## 2. Business Requirements
- **BR-001 (Round Trip Efficiency):** The user MUST be able to configure the Round Trip Efficiency (RTE) via the integration's configuration flow.
- **BR-002 (Export Margin):** The user MUST be able to define a financial "Export Margin" via the configuration flow.
- **BR-003 (Solver Profit Threshold):** The Linear Programming (LP) and Dynamic Programming (DP) solvers MUST mathematically refuse to discharge to the grid unless the current sell price is greater than the sum of the acquisition cost and the user-defined export margin.
- **BR-004 (Self-Consumption Immunity):** The export margin MUST ONLY penalize grid exports. It MUST NOT penalize standard self-consumption.

## 3. User Experience (UX)
The existing configuration flow (specifically the "Energy & Metrics" step) will be updated to include two new optional sliders:
- **Round Trip Efficiency**: Slider from 0.50 to 1.00, defaulting to 0.90.
- **Export Margin**: Slider from 0.000 to 1.000, defaulting to 0.000.

## 4. Technical Constraints
- The Export Margin must subtract directly from the `sell_price` in the solver's objective function for grid exports (`dg`).
- The Round Trip Efficiency is already utilized by the solver math; it simply needs its hardcoded default exposed to the configuration UI.
