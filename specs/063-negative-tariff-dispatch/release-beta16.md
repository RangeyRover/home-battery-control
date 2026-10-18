# v1.9.0-beta.16 — Negative-tariff calculation fixes

The battery planner now accounts for negative export tariffs and physical battery flows. It blocks deliberate battery export when the sell price is zero, negative, or does not exceed the configured export margin.

- Preserve battery space for forecast solar through signed solar-export costs and exact energy balances.
- Prevent simultaneous battery charging/discharging and grid importing/exporting in the optimisation.
- Re-solve acquisition-cost restrictions instead of modifying an already solved schedule.
- Check first-step negative-price grid charging against a feasible alternative without that charge, including later solar spill costs.
- Keep changes inside the existing linear calculation module. Powerwall scripts and mode control are unchanged.

Solar cannot be curtailed. Unavoidable solar export can still occur at negative prices; this release does not promise zero total export under every forecast or physical condition.

## Validation

- Offline calculation regression suite: 71 passed, 2 existing expected failures (2026-10-19).
- Previously recorded history CSV replay: no prohibited battery export across six full-horizon scenarios and 802 price-change checks.
- Latest supplied diagnostic snapshot: local 462-step replay produces zero negative-price solar export and zero negative-price battery export. Replay assumes export margin zero and no guard deadlines; diagnostics report the guard inactive. This is a forecast replay, not measured Powerwall verification.
- Home Assistant integration and live hardware operation have not been tested for this release.

## Scope and installation

This prerelease packages calculation fix ed19ee5 with version metadata updated to 1.9.0-beta.16. Uncommitted US4 solver-budget/dashboard specifications are excluded; their implementation is not included.

In HACS, select v1.9.0-beta.16 from the available beta versions, download it, then restart Home Assistant. Confirm the installed version and capture a fresh diagnostic snapshot to compare the recalculated plan. New forecasts and SoC can change the result.

## Release task record

User requested release preparation and confirmed a beta release on 2026-10-19. This packages the previously approved and implemented calculation work; no further solver changes are planned.

- [x] Confirm previous published version (v1.9.0-beta.15).
- [x] Run offline calculation regression checks.
- [x] Update manifest and HACS metadata; prepare release notes.
- [x] Commit only release metadata and this record (791acd1).
- [x] Publish v1.9.0-beta.16 as a GitHub prerelease and verify metadata.

Published and verified: https://github.com/RangeyRover/home-battery-control/releases/tag/v1.9.0-beta.16. Tag resolves to 791acd18a0491c8e87e5094b4f85ae830bdcb263; GitHub confirms prerelease=true and draft=false. Compared with beta.15, runtime differences are limited to lin_fsm.py and the two version metadata files.
