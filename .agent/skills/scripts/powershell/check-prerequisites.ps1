#!/usr/bin/env pwsh
<#
Consolidated prerequisite checking for Spec-Driven Development workflow.

Usage:
  pwsh ./check-prerequisites.ps1 [--json] [--require-tasks] [--include-tasks] [--paths-only] [--help|-h]
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---- Parse args (support GNU-ish flags) ----
$JSON_MODE     = $false
$REQUIRE_TASKS = $false
$INCLUDE_TASKS = $false
$PATHS_ONLY    = $false

foreach ($arg in $args) {
  switch ($arg) {
    "--json"          { $JSON_MODE = $true; break }
    "--require-tasks" { $REQUIRE_TASKS = $true; break }
    "--include-tasks" { $INCLUDE_TASKS = $true; break }
    "--paths-only"    { $PATHS_ONLY = $true; break }
    "--help" { Show-Help; exit 0 }
    "-h"     { Show-Help; exit 0 }
    default {
      Write-Error "ERROR: Unknown option '$arg'. Use --help for usage information."
      exit 1
    }
  }
}

function Show-Help {
@"
Usage: check-prerequisites.ps1 [OPTIONS]

Consolidated prerequisite checking for Spec-Driven Development workflow.

OPTIONS:
  --json              Output in JSON format
  --require-tasks     Require tasks.md to exist (for implementation phase)
  --include-tasks     Include tasks.md in AVAILABLE_DOCS list
  --paths-only        Only output path variables (no prerequisite validation)
  --help, -h          Show this help message

EXAMPLES:
  # Check task prerequisites (plan.md required)
  pwsh ./check-prerequisites.ps1 --json

  # Check implementation prerequisites (plan.md + tasks.md required)
  pwsh ./check-prerequisites.ps1 --json --require-tasks --include-tasks

  # Get feature paths only (no validation)
  pwsh ./check-prerequisites.ps1 --paths-only
"@ | Write-Host
}

# ---- Source common functions ----
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir "common.ps1")

# ---- Get feature paths and validate branch ----
$paths = Get-FeaturePaths
$REPO_ROOT      = $paths.REPO_ROOT
$CURRENT_BRANCH = $paths.CURRENT_BRANCH
$HAS_GIT        = $paths.HAS_GIT

$FEATURE_DIR   = $paths.FEATURE_DIR
$FEATURE_SPEC  = $paths.FEATURE_SPEC
$IMPL_PLAN     = $paths.IMPL_PLAN
$TASKS         = $paths.TASKS
$RESEARCH      = $paths.RESEARCH
$DATA_MODEL    = $paths.DATA_MODEL
$CONTRACTS_DIR = $paths.CONTRACTS_DIR
$QUICKSTART    = $paths.QUICKSTART

if (-not (Check-FeatureBranch -CurrentBranch $CURRENT_BRANCH -HasGit $HAS_GIT)) {
  exit 1
}

# ---- paths-only mode (JSON + paths-only supported) ----
if ($PATHS_ONLY) {
  if ($JSON_MODE) {
    $payload = [ordered]@{
      REPO_ROOT    = $REPO_ROOT
      BRANCH       = $CURRENT_BRANCH
      FEATURE_DIR  = $FEATURE_DIR
      FEATURE_SPEC = $FEATURE_SPEC
      IMPL_PLAN    = $IMPL_PLAN
      TASKS        = $TASKS
    }
    $payload | ConvertTo-Json -Compress | Write-Output
  } else {
    Write-Host "REPO_ROOT: $REPO_ROOT"
    Write-Host "BRANCH: $CURRENT_BRANCH"
    Write-Host "FEATURE_DIR: $FEATURE_DIR"
    Write-Host "FEATURE_SPEC: $FEATURE_SPEC"
    Write-Host "IMPL_PLAN: $IMPL_PLAN"
    Write-Host "TASKS: $TASKS"
  }
  exit 0
}

# ---- Validate required directories/files ----
if (-not (Test-Path -LiteralPath $FEATURE_DIR -PathType Container)) {
  Write-Error "ERROR: Feature directory not found: $FEATURE_DIR`nRun /speckit.specify first to create the feature structure."
  exit 1
}

if (-not (Test-Path -LiteralPath $IMPL_PLAN -PathType Leaf)) {
  Write-Error "ERROR: plan.md not found in $FEATURE_DIR`nRun /speckit.plan first to create the implementation plan."
  exit 1
}

if ($REQUIRE_TASKS -and -not (Test-Path -LiteralPath $TASKS -PathType Leaf)) {
  Write-Error "ERROR: tasks.md not found in $FEATURE_DIR`nRun /speckit.tasks first to create the task list."
  exit 1
}

# ---- Build list of available docs ----
$docs = New-Object System.Collections.Generic.List[string]

if (Test-Path -LiteralPath $RESEARCH   -PathType Leaf)      { $docs.Add("research.md") }
if (Test-Path -LiteralPath $DATA_MODEL -PathType Leaf)      { $docs.Add("data-model.md") }

if (Test-Path -LiteralPath $CONTRACTS_DIR -PathType Container) {
  $hasFiles = @(Get-ChildItem -LiteralPath $CONTRACTS_DIR -Force -ErrorAction SilentlyContinue).Count -gt 0
  if ($hasFiles) { $docs.Add("contracts/") }
}

if (Test-Path -LiteralPath $QUICKSTART -PathType Leaf) { $docs.Add("quickstart.md") }

if ($INCLUDE_TASKS -and (Test-Path -LiteralPath $TASKS -PathType Leaf)) { $docs.Add("tasks.md") }

# ---- Output ----
if ($JSON_MODE) {
  $payload = [ordered]@{
    FEATURE_DIR     = $FEATURE_DIR
    AVAILABLE_DOCS  = $docs
  }
  $payload | ConvertTo-Json -Compress | Write-Output
} else {
  Write-Host "FEATURE_DIR:$FEATURE_DIR"
  Write-Host "AVAILABLE_DOCS:"
  Check-File -Path $RESEARCH   -Label "research.md"
  Check-File -Path $DATA_MODEL -Label "data-model.md"
  Check-Dir  -Path $CONTRACTS_DIR -Label "contracts/"
  Check-File -Path $QUICKSTART -Label "quickstart.md"

  if ($INCLUDE_TASKS) {
    Check-File -Path $TASKS -Label "tasks.md"
  }
}