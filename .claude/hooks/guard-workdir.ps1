# guard-workdir.ps1
# PreToolUse guardrail: blocks file access and obvious shell path-escapes
# outside the folder(s) listed in ..\guardrail.json (allowedProjectDirs).
#
# This is a best-effort software guardrail, not an OS-level sandbox: it
# inspects the arguments a tool is about to run with and denies the call
# before it executes. It cannot stop every possible shell trick, but it
# blocks the normal ways Claude would read/write/cd outside the allowed
# folder(s).
#
# To switch which project this guards, edit ..\guardrail.json -- this
# script itself should never need to change.

$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.Encoding]::UTF8

$HooksDir    = $PSScriptRoot
$ClaudeDir   = Split-Path -Parent $HooksDir
$ProjectRoot = Split-Path -Parent $ClaudeDir
$ConfigPath  = Join-Path $ClaudeDir 'guardrail.json'

function Deny([string]$reason) {
    $out = @{
        hookSpecificOutput = @{
            hookEventName            = 'PreToolUse'
            permissionDecision       = 'deny'
            permissionDecisionReason = $reason
        }
    }
    Write-Output ($out | ConvertTo-Json -Depth 5 -Compress)
    exit 0
}

# No config -> guardrail is unconfigured, allow everything (fail-open by design;
# this is a soft guardrail, see header comment).
if (-not (Test-Path $ConfigPath)) { exit 0 }

try {
    $config = Get-Content -Raw -Encoding UTF8 -Path $ConfigPath | ConvertFrom-Json
} catch {
    exit 0
}

$allowedDirNames = @($config.allowedProjectDirs)
if (-not $allowedDirNames -or $allowedDirNames.Count -eq 0) { exit 0 }

$allowedRoots = @($allowedDirNames | ForEach-Object {
    ([System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $_))).TrimEnd('\')
})

function Test-InsideAllowedRoots([string]$path) {
    if ([string]::IsNullOrWhiteSpace($path)) { return $true }
    try {
        if (-not [System.IO.Path]::IsPathRooted($path)) {
            $path = Join-Path $allowedRoots[0] $path
        }
        $full = [System.IO.Path]::GetFullPath($path).TrimEnd('\')
    } catch {
        # Unparseable path -> fail closed
        return $false
    }
    foreach ($root in $allowedRoots) {
        if (($full -ieq $root) -or $full.StartsWith($root + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

$stdin = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($stdin)) { exit 0 }

try {
    $payload = $stdin | ConvertFrom-Json
} catch {
    exit 0
}

$toolName  = $payload.tool_name
$toolInput = $payload.tool_input
if (-not $toolInput) { exit 0 }

$scopeLabel = $allowedDirNames -join ', '

# 1) Direct file-path style tools (Read, Edit, Write, Glob, Grep, NotebookEdit, ...)
foreach ($key in @('file_path', 'path', 'notebook_path')) {
    if ($toolInput.PSObject.Properties.Name -contains $key) {
        $p = $toolInput.$key
        if ($p -and -not (Test-InsideAllowedRoots $p)) {
            Deny "Blocked by working-directory guardrail: '$p' is outside the active project ($scopeLabel). Edit .claude\guardrail.json to change scope."
        }
    }
}

# 2) Shell commands: best-effort block of parent-directory traversal and
#    absolute paths that land outside the allowed root(s).
if ($toolName -in @('PowerShell', 'Bash') -and ($toolInput.PSObject.Properties.Name -contains 'command')) {
    $cmd = [string]$toolInput.command

    if ($cmd -match '(?<![\w.])\.\.(?![\w.])') {
        Deny "Blocked by working-directory guardrail: command references a parent directory ('..'), which could escape the active project ($scopeLabel)."
    }

    $absoluteMatches = [regex]::Matches($cmd, '(?:[A-Za-z]:\\|\\\\)[^\s"'']+')
    foreach ($m in $absoluteMatches) {
        if (-not (Test-InsideAllowedRoots $m.Value)) {
            Deny "Blocked by working-directory guardrail: command references an absolute path outside the active project ('$($m.Value)')."
        }
    }
}

exit 0
