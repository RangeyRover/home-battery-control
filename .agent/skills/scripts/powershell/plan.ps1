#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------
# Parse args
# ---------------------------
$JSON_MODE = $false
$EXTRA = New-Object System.Collections.Generic.List[string]

foreach ($arg in $args) {
  switch ($arg) {
    "--json" { $JSON_MODE = $true; continue }
    "--help" { Show-Help; exit 0 }
    "-h"     { Show-Help; exit 0 }
    default  { $EXTRA.Add($arg); continue }
  }
}

function Show-Help {
  $me = Split-Path -Leaf $MyInvocation.MyCommand.Path
@"
Usage: $me [--json]
  --json    Output results in JSON format
  --help    Show this help message
"@ | Write-Host
}

# ---------------------------
# Load common
# ---------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir "common.ps1")

# ---------------------------
# Get paths / vars
# ---------------------------
$paths = Get-FeaturePaths

$REPO_ROOT      = $paths.REPO_ROOT
$CURRENT_BRANCH = $paths.CURRENT_BRANCH
$HAS_GIT        = $paths.HAS_GIT

$FEATURE_DIR   = $paths.FEATURE_DIR
$FEATURE_SPEC  = $paths.FEATURE_SPEC
$IMPL_PLAN     = $paths.IMPL_PLAN

# Validate branch naming only for git repos (matches your bash logic)
if (-not (Check-FeatureBranch -Branch $CURRENT_BRANCH -HasGitRepo $HAS_GIT)) { exit 1 }

# Ensure feature directory exists
New-Item -ItemType Directory -Path $FEATURE_DIR -Force | Out-Null

# Copy plan template if exists; else create empty plan.md
$template = Join-Path (Join-Path $REPO_ROOT ".specify") (Join-Path "templates" "plan-template.md")

if (Test-Path -LiteralPath $template -PathType Leaf) {
  Copy-Item -LiteralPath $template -Destination $IMPL_PLAN -Force
  Write-Host "Copied plan template to $IMPL_PLAN"
} else {
  Write-Host "Warning: Plan template not found at $template"
  New-Item -ItemType File -Path $IMPL_PLAN -Force | Out-Null
}

# Output (keep same keys as bash)
if ($JSON_MODE) {
  $payload = [ordered]@{
    FEATURE_SPEC = $FEATURE_SPEC
    IMPL_PLAN    = $IMPL_PLAN
    SPECS_DIR    = $FEATURE_DIR     # matches your bash output (even though name says SPECS_DIR)
    BRANCH       = $CURRENT_BRANCH
    HAS_GIT      = ($HAS_GIT.ToString().ToLowerInvariant())
  }
  $payload | ConvertTo-Json -Compress | Write-Output
} else {
  Write-Host "FEATURE_SPEC: $FEATURE_SPEC"
  Write-Host "IMPL_PLAN: $IMPL_PLAN"
  Write-Host "SPECS_DIR: $FEATURE_DIR"
  Write-Host "BRANCH: $CURRENT_BRANCH"
  Write-Host ("HAS_GIT: " + $HAS_GIT.ToString().ToLowerInvariant())
}