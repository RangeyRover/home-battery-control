# Specification: Visualizing Synthetic Forecast Transition

## Goal
Make it immediately obvious in the frontend Plan Table when the system stops using the live Amber forecast and begins using the historical analog (synthetic) forecast.

## Background
The HBC system currently constructs a 48-hour plan timeline. For the first ~24-30 hours, it relies on actual live forecasts from Amber. For the remainder of the 48-hour window, it seamlessly appends a "synthetic" forecast generated from historical analogs. Currently, this transition is invisible to the user in the Plan Table, making it difficult to understand which data points are live vs. historical.

## Functional Requirements
1. The backend API (`diagnostics.py`) MUST pass the internal `synthetic` flag to the frontend `hbc_status` payload for each plan row.
2. The frontend Plan Table (`hbc-plan-table.js`) MUST intercept the `Synthetic` flag when iterating through the plan rows.
3. If a row is flagged as synthetic, the `Local Time` column in the Plan Table MUST display an asterisk (`*`) immediately following the time string (e.g., `15:30*`).
4. A legend MUST be added to the bottom of the table to explain the asterisk. The text should read: `* Synthetic Forecast Period`.

## Success Criteria
- Users can visually distinguish synthetic forecast rows from live forecast rows in the Plan Table.
- The asterisk and legend are clear and unobtrusive.
- The table formatting does not break under 5-minute or 30-minute resolutions.

## Dependencies & Assumptions
- The internal `extended_rates_timeline` already accurately tracks the `synthetic` flag.
- The `diagnostics.py` file is the correct location to serialize this flag for the frontend.
