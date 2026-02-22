#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------
# Arg parsing (bash-like)
# ---------------------------
$JSON_MODE     = $false
$SHORT_NAME    = ""
$BRANCH_NUMBER = ""
$ARGS          = New-Object System.Collections.Generic.List[string]

for ($i = 0; $i -lt $args.Count; $i++) {
  $arg = $args[$i]
  switch ($arg) {
    "--json" { $JSON_MODE = $true; continue }

    "--short-name" {
      if ($i + 1 -ge $args.Count) { [Console]::Error.WriteLine("Error: --short-name requires a value"); exit 1 }
      $next = $args[$i + 1]
      if ($next -like "--*")       { [Console]::Error.WriteLine("Error: --short-name requires a value"); exit 1 }
      $SHORT_NAME = $next
      $i++
      continue
    }

    "--number" {
      if ($i + 1 -ge $args.Count) { [Console]::Error.WriteLine("Error: --number requires a value"); exit 1 }
      $next = $args[$i + 1]
      if ($next -like "--*")      { [Console]::Error.WriteLine("Error: --number requires a value"); exit 1 }
      $BRANCH_NUMBER = $next
      $i++
      continue
    }

    "--help" { Show-Help; exit 0 }
    "-h"     { Show-Help; exit 0 }

    default { $ARGS.Add($arg); continue }
  }
}

function Show-Help {
  $me = Split-Path -Leaf $MyInvocation.MyCommand.Path
@"
Usage: $me [--json] [--short-name <name>] [--number N] <feature_description>

Options:
  --json              Output in JSON format
  --short-name <name> Provide a custom short name (2-4 words) for the branch
  --number N          Specify branch number manually (overrides auto-detection)
  --help, -h          Show this help message

Examples:
  $me 'Add user authentication system' --short-name 'user-auth'
  $me 'Implement OAuth2 integration for API' --number 5
"@ | Write-Host
}

$FEATURE_DESCRIPTION = ($ARGS -join " ").Trim()
if ([string]::IsNullOrWhiteSpace($FEATURE_DESCRIPTION)) {
  [Console]::Error.WriteLine("Usage: specify.ps1 [--json] [--short-name <name>] [--number N] <feature_description>")
  exit 1
}

# ---------------------------
# Helpers: repo + git
# ---------------------------
function Test-HasGit {
  try { $null = (git rev-parse --show-toplevel 2>$null); return ($LASTEXITCODE -eq 0) } catch { return $false }
}

function Get-GitRepoRoot {
  try {
    $top = (git rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($top)) { return $top.Trim() }
  } catch {}
  return $null
}

function Find-RepoRoot {
  param([Parameter(Mandatory=$true)][string]$StartDir)

  $dir = (Resolve-Path -LiteralPath $StartDir).Path
  while ($true) {
    if (Test-Path -LiteralPath (Join-Path $dir ".git") -PathType Container) { return $dir }
    if (Test-Path -LiteralPath (Join-Path $dir ".specify") -PathType Container) { return $dir }

    $parent = Split-Path -Parent $dir
    if ([string]::IsNullOrWhiteSpace($parent) -or $parent -eq $dir) { break }
    $dir = $parent
  }
  return $null
}

# Highest N from specs directory (matches bash: leading digits of dir name)
function Get-HighestFromSpecs {
  param([Parameter(Mandatory=$true)][string]$SpecsDir)

  $highest = 0
  if (Test-Path -LiteralPath $SpecsDir -PathType Container) {
    foreach ($d in Get-ChildItem -LiteralPath $SpecsDir -Directory -ErrorAction SilentlyContinue) {
      $name = $d.Name
      $numStr = "0"
      if ($name -match '^([0-9]+)') { $numStr = $Matches[1] }

      # base-10 forced
      $num = 0
      try { $num = [int]$numStr } catch { $num = 0 }

      if ($num -gt $highest) { $highest = $num }
    }
  }
  return $highest
}

# Highest N from all git branches (local+remote) matching ^\d{3}-
function Get-HighestFromBranches {
  $highest = 0

  $branches = ""
  try { $branches = (git branch -a 2>$null) -join "`n" } catch { $branches = "" }

  if (-not [string]::IsNullOrWhiteSpace($branches)) {
    foreach ($line in ($branches -split "`n")) {
      $clean = $line.Trim()
      $clean = $clean -replace '^[\*\s]+', ''                 # remove leading "* " markers
      $clean = $clean -replace '^remotes/[^/]*/', ''          # remove "remotes/origin/"

      if ($clean -match '^([0-9]{3})-') {
        $num = [int]$Matches[1]  # base-10 safe
        if ($num -gt $highest) { $highest = $num }
      }
    }
  }

  return $highest
}

function Check-ExistingBranches {
  param([Parameter(Mandatory=$true)][string]$SpecsDir)

  # Fetch all remotes to get latest branch info (ignore errors)
  try { git fetch --all --prune 2>$null | Out-Null } catch {}

  $highestBranch = Get-HighestFromBranches
  $highestSpec   = Get-HighestFromSpecs -SpecsDir $SpecsDir

  $max = $highestBranch
  if ($highestSpec -gt $max) { $max = $highestSpec }

  return ($max + 1)
}

# Clean name: lowercase, non-alnum -> '-', collapse '-', trim ends
function Clean-BranchName {
  param([Parameter(Mandatory=$true)][string]$Name)

  $s = $Name.ToLowerInvariant()
  $s = [regex]::Replace($s, '[^a-z0-9]', '-')
  $s = [regex]::Replace($s, '-+', '-')
  $s = $s.Trim('-')
  return $s
}

# Branch suffix generation (stop words + length filtering + acronym preservation)
function Generate-BranchName {
  param([Parameter(Mandatory=$true)][string]$Description)

  # Mirror bash stop words (case-insensitive)
  $stop = @(
    "i","a","an","the","to","for","of","in","on","at","by","with","from",
    "is","are","was","were","be","been","being","have","has","had","do","does","did",
    "will","would","should","could","can","may","might","must","shall",
    "this","that","these","those","my","your","our","their",
    "want","need","add","get","set"
  ) | ForEach-Object { $_.ToLowerInvariant() }

  $orig = $Description
  $lower = $Description.ToLowerInvariant()
  $cleanWords = [regex]::Replace($lower, '[^a-z0-9]', ' ')
  $words = $cleanWords.Split(' ', [System.StringSplitOptions]::RemoveEmptyEntries)

  $meaningful = New-Object System.Collections.Generic.List[string]

  foreach ($w in $words) {
    if ([string]::IsNullOrWhiteSpace($w)) { continue }

    $isStop = $stop -contains $w
    if ($isStop) { continue }

    if ($w.Length -ge 3) {
      $meaningful.Add($w); continue
    }

    # Keep short words if they appear uppercase in original as whole word (acronym)
    $upper = $w.ToUpperInvariant()
    if ([regex]::IsMatch($orig, "\b$([regex]::Escape($upper))\b")) {
      $meaningful.Add($w)
    }
  }

  if ($meaningful.Count -gt 0) {
    $maxWords = 3
    if ($meaningful.Count -eq 4) { $maxWords = 4 }

    $picked = $meaningful | Select-Object -First $maxWords
    return ($picked -join "-")
  }

  # fallback: clean full string and take first 3 dash-separated tokens
  $cleaned = Clean-BranchName -Name $Description
  $parts = $cleaned.Split('-', [System.StringSplitOptions]::RemoveEmptyEntries) | Select-Object -First 3
  return ($parts -join "-")
}

# ---------------------------
# Resolve repo root + setup
# ---------------------------
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$repoRoot = Get-GitRepoRoot
$HAS_GIT = $false

if (-not [string]::IsNullOrWhiteSpace($repoRoot)) {
  $HAS_GIT = $true
} else {
  $repoRoot = Find-RepoRoot -StartDir $scriptDir
  if ([string]::IsNullOrWhiteSpace($repoRoot)) {
    [Console]::Error.WriteLine("Error: Could not determine repository root. Please run this script from within the repository.")
    exit 1
  }
  $HAS_GIT = $false
}

Set-Location -LiteralPath $repoRoot

$SPECS_DIR = Join-Path $repoRoot "specs"
New-Item -ItemType Directory -Path $SPECS_DIR -Force | Out-Null

# ---------------------------
# Branch suffix
# ---------------------------
if (-not [string]::IsNullOrWhiteSpace($SHORT_NAME)) {
  $BRANCH_SUFFIX = Clean-BranchName -Name $SHORT_NAME
} else {
  $BRANCH_SUFFIX = Generate-BranchName -Description $FEATURE_DESCRIPTION
}

# ---------------------------
# Branch number
# ---------------------------
if ([string]::IsNullOrWhiteSpace($BRANCH_NUMBER)) {
  if ($HAS_GIT) {
    $BRANCH_NUMBER = (Check-ExistingBranches -SpecsDir $SPECS_DIR).ToString()
  } else {
    $highest = Get-HighestFromSpecs -SpecsDir $SPECS_DIR
    $BRANCH_NUMBER = ($highest + 1).ToString()
  }
}

# Force base-10 and format %03d
$bn = 0
try { $bn = [int]$BRANCH_NUMBER } catch { $bn = 0 }
$FEATURE_NUM = $bn.ToString("000")

$BRANCH_NAME = "$FEATURE_NUM-$BRANCH_SUFFIX"

# GitHub 244-byte limit on branch names -> truncate suffix if needed
$MAX_BRANCH_LENGTH = 244
$bytes = [System.Text.Encoding]::UTF8.GetByteCount($BRANCH_NAME)

if ($bytes -gt $MAX_BRANCH_LENGTH) {
  # Account for "###-" = 4 bytes (ASCII)
  $MAX_SUFFIX_BYTES = $MAX_BRANCH_LENGTH - 4

  # Truncate by bytes safely
  $suffixBytes = [System.Text.Encoding]::UTF8.GetBytes($BRANCH_SUFFIX)
  if ($suffixBytes.Length -gt $MAX_SUFFIX_BYTES) {
    $truncBytes = $suffixBytes[0..($MAX_SUFFIX_BYTES-1)]
    $TRUNCATED_SUFFIX = [System.Text.Encoding]::UTF8.GetString($truncBytes)
  } else {
    $TRUNCATED_SUFFIX = $BRANCH_SUFFIX
  }

  # Remove trailing '-' if truncation created one
  $TRUNCATED_SUFFIX = $TRUNCATED_SUFFIX.TrimEnd('-')

  $ORIGINAL_BRANCH_NAME = $BRANCH_NAME
  $BRANCH_NAME = "$FEATURE_NUM-$TRUNCATED_SUFFIX"

  [Console]::Error.WriteLine("[specify] Warning: Branch name exceeded GitHub's 244-byte limit")
  [Console]::Error.WriteLine("[specify] Original: $ORIGINAL_BRANCH_NAME ($([System.Text.Encoding]::UTF8.GetByteCount($ORIGINAL_BRANCH_NAME)) bytes)")
  [Console]::Error.WriteLine("[specify] Truncated to: $BRANCH_NAME ($([System.Text.Encoding]::UTF8.GetByteCount($BRANCH_NAME)) bytes)")
}

# ---------------------------
# Create branch (if git)
# ---------------------------
if ($HAS_GIT) {
  git checkout -b $BRANCH_NAME | Out-Null
} else {
  [Console]::Error.WriteLine("[specify] Warning: Git repository not detected; skipped branch creation for $BRANCH_NAME")
}

# ---------------------------
# Create feature dir + spec.md
# ---------------------------
$featureDir = Join-Path $SPECS_DIR $BRANCH_NAME
New-Item -ItemType Directory -Path $featureDir -Force | Out-Null

$template = Join-Path (Join-Path $repoRoot ".specify") (Join-Path "templates" "spec-template.md")
$specFile = Join-Path $featureDir "spec.md"

if (Test-Path -LiteralPath $template -PathType Leaf) {
  Copy-Item -LiteralPath $template -Destination $specFile -Force
} else {
  New-Item -ItemType File -Path $specFile -Force | Out-Null
}

# Set env var for current session
$env:SPECIFY_FEATURE = $BRANCH_NAME

# ---------------------------
# Output
# ---------------------------
if ($JSON_MODE) {
  $payload = [ordered]@{
    BRANCH_NAME = $BRANCH_NAME
    SPEC_FILE   = $specFile
    FEATURE_NUM = $FEATURE_NUM
  }
  $payload | ConvertTo-Json -Compress | Write-Output
} else {
  Write-Host "BRANCH_NAME: $BRANCH_NAME"
  Write-Host "SPEC_FILE: $specFile"
  Write-Host "FEATURE_NUM: $FEATURE_NUM"
  Write-Host "SPECIFY_FEATURE environment variable set to: $BRANCH_NAME"
}