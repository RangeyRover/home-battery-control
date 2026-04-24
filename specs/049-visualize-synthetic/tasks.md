# Tasks

- [x] Modify `diagnostics.py` to extract `rate.get("synthetic", False)` and append `"Synthetic": ...` to `table`.
- [x] Modify `hbc-plan-table.js`:
  - [x] Map the `"Synthetic"` field from the API row into `r.synthetic` for both 5min and 30min aggregations.
  - [x] Append `*` to `Local Time` string if `r.synthetic` is true in the `<tbody>` render.
  - [x] Add the `* Synthetic Forecast Period` legend below the table.
- [x] Run test suite (`pytest`) to verify no regressions in `diagnostics.py`.
- [x] Lint using `ruff check --fix custom_components/ tests/`.
