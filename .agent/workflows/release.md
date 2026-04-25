---
description: MANDATORY versioning and release workflow. Must be followed before ANY version bump, tag, or GitHub release.
---

# Release Workflow

// turbo-all

## GITHUB CLI TIMING RULES (MANDATORY)

`gh` commands (release, issue, pr) do NOT produce detectable completion output.
Using `command_status` on them returns RUNNING indefinitely, even after they succeed.

**Rules:**
1. ALL `gh` commands MUST use `WaitMsBeforeAsync: 3000` (3-second fire-and-forget)
2. NEVER call `command_status` on a `gh` command — it will appear stuck
3. After firing a `gh` command, immediately proceed to the next step
4. If verification is critical, use a SEPARATE command: `gh release list --limit 3` or `gh release view vX.Y.Z`
5. The same rule applies to `gh issue create`, `gh issue close`, `gh pr create`

## VERSIONING RULES (MANDATORY)

Before bumping ANY version, you MUST check the current latest tag:

1. Run `git tag --list "v*" --sort=-v:refname` to find the latest stable version
2. The version MUST continue the existing v1.x line (e.g. if latest is v1.1.6, next feature = v1.2.0, next patch = v1.1.7)
3. NEVER reset to v0.x — the project is past v1.0.0
4. Feature branches use pre-release tags: v1.2.0-beta.1, v1.2.0-beta.2, etc.

### Semver Rules
- **MAJOR** (v2.0.0): Breaking changes to public interfaces or data models
- **MINOR** (v1.2.0): New features (e.g. new dashboard element, new API endpoint)
- **PATCH** (v1.1.7): Bug fixes, test fixes, doc updates, lint cleanup

## RELEASE STEPS

1. Run `git tag --list "v*" --sort=-v:refname` to determine the NEXT version number
2. Update version in BOTH files (they must match):
   - `custom_components/house_battery_control/manifest.json` → `"version": "X.Y.Z"`
   - `hacs.json` → `"version": "X.Y.Z"`
3. Run `pytest tests/ -v` — ALL tests must pass
4. Run `ruff check custom_components/ tests/` — must be clean
5. Run `npm run lint:js` — must be clean
6. **GitIgnore Audit (MANDATORY)**: Run `git status` and verify NO accidental junk files are staged. You MUST ensure:
   - `*.db` files (e.g. testing databases) are ignored (GitHub will block >100MB files).
   - Agent folders (e.g. `.agent/`, `.gemini/`) are not staged.
   - Scratch and Temp folders (`tmp/`, `scratch/`) are not staged.
7. Commit: `git add -A; git commit -m "chore: bump version to X.Y.Z"`
8. Push: `git push origin main` (WaitMsBeforeAsync: 10000)
9. Tag: `git tag vX.Y.Z`
10. Push tag: `git push origin vX.Y.Z` (WaitMsBeforeAsync: 10000)
11. Create release: `gh release create vX.Y.Z --title "vX.Y.Z — <summary>" --notes "<release notes>"` (**WaitMsBeforeAsync: 3000, do NOT wait**)
12. Verify (separate command, 3s later): `gh release list --limit 3`

## HACS COMPATIBILITY

- HACS uses the GitHub release tag to determine the latest version
- The tag name MUST match the version in `manifest.json` (with `v` prefix)
- The release MUST NOT be marked as pre-release for main branch releases
- Feature branch releases MUST be marked as pre-release: `gh release create vX.Y.Z-beta.N --prerelease`
