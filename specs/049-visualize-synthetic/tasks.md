# Tasks

- [ ] Modify `diagnostics.py` to extract `rate.get("synthetic", False)` and append `"Synthetic": ...` to `table`.
- [ ] Modify `hbc-plan-table.js`:
  - [ ] Map the `"Synthetic"` field from the API row into `r.synthetic` for both 5min and 30min aggregations.
  - [ ] Append `*` to `Local Time` string if `r.synthetic` is true in the `<tbody>` render.
  - [ ] Add the `* Synthetic Forecast Period` legend below the table.
- [ ] Run test suite (`pytest`) to verify no regressions in `diagnostics.py`.
- [ ] Lint using `ruff check --fix custom_components/ tests/`.
