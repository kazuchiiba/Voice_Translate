# guard-destructive.ps1
# PreToolUse guardrail for shell commands (Bash / PowerShell):
#
#   1. File deletion is allowed ONLY inside temp locations:
#        - deletableTempDirs in ..\guardrail.json (e.g. Work\, tmp\)
#        - deletableCacheDirNames at any depth (e.g. __pycache__)
#        - the OS temp folder (%TEMP% / $env:TEMP, incl. Claude's scratchpad)
#      A command made only of such temp deletions is auto-allowed. Deleting
#      anything else -- or anything whose target can't be determined
#      (variables, pipelines, wildcards spanning folders) -- is denied.
#   2. Deletion whose target can't be checked at all (python os.remove /
#      shutil.rmtree, .NET File.Delete, robocopy /MIR, find -delete,
#      git clean, ...) is always denied.
#   3. Shell access to secret files (.env etc.) and piping downloads into a
#      shell are denied.
#
# Git history operations (commit, push, reset, rebase, ...) are NOT handled
# here; they are "ask" rules in ..\settings.json so the user confirms each one.
#
# Best-effort software guardrail, not an OS sandbox. When a block is a false
# positive, the user can run the command themselves with the `!` prefix.

$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.Encoding]::UTF8

$HooksDir    = $PSScriptRoot
$ClaudeDir   = Split-Path -Parent $HooksDir
$ProjectRoot = (Split-Path -Parent $ClaudeDir).TrimEnd('\')
$ConfigPath  = Join-Path $ClaudeDir 'guardrail.json'

function Emit([string]$decision, [string]$reason) {
    $out = @{
        hookSpecificOutput = @{
            hookEventName            = 'PreToolUse'
            permissionDecision       = $decision
            permissionDecisionReason = $reason
        }
    }
    Write-Output ($out | ConvertTo-Json -Depth 5 -Compress)
    exit 0
}

function Deny([string]$reason) {
    Emit 'deny' ("Blocked by destructive-operation guardrail: {0} Explain to the user what you wanted to do; they can run it themselves with the ! prefix if they agree." -f $reason)
}

$stdin = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($stdin)) { exit 0 }
try { $payload = $stdin | ConvertFrom-Json } catch { exit 0 }

if ($payload.tool_name -notin @('Bash', 'PowerShell')) { exit 0 }
$cmd = [string]$payload.tool_input.command
if ([string]::IsNullOrWhiteSpace($cmd)) { exit 0 }

$cwd = [string]$payload.cwd
if ([string]::IsNullOrWhiteSpace($cwd)) { $cwd = $ProjectRoot }

# ---------------------------------------------------------------- config ---
$tempDirs = @('Work', 'tmp', 'temp', '.tmp')
$cacheDirNames = @('__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache')
if (Test-Path $ConfigPath) {
    try {
        $config = Get-Content -Raw -Encoding UTF8 -Path $ConfigPath | ConvertFrom-Json
        if ($config.deletableTempDirs) { $tempDirs = @($config.deletableTempDirs) }
        if ($config.deletableCacheDirNames) { $cacheDirNames = @($config.deletableCacheDirNames) }
    } catch { }
}

$tempRoots = New-Object System.Collections.Generic.List[string]
foreach ($d in $tempDirs) {
    $tempRoots.Add([System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $d)).TrimEnd('\'))
}
foreach ($t in @($env:TEMP, $env:TMP)) {
    if ($t) { $tempRoots.Add([System.IO.Path]::GetFullPath($t).TrimEnd('\')) }
}

function Test-Under([string]$full, [string]$root) {
    return ($full -ieq $root) -or $full.StartsWith($root + '\', [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-TempPath([string]$full) {
    foreach ($root in $tempRoots) {
        # Deleting a temp root itself (e.g. the whole Work\ folder) is fine,
        # but never the OS temp folder itself.
        if ((Test-Under $full $root) -and -not ($full -ieq $env:TEMP.TrimEnd('\'))) { return $true }
    }
    if (Test-Under $full $ProjectRoot) {
        $rel = $full.Substring($ProjectRoot.Length).TrimStart('\')
        foreach ($seg in $rel.Split('\')) {
            if ($cacheDirNames -icontains $seg) { return $true }
        }
    }
    return $false
}

# Turns one deletion target as written in the command into a full path, or
# returns $null when it can't be determined safely.
function Resolve-Target([string]$t) {
    $t = $t.Trim().Trim('"', "'")
    if (-not $t) { return $null }

    if ($t -match '^(?i)(\$env:(TEMP|TMP)|%(TEMP|TMP)%|\$\{?TMPDIR\}?|/tmp)(?<rest>([\\/].*)?)$') {
        $t = $env:TEMP + $Matches['rest']
    } elseif ($t -match '^~(?<rest>([\\/].*)?)$') {
        $t = $HOME + $Matches['rest']
    } elseif ($t -match '^/(?<drive>[a-zA-Z])(?<rest>/.*)?$') {
        $t = $Matches['drive'] + ':\' + $Matches['rest']
    }

    # Anything still containing variables / expressions is unknowable.
    if ($t -match '[\$%`(){}@]') { return $null }

    $t = $t.Replace('/', '\')
    $wild = $t.IndexOfAny([char[]]'*?[')
    if ($wild -ge 0) {
        $base = $t.Substring(0, $wild)
        if ($base -eq '' -or -not ($base.EndsWith('\'))) {
            # `Work\chunk*` -> must be judged by its folder `Work\`
            # `Work*` -> folder is the parent, which could match `WorkImportant`
            $idx = $base.LastIndexOf('\')
            $base = if ($idx -ge 0) { $base.Substring(0, $idx + 1) } else { '.\' }
        }
        $t = $base
    }

    try {
        if (-not [System.IO.Path]::IsPathRooted($t)) { $t = Join-Path $cwd $t }
        return [System.IO.Path]::GetFullPath($t).TrimEnd('\')
    } catch {
        return $null
    }
}

# Prose in commit messages / PR descriptions often contains words like "rm",
# "del" or ".env". For those commands, ignore quoted text when scanning;
# anything outside the quotes (e.g. `; rm -rf x`) is still checked.
$scan = $cmd
if ($cmd -match '^\s*(git\s+(commit|tag)|gh\s+(repo\s+(create|edit)|pr\s+(create|edit)|issue\s+create|release\s+create))\b') {
    $scan = [regex]::Replace($scan, "@'[\s\S]*?'@", ' ')
    $scan = [regex]::Replace($scan, '@"[\s\S]*?"@', ' ')
    $scan = [regex]::Replace($scan, '"[^"]*"', ' ')
    $scan = [regex]::Replace($scan, "'[^']*'", ' ')
}

$ic = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase

# ------------------------------------------------- 3. secrets / remote exec ---
if ([regex]::IsMatch($scan, '(^|[\s"''\\/=<(])\.env(?![.\w])', $ic)) {
    Deny 'shell access to .env (contains the API key). Use .env.example for the variable names.'
}
if ([regex]::IsMatch($scan, 'secrets\.toml|[\\/]\.ssh[\\/]|id_rsa|id_ed25519|\.aws[\\/]credentials', $ic)) {
    Deny 'shell access to secret / credential files.'
}
if ([regex]::IsMatch($scan, '\b(curl|wget|iwr|irm|Invoke-WebRequest|Invoke-RestMethod)\b[^\n]*\|\s*(sh|bash|zsh|pwsh|powershell|iex|Invoke-Expression)\b', $ic)) {
    Deny 'piping downloaded code straight into a shell.'
}

# ------------------------------------- 2. deletion that can't be verified ---
$opaque = @(
    @{ p = 'shutil\.rmtree|os\.(remove|unlink|rmdir|removedirs)\s*\(|\.unlink\s*\(|\.rmdir\s*\(|send2trash'; r = 'Python file deletion' },
    @{ p = '\[(System\.)?IO\.(File|Directory|FileInfo|DirectoryInfo)\]::Delete|\.Delete\s*\(|FileSystem\]::Delete'; r = '.NET file deletion' },
    @{ p = '\brobocopy\b[^\n]*\s/(MIR|PURGE)\b'; r = 'robocopy /MIR or /PURGE (deletes files in the destination)' },
    @{ p = '\bfind\b[^\n]*\s-delete\b|\bfind\b[^\n]*-exec\s+rm\b'; r = 'find -delete' },
    @{ p = '\bgit\s+clean\b'; r = 'git clean (deletes untracked files, which git cannot restore)' },
    @{ p = 'Format-Volume|Clear-Disk|Clear-RecycleBin|\bformat\s+[a-z]:'; r = 'disk / recycle-bin wipe' },
    @{ p = '\bgh\s+repo\s+delete\b|\bgh\s+api\b[^\n]*(-X|--method)\s*DELETE\b'; r = 'GitHub repository / resource deletion' }
)
foreach ($o in $opaque) {
    if ([regex]::IsMatch($scan, $o.p, $ic)) {
        Deny ("{0}. Its targets can't be verified, so it is never allowed. To clean temp files, use Remove-Item with explicit paths under Work\ or another temp folder." -f $o.r)
    }
}

# ----------------------------------------------- 1. ordinary delete commands ---
# A delete verb must start the command or follow a separator / quote / brace.
$verbPattern = '(?:^|(?<=[\s;&|(){}"''`]))(?<verb>Remove-Item|Clear-Content|rm|rmdir|rd|del|erase|ri|unlink|shred|rimraf)(?=\s|$|["''])'
$valueParams = '^-(ErrorAction|ea|WarningAction|wa|InformationAction|ia|Include|Exclude|Filter|OutVariable|ov|ErrorVariable|ev|Stream|Credential)$'

$verbMatches = [regex]::Matches($scan, $verbPattern, $ic)
$foundDelete = $false
foreach ($m in $verbMatches) {
    # `git rm` is a git operation (tracked files are recoverable) -> settings.json "ask".
    $before = $scan.Substring(0, $m.Index)
    if ($before -match '(?i)\bgit\s+$') { continue }

    $foundDelete = $true
    $verb = $m.Groups['verb'].Value
    $rest = $scan.Substring($m.Index + $m.Length)
    $end = $rest.IndexOfAny([char[]]";&|`n`r)}")
    if ($end -ge 0) { $rest = $rest.Substring(0, $end) }

    $tokens = [regex]::Matches($rest, '"[^"]*"|''[^'']*''|\S+') | ForEach-Object { $_.Value }
    $targets = @()
    $skipNext = $false
    foreach ($tok in $tokens) {
        if ($skipNext) { $skipNext = $false; continue }
        $bare = $tok.Trim('"', "'")
        if ($bare -eq '' -or $bare -eq '--') { continue }
        if ($bare -match '^\d?>') { continue }                 # redirections 2>$null
        if ($bare -match $valueParams) { $skipNext = $true; continue }
        if ($bare -match '^-') { continue }                     # -Recurse -Force -rf -Path
        if ($verb -match '^(?i)(del|erase|rd|rmdir)$' -and $bare -match '^/[a-zA-Z]$') { continue }  # cmd /s /q
        $targets += $tok
    }

    if ($targets.Count -eq 0) {
        Deny ("'{0}' without explicit target paths (e.g. fed from a pipeline or variable) can't be verified as temp-only." -f $verb)
    }
    foreach ($tgt in $targets) {
        $full = Resolve-Target $tgt
        if (-not $full) {
            Deny ("can't determine what '{0} {1}' would delete (variables / expressions are not allowed in delete targets)." -f $verb, $tgt)
        }
        if (-not (Test-TempPath $full)) {
            Deny ("'{0}' is outside the deletable temp locations ({1}, cache folders, OS temp). Claude may not delete project files." -f $full, ($tempDirs -join ', '))
        }
    }
}

# Auto-allow only when the WHOLE command is nothing but verified temp deletions,
# so a temp delete can't smuggle another command past the permission prompt.
if ($foundDelete) {
    $segments = [regex]::Split($cmd, '\s*(?:&&|\|\||;|\r?\n)\s*') | Where-Object { $_.Trim() }
    $onlyDeletes = $true
    foreach ($seg in $segments) {
        if (-not [regex]::IsMatch($seg.Trim(), '^(Remove-Item|rm|rmdir|rd|del|erase|ri)(\s|$)', $ic) -or $seg -match '\|') {
            $onlyDeletes = $false
            break
        }
    }
    if ($onlyDeletes) {
        Emit 'allow' 'Temp-only deletion verified by guard-destructive.ps1.'
    }
}

exit 0
