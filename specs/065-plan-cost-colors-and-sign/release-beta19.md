# v1.9.0-beta.19 — Plan table cost/tariff color coding & export cost fixes

This prerelease (`Feature 065`) adds semantic green/red/neutral color coding to the 24-Hour Plan table (`5min` and `30min` views) and fixes two cost-accounting discrepancies uncovered during live wholesale operation.

## Highlights

- **Semantic Cost & Tariff Color Coding (`<hbc-plan-table-lite>` & `<hbc-plan-table>`):**
  - **`Cost` (`Interval Cost`):** Green (`#00ff88`, `.val-credit`) when `< -$0.0005` (net bill credit / earnings), Red/Coral (`#ff6b6b`, `.val-cost`) when `> +$0.0005` (net bill expense or negative-FiT export penalty), and Muted (`#8888aa`, `.val-neutral`) at `$0.00.0`.
  - **`Export` (`Export Rate`):** Red/Coral when `< -0.005` (solar-sponge negative feed-in penalty where exporting costs money), Green when `> +0.005` (positive feed-in reward), and Muted at `0.00`.
  - **`Import` (`Import Rate`):** Green when `< -0.005` (negative wholesale import price — paid to import) and Muted at `0.00` (keeping positive import rates in standard text).
  - Includes header tooltips on `Import`, `Export`, and `Cost`, a concise sign legend beneath the table, and `?v=58` panel cache-busting.
- **`:25` / `:55` Boundary Duration Fix (`diagnostics.py` & `coordinator.py`):**
  - Rounds interval duration (`round((end - start).total_seconds() / 60.0)`) so `299s` Amber `:25:01–:30:00` and `:55:01–:00:00` intervals evaluate as `5` minutes instead of truncating to `4` minutes (`-20%` interval cost dip), and hardens `$` stripping in `30min` summation.
- **Live Cumulative Cost Export Sign Fix (`TelemetryCostTracker`):**
  - Aligns `TelemetryCostTracker._on_tick` with the LP solver equation `(import_delta * current_price_imp) - (export_delta * current_price_exp)` so positive feed-in exports reduce cumulative cost and negative solar-sponge feed-in exports increase cumulative cost.

## Validation

- Python test suite: `365 passed, 2 xfailed` (`pytest tests/ -q`).
- Browser JS test suite: `21 passed, 0 failed` (`npm test` / Headless Chrome).
- Linters: `ruff check custom_components/ tests/` and `npm run lint:js` passed with `0` errors and `0` warnings.
- Non-destructive solver check: `0` lines modified in `fsm/lin_fsm.py`.
