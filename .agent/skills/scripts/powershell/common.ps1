Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  # If we're in a git repo, use git to get the repo root.
  try {
    $top = (git rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($top)) {
      return $top.Trim()
    }
  } catch {}

  # Fall back to script location for non-git repos:
  # bash: script_dir/../../.. (three levels up from scripts dir)
  $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
  $fallback  = Resolve-Path -LiteralPath (Join-Path $scriptDir "..\..\..")
  return $fallback.Path
}

function Has-Git {
  try {
    $null = (git rev-parse --show-toplevel 2>$null)
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  }
}

function Get-CurrentBranch {
  # 1) SPECIFY_FEATURE env var override
  if (-not [string]::IsNullOrWhiteSpace($env:SPECIFY_FEATURE)) {
    return $env:SPECIFY_FEATURE
  }

  # 2) git branch if available
  try {
    $b = (git rev-parse --abbrev-ref HEAD 2>$null)
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($b)) {
      return $b.Trim()
    }
  } catch {}

  # 3) non-git: find latest feature directory under specs/ by numeric prefix
  $repoRoot = Get-RepoRoot
  $specsDir = Join-Path $repoRoot "specs"

  if (Test-Path -LiteralPath $specsDir -PathType Container) {
    $highest = -1
    $latest  = $null

    foreach ($d in Get-ChildItem -LiteralPath $specsDir -Directory -ErrorAction SilentlyContinue) {
      if ($d.Name -match '^([0-9]{3})-') {
        # Preserve leading zeros: parse as int
        $num = [int]$Matches[1]
        if ($num -gt $highest) {
          $highest = $num
          $latest  = $d.Name
        }
      }
    }

    if (-not [string]::IsNullOrWhiteSpace($latest)) {
      return $latest
    }
  }

  # Final fallback
  return "main"
}

function Check-FeatureBranch {
  param(
    [Parameter(Mandatory=$true)][string]$Branch,
    [Parameter(Mandatory=$true)][bool]$HasGitRepo
  )

  if (-not $HasGitRepo) {
    # Match bash behaviour: warn, but return success
    Write-Error "[specify] Warning: Git repository not detected; skipped branch validation"
    return $true
  }

  if ($Branch -notmatch '^[0-9]{3}-') {
    Write-Error "ERROR: Not on a feature branch. Current branch: $Branch"
    Write-Error "Feature branches should be named like: 001-feature-name"
    return $false
  }

  return $true
}

function Get-FeatureDir {
  param(
    [Parameter(Mandatory=$true)][string]$RepoRoot,
    [Parameter(Mandatory=$true)][string]$BranchName
  )
  return (Join-Path (Join-Path $RepoRoot "specs") $BranchName)
}

function Find-FeatureDirByPrefix {
  param(
    [Parameter(Mandatory=$true)][string]$RepoRoot,
    [Parameter(Mandatory=$true)][string]$BranchName
  )

  $specsDir = Join-Path $RepoRoot "specs"

  # Extract numeric prefix from branch (e.g., "004" from "004-whatever")
  if ($BranchName -notmatch '^([0-9]{3})-') {
    # If branch doesn't have numeric prefix, fall back to exact match
    return (Join-Path $specsDir $BranchName)
  }

  $prefix = $Matches[1]

  $matches = @()
  if (Test-Path -LiteralPath $specsDir -PathType Container) {
    foreach ($d in Get-ChildItem -LiteralPath $specsDir -Directory -ErrorAction SilentlyContinue) {
      if ($d.Name -like "$prefix-*") {
        $matches += $d.Name
      }
    }
  }

  if ($matches.Count -eq 0) {
    return (Join-Path $specsDir $BranchName)
  }
  elseif ($matches.Count -eq 1) {
    return (Join-Path $specsDir $matches[0])
  }
  else {
    Write-Error ("ERROR: Multiple spec directories found with prefix '{0}': {1}" -f $prefix, ($matches -join " "))
    Write-Error "Please ensure only one spec directory exists per numeric prefix."
    return (Join-Path $specsDir $BranchName)
  }
}

function Get-FeaturePaths {
  $repoRoot      = Get-RepoRoot
  $currentBranch = Get-CurrentBranch
  $hasGitRepo    = Has-Git

  # Use prefix-based lookup to support multiple branches per spec
  $featureDir = Find-FeatureDirByPrefix -RepoRoot $repoRoot -BranchName $currentBranch

  return [pscustomobject]@{
    REPO_ROOT      = $repoRoot
    CURRENT_BRANCH = $currentBranch
    HAS_GIT        = $hasGitRepo

    FEATURE_DIR    = $featureDir
    FEATURE_SPEC   = (Join-Path $featureDir "spec.md")
    IMPL_PLAN      = (Join-Path $featureDir "plan.md")
    TASKS          = (Join-Path $featureDir "tasks.md")
    RESEARCH       = (Join-Path $featureDir "research.md")
    DATA_MODEL     = (Join-Path $featureDir "data-model.md")
    QUICKSTART     = (Join-Path $featureDir "quickstart.md")
    CONTRACTS_DIR  = (Join-Path $featureDir "contracts")
  }
}

function Check-File {
  param(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)][string]$Label
  )
  if (Test-Path -LiteralPath $Path -PathType Leaf) { Write-Host "  ✓ $Label" }
  else { Write-Host "  ✗ $Label" }
}

function Check-Dir {
  param(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)][string]$Label
  )

  $ok = $false
  if (Test-Path -LiteralPath $Path -PathType Container) {
    $count = @(Get-ChildItem -LiteralPath $Path -Force -ErrorAction SilentlyContinue).Count
    $ok = ($count -gt 0)
  }

  if ($ok) { Write-Host "  ✓ $Label" }
  else { Write-Host "  ✗ $Label" }
}