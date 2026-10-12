# Research and decisions

## Approved scope amendment — 2026-10-12

The user approved implementation, then explicitly limited it to calculation changes and required Spec Kit task decomposition followed by SDD/TDD (tests before code). Powerwall mode scripts, executor behaviour, service payloads and command lifecycle remain unchanged. Script capability certification, rate control, watchdogs and new dispatch plumbing are excluded from this feature. Earlier wording requiring those changes is superseded by this amendment. First-state protection belongs in the calculation adapter, using its current price input; this does not claim continuous live enforcement between updates.

Economic policy remains: never recommend deliberate battery export at a nonpositive effective price; allow additional later negative-price solar export when the whole forecast sequence saves money. Forecasts are estimates, not a guarantee of actuator power or realised savings. Existing input price units are retained consistently; no speculative migration of stored accounting values.


## Exact model

Decision: use SciPy MILP with direction/mode binaries and equality balances.
Rationale: current grid balance inequality admits 0.65 kWh import for 0.125 kWh load without charging; negative prices reward the unused slack. Equality alone does not exclude simultaneous charging/discharging or net importing/exporting.
Alternative rejected: coefficient-only patch. It fixes one symptom but leaves impossible energy flows and post-solve inconsistency.
Primary API source: https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html (read 2026-10-12). SciPy supports bounded integer variables and a solve time limit. Compatibility with the repository minimum and deployed hardware remains a verification task.

## Economic policy

Decision: permit extra later negative-price solar export if the complete executable sequence saves money; forbid direct battery export at nonpositive effective prices.
Rationale: user explicitly selected this trade-off on 2026-10-12. Compare with no grid charging in the current command interval and retain future optimisation freedom.
Alternative rejected: lexicographic minimum negative solar spill or rigid reserved headroom. Those would reject profitable sequences the user explicitly allows.

## Existing defects relevant to replacement

- Positive dg coefficient floor at lin_fsm.py:174 reverses the intended incentive at negative sell prices.
- Spill penalty at line 184 already penalises negative solar export correctly; replace with exact meter cash, not a blindly sign-reversed coefficient.
- Acquisition gate at line 328 is missing a nonpositive-price prohibition, not an arithmetic sign inversion.
- Initial running_capacity is an SoC fraction at line 273 but later represents kWh.
- Headroom uses end-of-step B at line 289 and then clips C without reconstructing B.
- Current grid/discharge formulation and post-solve edits do not guarantee a physically consistent reported plan.
- execute.py sends entity_id only; limit_kw is not transmitted.
- context_builder.py pads prices/load/PV and has no trustworthy coverage contract; coordinator also contains a builder path that must remain consistent.

## Incident evidence

The user's CSV supports negative-tariff export timing, not battery attribution. Prior controlled solver experiments reproduced DISCHARGE_GRID with 27 kWh capacity, full initial SoC, 6.3 kW charge, 10 kW discharge, 1.5 kW load, 4.8 kW PV, buy -0.15, sell -0.20, acquisition -0.25 and 24 five-minute intervals. These are synthetic assumptions, not measured incident battery conditions. Preserve them as regression inputs during implementation.

## Actuation and forecast uncertainty

Decision: validate executable script modes and bounded command lifetime before enabling discretionary actions. Missing knowledge means safe fallback, not guessed fractional control.
Alternative rejected: applying an ideal continuous plan and hoping the next poll corrects it. It can consume the headroom the economics relied on.

## Spec Kit discovery

Observed: `.agent/skills/speckit.plan/SKILL.md` is installed for Antigravity; its frontmatter name uses a dot. `.agents/skills` and `.specify/memory/constitution.md` are absent. `.agents/rules/speckit.md` exists, but is not a discoverable skill manifest. `$speckit-plan` is not in this session's available-skill catalog.

OpenAI's repository skill examples use `.agents/skills/`: https://developers.openai.com/blog/skills-agents-sdk (read 2026-10-12). This explains the directory mismatch. The local helper scripts also expect `.specify` templates and numbered branch names, so blindly copying manifests would not fully repair their workflow.

Proposed separate repair: expose validated Codex-compatible skills under `.agents/skills`, align names with intended invocation, correct template/script paths and codex-prefixed feature resolution, and validate discovery in a fresh session. Do not overwrite this repo's Antigravity installation or run a force initialisation as part of the battery plan.
