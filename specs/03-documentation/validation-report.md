# Validation Report: User Documentation (03-documentation)

**Date**: 2026-03-04  
**Status**: PARTIAL

## Coverage Summary

| Metric | Count | Percentage |
|--------|-------|------------|
| Functional Requirements Covered | 7/7 | 100% |
| Acceptance Criteria Met | 7/8 | 87% |
| Edge Cases Documented | 2/3 | 67% |
| Success Criteria Met | 2/4 | 50% |
| Deliverables Present | 5/5 | 100% |
| CONF_ Keys Documented | 25/28 | 89% |

---

## Functional Requirements

| FR | Requirement | Status | Evidence |
|---|---|---|---|
| FR-001 | README install-to-working walkthrough | ✅ PASS | README.md L26-42: HACS steps, manual install, verification section |
| FR-002 | README reflects current state | ⚠️ PARTIAL | README L78 says "133 tests" — now 191. architecture.md L125 says "176 tests" |
| FR-003 | /docs config reference for every key | ⚠️ PARTIAL | 25/28 CONF_ keys documented. 3 missing (see below) |
| FR-004 | /docs troubleshooting/FAQ | ✅ PASS | troubleshooting.md: 7 FAQ entries matching plan |
| FR-005 | README badges | ✅ PASS | README L3-5: HACS, HA 2024.1+, MIT badges |
| FR-006 | manifest.json documentation URL correct | ✅ PASS | `https://github.com/RangeyRover/home-battery-control` ✓ |
| FR-007 | /docs How It Works deep-dive | ✅ PASS | how-it-works.md: 388 lines, Mermaid pipeline, solver objectives, I/O detail, execution, 5-min cycle |

---

## Undocumented Config Keys (SC-002 Gap)

| # | CONF_ Constant | Key String | Where It Should Be |
|---|---|---|---|
| 1 | `CONF_LOAD_CACHE_TTL` | `load_cache_ttl_minutes` | Step 2 Energy table — new in v1.4.4 |
| 2 | `CONF_ALLOW_CHARGE_FROM_GRID_ENTITY` | `allow_charge_entity` | Step 3 Control table |
| 3 | `CONF_ALLOW_EXPORT_ENTITY` | `allow_export_entity` | Step 3 Control table |
| 4 | `CONF_OBSERVATION_MODE` | `observation_mode` | Step 3 Control table |

> `round_trip_efficiency` is used via `config.get()` but has no CONF_ constant — it IS documented in configuration.md L69. No action needed.

---

## Acceptance Criteria

| # | Criterion | Status | Notes |
|---|---|---|---|
| US1-1 | Follow README → install | ✅ PASS | HACS steps, manual install, add integration |
| US1-2 | Complete config → see live data | ✅ PASS | Verification section L56-63 |
| US2-1 | Read config.md → understand options | ⚠️ PARTIAL | 4 config keys missing |
| US3-1 | Identify all inputs/outputs | ✅ PASS | how-it-works.md L70-205 covers all |
| US3-2 | Understand solver objectives | ✅ PASS | Solver section L249-286 |
| US3-3 | Understand pipeline data structures | ✅ PASS | FSMContext, FSMResult, Plan Interval all documented |
| US4-1 | Troubleshoot common issues | ✅ PASS | 7 FAQ entries |
| US5 | Developer can clone + test | ✅ PASS | README L74-80, architecture.md L121-128 |

---

## Edge Cases

| Edge Case | Documented? | Where |
|---|---|---|
| User installs without Amber | ❌ NOT DOCUMENTED | Should be in troubleshooting or prerequisites FAQ |
| User installs without Solcast | ❌ NOT DOCUMENTED | Same — partial install behaviour |
| User configures wrong entity type | ✅ | troubleshooting.md L72-80 (sensors unavailable) |

---

## Success Criteria

| SC | Criterion | Status | Notes |
|---|---|---|---|
| SC-001 | End-to-end install from README alone | ✅ PASS | Tested by file review — all steps present |
| SC-002 | Every CONF_ constant documented | ❌ FAIL | 25/28 — missing 3 keys |
| SC-003 | No stale references | ❌ FAIL | README L78 "133 tests", architecture.md L125 "176 tests" — actual is 191 |
| SC-004 | manifest.json URL correct | ✅ PASS | Both `documentation` and `issue_tracker` correct |

---

## Stale References Found

| File | Line | Stale Content | Should Be |
|---|---|---|---|
| README.md | L78 | `# 133 tests` | `# 191 tests` |
| architecture.md | L125 | `# Full suite (176 tests)` | `# Full suite (191 tests)` |

---

## Recommendations

### Must Fix (SC failures)

1. **Add `CONF_LOAD_CACHE_TTL` to configuration.md** Step 2 table — new configurable cache TTL (5-1440 min, default 360)
2. **Add `CONF_ALLOW_CHARGE_FROM_GRID_ENTITY` and `CONF_ALLOW_EXPORT_ENTITY`** to configuration.md Step 3 table — Teslemetry toggle entities
3. **Add `CONF_OBSERVATION_MODE`** to configuration.md Step 3 table — enables dry-run mode
4. **Fix test count** in README.md (133 → 191) and architecture.md (176 → 191)

### Should Fix (Edge cases)

5. **Add FAQ entry** for "What happens without Amber/Solcast?" — explain that HBC still loads but solver will produce sub-optimal results with flat/zero forecasts

### Nice to Have

6. Update tasks.md task statuses to reflect completed work
