#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Strict-ish error handling parity with bash:
# bash: set -e -u -o pipefail
# PS: StrictMode + Stop already covers most.

# -------------------------------------------------------------------
# Args: [agent_type]
# -------------------------------------------------------------------
$AGENT_TYPE = ""
if ($args.Count -ge 1) { $AGENT_TYPE = $args[0] }

# -------------------------------------------------------------------
# Load common.ps1 + feature paths
# -------------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir "common.ps1")

$paths = Get-FeaturePaths

$REPO_ROOT      = $paths.REPO_ROOT
$CURRENT_BRANCH = $paths.CURRENT_BRANCH
$HAS_GIT        = $paths.HAS_GIT

$FEATURE_DIR  = $paths.FEATURE_DIR
$FEATURE_SPEC = $paths.FEATURE_SPEC
$IMPL_PLAN    = $paths.IMPL_PLAN
$NEW_PLAN     = $IMPL_PLAN   # alias

# -------------------------------------------------------------------
# Agent-specific file paths (match bash)
# -------------------------------------------------------------------
$CLAUDE_FILE    = Join-Path $REPO_ROOT "CLAUDE.md"
$GEMINI_FILE    = Join-Path $REPO_ROOT "GEMINI.md"
$COPILOT_FILE   = Join-Path (Join-Path $REPO_ROOT ".github") (Join-Path "agents" "copilot-instructions.md")
$CURSOR_FILE    = Join-Path (Join-Path $REPO_ROOT ".cursor") (Join-Path "rules" "specify-rules.mdc")
$QWEN_FILE      = Join-Path $REPO_ROOT "QWEN.md"
$AGENTS_FILE    = Join-Path $REPO_ROOT "AGENTS.md"
$WINDSURF_FILE  = Join-Path (Join-Path $REPO_ROOT ".windsurf") (Join-Path "rules" "specify-rules.md")
$KILOCODE_FILE  = Join-Path (Join-Path $REPO_ROOT ".kilocode") (Join-Path "rules" "specify-rules.md")
$AUGGIE_FILE    = Join-Path (Join-Path $REPO_ROOT ".augment") (Join-Path "rules" "specify-rules.md")
$ROO_FILE       = Join-Path (Join-Path $REPO_ROOT ".roo") (Join-Path "rules" "specify-rules.md")
$CODEBUDDY_FILE = Join-Path $REPO_ROOT "CODEBUDDY.md"
$QODER_FILE     = Join-Path $REPO_ROOT "QODER.md"
$AMP_FILE       = $AGENTS_FILE
$SHAI_FILE      = Join-Path $REPO_ROOT "SHAI.md"
$Q_FILE         = $AGENTS_FILE
$BOB_FILE       = $AGENTS_FILE

$TEMPLATE_FILE  = Join-Path (Join-Path $REPO_ROOT ".specify") (Join-Path "templates" "agent-file-template.md")

# -------------------------------------------------------------------
# Globals for parsed plan data
# -------------------------------------------------------------------
$script:NEW_LANG = ""
$script:NEW_FRAMEWORK = ""
$script:NEW_DB = ""
$script:NEW_PROJECT_TYPE = ""

# -------------------------------------------------------------------
# Logging helpers
# -------------------------------------------------------------------
function Log-Info    { param([string]$m) Write-Host "INFO: $m" }
function Log-Success { param([string]$m) Write-Host "✓ $m" }
function Log-Warn    { param([string]$m) [Console]::Error.WriteLine("WARNING: $m") }
function Log-Error   { param([string]$m) [Console]::Error.WriteLine("ERROR: $m") }

# -------------------------------------------------------------------
# Validation
# -------------------------------------------------------------------
function Validate-Environment {
  if ([string]::IsNullOrWhiteSpace($CURRENT_BRANCH)) {
    Log-Error "Unable to determine current feature"
    if ($HAS_GIT) { Log-Info "Make sure you're on a feature branch" }
    else { Log-Info "Set SPECIFY_FEATURE environment variable or create a feature first" }
    exit 1
  }

  if (-not (Test-Path -LiteralPath $NEW_PLAN -PathType Leaf)) {
    Log-Error "No plan.md found at $NEW_PLAN"
    Log-Info "Make sure you're working on a feature with a corresponding spec directory"
    if (-not $HAS_GIT) {
      Log-Info "Use: `$env:SPECIFY_FEATURE='your-feature-name' or create a new feature first"
    }
    exit 1
  }

  if (-not (Test-Path -LiteralPath $TEMPLATE_FILE -PathType Leaf)) {
    Log-Warn "Template file not found at $TEMPLATE_FILE"
    Log-Warn "Creating new agent files will fail"
  }
}

# -------------------------------------------------------------------
# Plan parsing: extract **Field**: value
# Mirrors: grep "^\*\*Field\*\*: " | head -1 | sed ... | grep -v NEEDS CLARIFICATION | grep -v "^N/A$"
# -------------------------------------------------------------------
function Extract-PlanField {
  param(
    [Parameter(Mandatory=$true)][string]$FieldPattern,
    [Parameter(Mandatory=$true)][string]$PlanFile
  )

  $needle = "**$FieldPattern**: "
  foreach ($line in (Get-Content -LiteralPath $PlanFile -ErrorAction Stop)) {
    if ($line.StartsWith($needle)) {
      $val = $line.Substring($needle.Length).Trim()
      if ($val -match "NEEDS CLARIFICATION") { return "" }
      if ($val -eq "N/A") { return "" }
      return $val
    }
  }
  return ""
}

function Parse-PlanData {
  param([Parameter(Mandatory=$true)][string]$PlanFile)

  if (-not (Test-Path -LiteralPath $PlanFile -PathType Leaf)) {
    Log-Error "Plan file not found: $PlanFile"
    return $false
  }

  try { $null = Get-Content -LiteralPath $PlanFile -ErrorAction Stop -TotalCount 1 } catch {
    Log-Error "Plan file is not readable: $PlanFile"
    return $false
  }

  Log-Info "Parsing plan data from $PlanFile"

  $script:NEW_LANG         = Extract-PlanField -FieldPattern "Language/Version"       -PlanFile $PlanFile
  $script:NEW_FRAMEWORK    = Extract-PlanField -FieldPattern "Primary Dependencies"   -PlanFile $PlanFile
  $script:NEW_DB           = Extract-PlanField -FieldPattern "Storage"                -PlanFile $PlanFile
  $script:NEW_PROJECT_TYPE = Extract-PlanField -FieldPattern "Project Type"           -PlanFile $PlanFile

  if (-not [string]::IsNullOrWhiteSpace($script:NEW_LANG)) { Log-Info "Found language: $script:NEW_LANG" }
  else { Log-Warn "No language information found in plan" }

  if (-not [string]::IsNullOrWhiteSpace($script:NEW_FRAMEWORK)) { Log-Info "Found framework: $script:NEW_FRAMEWORK" }
  if (-not [string]::IsNullOrWhiteSpace($script:NEW_DB)) { Log-Info "Found database: $script:NEW_DB" }
  if (-not [string]::IsNullOrWhiteSpace($script:NEW_PROJECT_TYPE)) { Log-Info "Found project type: $script:NEW_PROJECT_TYPE" }

  return $true
}

function Format-TechnologyStack {
  param([string]$Lang, [string]$Framework)

  $parts = New-Object System.Collections.Generic.List[string]
  if (-not [string]::IsNullOrWhiteSpace($Lang) -and $Lang -ne "NEEDS CLARIFICATION") { $parts.Add($Lang) }
  if (-not [string]::IsNullOrWhiteSpace($Framework) -and $Framework -notin @("NEEDS CLARIFICATION","N/A")) { $parts.Add($Framework) }

  if ($parts.Count -eq 0) { return "" }
  if ($parts.Count -eq 1) { return $parts[0] }

  return ($parts -join " + ")
}

# -------------------------------------------------------------------
# Template / generated content helpers
# -------------------------------------------------------------------
function Get-ProjectStructure {
  param([string]$ProjectType)
  if ($ProjectType -like "*web*") {
    # In bash they used escaped \n; we can return actual newlines directly
    return "backend/`nfrontend/`ntests/"
  }
  return "src/`ntests/"
}

function Get-CommandsForLanguage {
  param([string]$Lang)
  if ($Lang -like "*Python*")      { return "cd src && pytest && ruff check ." }
  if ($Lang -like "*Rust*")        { return "cargo test && cargo clippy" }
  if ($Lang -like "*JavaScript*" -or $Lang -like "*TypeScript*") { return "npm test && npm run lint" }
  return "# Add commands for $Lang"
}

function Get-LanguageConventions {
  param([string]$Lang)
  return "$Lang: Follow standard conventions"
}

function Ensure-ParentDir {
  param([Parameter(Mandatory=$true)][string]$Path)
  $dir = Split-Path -Parent $Path
  if (-not (Test-Path -LiteralPath $dir -PathType Container)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
  }
}

# Create a new agent file from template (placeholder substitution)
function Create-NewAgentFile {
  param(
    [Parameter(Mandatory=$true)][string]$TempFile,
    [Parameter(Mandatory=$true)][string]$ProjectName,
    [Parameter(Mandatory=$true)][string]$CurrentDate
  )

  if (-not (Test-Path -LiteralPath $TEMPLATE_FILE -PathType Leaf)) {
    Log-Error "Template not found at $TEMPLATE_FILE"
    return $false
  }

  try {
    Copy-Item -LiteralPath $TEMPLATE_FILE -Destination $TempFile -Force
  } catch {
    Log-Error "Failed to copy template file"
    return $false
  }

  $projectStructure     = Get-ProjectStructure -ProjectType $script:NEW_PROJECT_TYPE
  $commands             = Get-CommandsForLanguage -Lang $script:NEW_LANG
  $languageConventions  = Get-LanguageConventions -Lang $script:NEW_LANG

  # Build tech stack / recent change strings (same conditional logic)
  $lang = $script:NEW_LANG
  $fw   = $script:NEW_FRAMEWORK
  $br   = $CURRENT_BRANCH

  if (-not [string]::IsNullOrWhiteSpace($lang) -and -not [string]::IsNullOrWhiteSpace($fw)) {
    $techStack    = "- $lang + $fw ($br)"
    $recentChange = "- $br: Added $lang + $fw"
  } elseif (-not [string]::IsNullOrWhiteSpace($lang)) {
    $techStack    = "- $lang ($br)"
    $recentChange = "- $br: Added $lang"
  } elseif (-not [string]::IsNullOrWhiteSpace($fw)) {
    $techStack    = "- $fw ($br)"
    $recentChange = "- $br: Added $fw"
  } else {
    $techStack    = "- ($br)"
    $recentChange = "- $br: Added"
  }

  $content = Get-Content -LiteralPath $TempFile -Raw

  # Simple literal replacements (template tokens are literal)
  $content = $content.Replace("[PROJECT NAME]", $ProjectName)
  $content = $content.Replace("[DATE]", $CurrentDate)
  $content = $content.Replace("[EXTRACTED FROM ALL PLAN.MD FILES]", $techStack)
  $content = $content.Replace("[ACTUAL STRUCTURE FROM PLANS]", $projectStructure)
  $content = $content.Replace("[ONLY COMMANDS FOR ACTIVE TECHNOLOGIES]", $commands)
  $content = $content.Replace("[LANGUAGE-SPECIFIC, ONLY FOR LANGUAGES IN USE]", $languageConventions)
  $content = $content.Replace("[LAST 3 FEATURES AND WHAT THEY ADDED]", $recentChange)

  Set-Content -LiteralPath $TempFile -Value $content -NoNewline
  return $true
}

# Update existing agent file (section-aware)
function Update-ExistingAgentFile {
  param(
    [Parameter(Mandatory=$true)][string]$TargetFile,
    [Parameter(Mandatory=$true)][string]$CurrentDate
  )

  Log-Info "Updating existing agent context file..."

  $techStack = Format-TechnologyStack -Lang $script:NEW_LANG -Framework $script:NEW_FRAMEWORK

  $newTechEntries = New-Object System.Collections.Generic.List[string]
  $newChangeEntry = ""

  # New tech entries (mirror bash rules)
  if (-not [string]::IsNullOrWhiteSpace($techStack)) {
    # bash bug note: they intended "- $tech_stack ($CURRENT_BRANCH)" but also checked grep -q "$tech_stack"
    # We'll mirror intent: if file doesn't already contain the techStack text, add entry.
    if (-not (Select-String -LiteralPath $TargetFile -SimpleMatch $techStack -Quiet)) {
      $newTechEntries.Add("- $techStack ($CURRENT_BRANCH)")
    }
  }

  if (-not [string]::IsNullOrWhiteSpace($script:NEW_DB) -and $script:NEW_DB -notin @("N/A","NEEDS CLARIFICATION")) {
    if (-not (Select-String -LiteralPath $TargetFile -SimpleMatch $script:NEW_DB -Quiet)) {
      $newTechEntries.Add("- $($script:NEW_DB) ($CURRENT_BRANCH)")
    }
  }

  if (-not [string]::IsNullOrWhiteSpace($techStack)) {
    $newChangeEntry = "- $CURRENT_BRANCH: Added $techStack"
  } elseif (-not [string]::IsNullOrWhiteSpace($script:NEW_DB) -and $script:NEW_DB -notin @("N/A","NEEDS CLARIFICATION")) {
    $newChangeEntry = "- $CURRENT_BRANCH: Added $($script:NEW_DB)"
  }

  $lines = Get-Content -LiteralPath $TargetFile -ErrorAction Stop

  $hasActiveTech = $lines | Where-Object { $_ -eq "## Active Technologies" } | ForEach-Object { $true } | Select-Object -First 1
  $hasRecent     = $lines | Where-Object { $_ -eq "## Recent Changes" }      | ForEach-Object { $true } | Select-Object -First 1

  if (-not $hasActiveTech) { $hasActiveTech = $false }
  if (-not $hasRecent)     { $hasRecent = $false }

  $out = New-Object System.Collections.Generic.List[string]

  $inTech = $false
  $inChanges = $false
  $techAdded = $false
  $existingChangesCount = 0

  foreach ($line in $lines) {
    # Active Technologies section start
    if ($line -eq "## Active Technologies") {
      $out.Add($line)
      $inTech = $true
      continue
    }

    # Leaving tech section on new heading
    if ($inTech -and $line -match '^##\s') {
      if (-not $techAdded -and $newTechEntries.Count -gt 0) {
        foreach ($e in $newTechEntries) { $out.Add($e) }
        $techAdded = $true
      }
      $out.Add($line)
      $inTech = $false
      continue
    }

    # In tech section, if blank line: insert new entries before blank (bash behaviour)
    if ($inTech -and $line -eq "") {
      if (-not $techAdded -and $newTechEntries.Count -gt 0) {
        foreach ($e in $newTechEntries) { $out.Add($e) }
        $techAdded = $true
      }
      $out.Add($line)
      continue
    }

    # Recent Changes section start
    if ($line -eq "## Recent Changes") {
      $out.Add($line)
      if (-not [string]::IsNullOrWhiteSpace($newChangeEntry)) { $out.Add($newChangeEntry) }
      $inChanges = $true
      continue
    }

    # Leaving changes section on new heading
    if ($inChanges -and $line -match '^##\s') {
      $out.Add($line)
      $inChanges = $false
      continue
    }

    # In changes section: keep only first 2 existing "- " bullets (bash behaviour)
    if ($inChanges -and $line -like "- *") {
      if ($existingChangesCount -lt 2) {
        $out.Add($line)
        $existingChangesCount++
      }
      continue
    }

    # Timestamp update: **Last updated**: YYYY-MM-DD
    if ($line -match '\*\*Last updated\*\*:\s*.*\d{4}-\d{2}-\d{2}') {
      $out.Add([regex]::Replace($line, '\d{4}-\d{2}-\d{2}', $CurrentDate, 1))
      continue
    }

    $out.Add($line)
  }

  # If file ended while still in tech section and entries not added: append them (bash post-loop)
  if ($inTech -and -not $techAdded -and $newTechEntries.Count -gt 0) {
    foreach ($e in $newTechEntries) { $out.Add($e) }
    $techAdded = $true
  }

  # If sections missing, append them at end (bash behaviour)
  if (-not $hasActiveTech -and $newTechEntries.Count -gt 0) {
    $out.Add("")
    $out.Add("## Active Technologies")
    foreach ($e in $newTechEntries) { $out.Add($e) }
  }

  if (-not $hasRecent -and -not [string]::IsNullOrWhiteSpace($newChangeEntry)) {
    $out.Add("")
    $out.Add("## Recent Changes")
    $out.Add($newChangeEntry)
  }

  # Atomic-ish write: write to temp then move
  $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("agent_update_{0}_{1}.tmp" -f ([System.Diagnostics.Process]::GetCurrentProcess().Id), ([guid]::NewGuid().ToString("N")))
  Set-Content -LiteralPath $tmp -Value ($out -join "`n") -NoNewline

  Move-Item -LiteralPath $tmp -Destination $TargetFile -Force
  return $true
}

# -------------------------------------------------------------------
# Update/create an agent file
# -------------------------------------------------------------------
function Update-AgentFile {
  param(
    [Parameter(Mandatory=$true)][string]$TargetFile,
    [Parameter(Mandatory=$true)][string]$AgentName
  )

  Log-Info "Updating $AgentName context file: $TargetFile"

  $projectName = Split-Path -Leaf $REPO_ROOT
  $currentDate = (Get-Date).ToString("yyyy-MM-dd")

  Ensure-ParentDir -Path $TargetFile

  if (-not (Test-Path -LiteralPath $TargetFile -PathType Leaf)) {
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("agent_new_{0}_{1}.tmp" -f ([System.Diagnostics.Process]::GetCurrentProcess().Id), ([guid]::NewGuid().ToString("N")))
    if (Create-NewAgentFile -TempFile $tmp -ProjectName $projectName -CurrentDate $currentDate) {
      Move-Item -LiteralPath $tmp -Destination $TargetFile -Force
      Log-Success "Created new $AgentName context file"
      return $true
    }
    if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
    Log-Error "Failed to create new agent file"
    return $false
  }

  # existing file checks
  try { $null = Get-Content -LiteralPath $TargetFile -TotalCount 1 -ErrorAction Stop } catch {
    Log-Error "Cannot read existing file: $TargetFile"
    return $false
  }

  try {
    # quick write test: open for append without changing content
    $fs = [System.IO.File]::Open($TargetFile, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::Read)
    $fs.Close()
  } catch {
    Log-Error "Cannot write to existing file: $TargetFile"
    return $false
  }

  $ok = Update-ExistingAgentFile -TargetFile $TargetFile -CurrentDate $currentDate
  if ($ok) { Log-Success "Updated existing $AgentName context file" }
  else { Log-Error "Failed to update existing agent file" }
  return $ok
}

# -------------------------------------------------------------------
# Agent selection logic (same names)
# -------------------------------------------------------------------
function Update-SpecificAgent {
  param([Parameter(Mandatory=$true)][string]$AgentType)

  switch ($AgentType) {
    "claude"      { return Update-AgentFile -TargetFile $CLAUDE_FILE    -AgentName "Claude Code" }
    "gemini"      { return Update-AgentFile -TargetFile $GEMINI_FILE    -AgentName "Gemini CLI" }
    "copilot"     { return Update-AgentFile -TargetFile $COPILOT_FILE   -AgentName "GitHub Copilot" }
    "cursor-agent"{ return Update-AgentFile -TargetFile $CURSOR_FILE    -AgentName "Cursor IDE" }
    "qwen"        { return Update-AgentFile -TargetFile $QWEN_FILE      -AgentName "Qwen Code" }
    "opencode"    { return Update-AgentFile -TargetFile $AGENTS_FILE    -AgentName "opencode" }
    "codex"       { return Update-AgentFile -TargetFile $AGENTS_FILE    -AgentName "Codex CLI" }
    "windsurf"    { return Update-AgentFile -TargetFile $WINDSURF_FILE  -AgentName "Windsurf" }
    "kilocode"    { return Update-AgentFile -TargetFile $KILOCODE_FILE  -AgentName "Kilo Code" }
    "auggie"      { return Update-AgentFile -TargetFile $AUGGIE_FILE    -AgentName "Auggie CLI" }
    "roo"         { return Update-AgentFile -TargetFile $ROO_FILE       -AgentName "Roo Code" }
    "codebuddy"   { return Update-AgentFile -TargetFile $CODEBUDDY_FILE -AgentName "CodeBuddy CLI" }
    "qoder"       { return Update-AgentFile -TargetFile $QODER_FILE     -AgentName "Qoder CLI" }
    "amp"         { return Update-AgentFile -TargetFile $AMP_FILE       -AgentName "Amp" }
    "shai"        { return Update-AgentFile -TargetFile $SHAI_FILE      -AgentName "SHAI" }
    "q"           { return Update-AgentFile -TargetFile $Q_FILE         -AgentName "Amazon Q Developer CLI" }
    "bob"         { return Update-AgentFile -TargetFile $BOB_FILE       -AgentName "IBM Bob" }
    default {
      Log-Error "Unknown agent type '$AgentType'"
      Log-Error "Expected: claude|gemini|copilot|cursor-agent|qwen|opencode|codex|windsurf|kilocode|auggie|roo|amp|shai|q|bob|qoder"
      exit 1
    }
  }
}

function Update-AllExistingAgents {
  $found = $false

  if (Test-Path -LiteralPath $CLAUDE_FILE -PathType Leaf)    { $null = Update-AgentFile $CLAUDE_FILE "Claude Code"; $found = $true }
  if (Test-Path -LiteralPath $GEMINI_FILE -PathType Leaf)    { $null = Update-AgentFile $GEMINI_FILE "Gemini CLI"; $found = $true }
  if (Test-Path -LiteralPath $COPILOT_FILE -PathType Leaf)   { $null = Update-AgentFile $COPILOT_FILE "GitHub Copilot"; $found = $true }
  if (Test-Path -LiteralPath $CURSOR_FILE -PathType Leaf)    { $null = Update-AgentFile $CURSOR_FILE "Cursor IDE"; $found = $true }
  if (Test-Path -LiteralPath $QWEN_FILE -PathType Leaf)      { $null = Update-AgentFile $QWEN_FILE "Qwen Code"; $found = $true }
  if (Test-Path -LiteralPath $AGENTS_FILE -PathType Leaf)    { $null = Update-AgentFile $AGENTS_FILE "Codex/opencode"; $found = $true }
  if (Test-Path -LiteralPath $WINDSURF_FILE -PathType Leaf)  { $null = Update-AgentFile $WINDSURF_FILE "Windsurf"; $found = $true }
  if (Test-Path -LiteralPath $KILOCODE_FILE -PathType Leaf)  { $null = Update-AgentFile $KILOCODE_FILE "Kilo Code"; $found = $true }
  if (Test-Path -LiteralPath $AUGGIE_FILE -PathType Leaf)    { $null = Update-AgentFile $AUGGIE_FILE "Auggie CLI"; $found = $true }
  if (Test-Path -LiteralPath $ROO_FILE -PathType Leaf)       { $null = Update-AgentFile $ROO_FILE "Roo Code"; $found = $true }
  if (Test-Path -LiteralPath $CODEBUDDY_FILE -PathType Leaf) { $null = Update-AgentFile $CODEBUDDY_FILE "CodeBuddy CLI"; $found = $true }
  if (Test-Path -LiteralPath $SHAI_FILE -PathType Leaf)      { $null = Update-AgentFile $SHAI_FILE "SHAI"; $found = $true }
  if (Test-Path -LiteralPath $QODER_FILE -PathType Leaf)     { $null = Update-AgentFile $QODER_FILE "Qoder CLI"; $found = $true }
  if (Test-Path -LiteralPath $Q_FILE -PathType Leaf)         { $null = Update-AgentFile $Q_FILE "Amazon Q Developer CLI"; $found = $true }
  if (Test-Path -LiteralPath $BOB_FILE -PathType Leaf)       { $null = Update-AgentFile $BOB_FILE "IBM Bob"; $found = $true }

  if (-not $found) {
    Log-Info "No existing agent files found, creating default Claude file..."
    return Update-AgentFile -TargetFile $CLAUDE_FILE -AgentName "Claude Code"
  }

  return $true
}

function Print-Summary {
  Write-Host ""
  Log-Info "Summary of changes:"

  if (-not [string]::IsNullOrWhiteSpace($script:NEW_LANG)) { Write-Host "  - Added language: $($script:NEW_LANG)" }
  if (-not [string]::IsNullOrWhiteSpace($script:NEW_FRAMEWORK)) { Write-Host "  - Added framework: $($script:NEW_FRAMEWORK)" }
  if (-not [string]::IsNullOrWhiteSpace($script:NEW_DB) -and $script:NEW_DB -ne "N/A") { Write-Host "  - Added database: $($script:NEW_DB)" }

  Write-Host ""
  Log-Info "Usage: update-agent-context.ps1 [claude|gemini|copilot|cursor-agent|qwen|opencode|codex|windsurf|kilocode|auggie|codebuddy|shai|q|bob|qoder]"
}

# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------
function Main {
  Validate-Environment

  Log-Info "=== Updating agent context files for feature $CURRENT_BRANCH ==="

  if (-not (Parse-PlanData -PlanFile $NEW_PLAN)) {
    Log-Error "Failed to parse plan data"
    exit 1
  }

  $success = $true

  if ([string]::IsNullOrWhiteSpace($AGENT_TYPE)) {
    Log-Info "No agent specified, updating all existing agent files..."
    if (-not (Update-AllExistingAgents)) { $success = $false }
  } else {
    Log-Info "Updating specific agent: $AGENT_TYPE"
    if (-not (Update-SpecificAgent -AgentType $AGENT_TYPE)) { $success = $false }
  }

  Print-Summary

  if ($success) {
    Log-Success "Agent context update completed successfully"
    exit 0
  } else {
    Log-Error "Agent context update completed with errors"
    exit 1
  }
}

Main