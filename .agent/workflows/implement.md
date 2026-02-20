---
description: MANDATORY pre-code gate. Must be followed before touching ANY .py file in custom_components/
---

# /implement — Spec-Kit Code Change Gate

**This workflow is MANDATORY before modifying any source file in `custom_components/`.**

## Phase Order (from SPECKIT.md)

The Spec-Kit SDLC phases must be followed in order. You cannot skip phases:

```
specify → clarify → plan → tasks → implement → checker → tester → validate
```

| Phase | What | File | Required Before Code? |
| :--- | :--- | :--- | :--- |
| `@speckit.specify` | Define/update requirements | `system_requirements.md` | YES |
| `@speckit.plan` | Technical plan | `implementation_plan.md` | YES |
| `@speckit.tester` | Write tests FIRST | `tests/test_*.py` | YES |
| `@speckit.implement` | Write code (make tests GREEN) | `custom_components/**/*.py` | — |
| `@speckit.checker` | Static analysis (ruff) | — | After code |
| `@speckit.validate` | Cross-check spec vs implementation | — | After code |

---

## Pre-Flight Checklist (BEFORE any source edit)

### Step 1 — SPEC
Which section in `system_requirements.md` does this change trace to?
- If none → STOP. Update the spec first. Request user review.
- State the section number (e.g. "Spec 3.2") before proceeding.

### Step 2 — PLAN
Is there an approved `implementation_plan.md` for this change?
- If no → Write the plan. Request user review. Wait for approval.
- Keep plans focused: one concern per plan.

### Step 3 — TEST
Is there a test that would FAIL if this bug existed?
- If no → Write the test FIRST. Do NOT touch the source file yet.
- Regression tests must document the exact production error in their docstring.

### Step 4 — RED
Run `python -m pytest tests/ -q` and confirm the new test FAILS.
- If it passes → The test doesn't catch the bug. Fix the test, not the code.
- If already GREEN (fix was pre-applied) → Acknowledge the process violation to the user.

---

## Execute (NOW you may edit source files)

### Step 5 — IMPLEMENT
Make the minimal code change to fix the failing test.
- One change per turn. Do not batch unrelated fixes.

### Step 6 — GREEN
Run `python -m pytest tests/ -q` — all tests must pass.

### Step 7 — LINT
Run `ruff check custom_components/ tests/` — must be clean.

---

## Ship (Separate commands — NEVER combine)

### Step 8 — COMMIT
```bash
git add -A && git commit -m "short message"
```

### Step 9 — PUSH
```bash
git push origin main
```

**NEVER combine steps 8 and 9 in one `&&` chain.** Multi-line commit messages cause the shell to hang.

---

## QA Pipeline (from SPECKIT.md)

After shipping, run the QA pipeline in this order:

1. **Checker** (`@speckit.checker`): `ruff check` — syntax & security
2. **Tester** (`@speckit.tester`): `pytest` — functionality
3. **Reviewer** (`@speckit.reviewer`): Code review — logic, performance, style
4. **Validate** (`@speckit.validate`): Cross-check implementation vs `system_requirements.md`

---

## Suggest Next Command (from SPECKIT.md)

After completing work, check project state and suggest next action:
- If **no spec**: suggest `@speckit.specify`
- If **spec exists but no plan**: suggest `@speckit.plan`
- If **plan exists but no tests**: suggest `@speckit.tester`
- If **tests exist and code is written**: suggest `@speckit.checker`
- If **checker passes**: suggest `@speckit.validate`

Always end with:
> "Based on the current state, I recommend running **[Next Command]** next."

---

## Violations

If you catch yourself editing source before step 3 is done:
- STOP immediately
- Write the test
- Acknowledge the violation to the user
- Do NOT continue until the test is written

## Reference Files

| File | Purpose |
| :--- | :--- |
| `system_requirements.md` | Source of truth for all requirements |
| `implementation_plan.md` | Technical plan for current changes |
| `task.md` | Checklist tracking progress |
| `.agent/skills/SPECKIT.md` | Full Spec-Kit skill definition |
| `tests/` | All test files |
