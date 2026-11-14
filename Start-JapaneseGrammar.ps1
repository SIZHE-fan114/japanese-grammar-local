# Start GraspMemoEdu Japanese Grammar Local-Personal Engine
[CmdletBinding()]
param(
    [string]$DataDir,
    [string]$PackagesDir,
    [ValidateRange(1, 65535)][int]$Port = 18782,
    [string]$BindHost = "127.0.0.1",
    [switch]$Reset,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$EnvDataDir = $env:GRASPMEMOEDU_JP_DATA_DIR
$DefaultDataDir = [IO.Path]::GetFullPath((Join-Path $RepoRoot '.runtime/japanese-grammar'))
if (-not $DataDir) {
    $DataDir = if ($EnvDataDir) { $EnvDataDir } else { $DefaultDataDir }
}
$DataDir = [IO.Path]::GetFullPath($DataDir)

if ($BindHost -notin @('127.0.0.1', 'localhost')) {
    throw "Refusing non-loopback host '$BindHost'. Local-Personal edition binds loopback only."
}

$ReservedPorts = @{
    8765  = 'AnkiConnect'
    8767  = 'GraspMemoEdu local dev server'
    18768 = 'Tencent Cloud production tunnel/service'
    18769 = 'Hyperskill bridge'
    18780 = 'graspmemoedu_local personal server'
    18781 = 'topological_quantum local server'
    18789 = 'category_theory local tool'
}
if ($ReservedPorts.ContainsKey($Port)) {
    $Owner = $ReservedPorts[$Port]
    throw "Port $Port is reserved for $Owner. Never terminate or reuse reserved ports (default 18782)."
}

$ForbiddenRuntimeDirs = @(
    [IO.Path]::GetFullPath((Join-Path $RepoRoot '.runtime/category-theory')),
    [IO.Path]::GetFullPath((Join-Path $RepoRoot '.runtime/topological-quantum'))
)
foreach ($ForbiddenDir in $ForbiddenRuntimeDirs) {
    if ([string]::Equals($DataDir, $ForbiddenDir, [StringComparison]::OrdinalIgnoreCase)) {
        throw "DataDir cannot point to sibling runtime directory '$ForbiddenDir'."
    }
}

if (Test-Path -LiteralPath $DataDir) {
    $DataItem = Get-Item -LiteralPath $DataDir -Force
    if ($DataItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "DataDir must not be a symlink/reparse point: $DataDir"
    }
}

if ($PackagesDir) {
    $PackagesDir = [IO.Path]::GetFullPath($PackagesDir)
    if (Test-Path -LiteralPath $PackagesDir) {
        $PkgItem = Get-Item -LiteralPath $PackagesDir -Force
        if ($PkgItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "PackagesDir must not be a symlink/reparse point: $PackagesDir"
        }
    }
}

$PythonBin = if ($env:GRASPMEMOEDU_PYTHON) { $env:GRASPMEMOEDU_PYTHON } else { Join-Path $RepoRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $PythonBin -PathType Leaf)) {
    throw "Virtual environment python not found at $PythonBin"
}

$DependencyCheck = "from importlib.metadata import version; from graspmemoedu.fsrs_engine import FSRSEngine; import tools.japanese_grammar.backend; assert version('fsrs') == '6.3.2'"
Push-Location -LiteralPath $RepoRoot
try {
    & $PythonBin -c $DependencyCheck
    if ($LASTEXITCODE -ne 0) {
        throw 'Environment dependencies check failed (requires fsrs==6.3.2 and tools.japanese_grammar.backend).'
    }
} finally {
    Pop-Location
}

$HealthUrl = "http://${BindHost}:${Port}/api/health"
$BrowserUrl = "http://${BindHost}:${Port}/"
$MarkerPath = Join-Path $DataDir 'server.json'
$ExpectedServiceId = 'graspmemoedu-japanese-grammar-local-v1'

function Test-LocalInstance($Identity, $ExpectedProcess) {
    if (-not $Identity) { return $false }
    if ($Identity.service_id -ne $ExpectedServiceId -or $Identity.mode -ne 'local-personal') { return $false }
    if ([int]$Identity.port -ne $Port) { return $false }
    if (-not (Test-Path -LiteralPath $MarkerPath -PathType Leaf)) { return $false }

    $Marker = Get-Content -LiteralPath $MarkerPath -Raw | ConvertFrom-Json
    if (
        $Marker.service -ne $ExpectedServiceId -or
        $Marker.instance_id -ne $Identity.instance_id -or
        [int]$Marker.pid -ne [int]$Identity.pid -or
        [int]$Marker.port -ne $Port
    ) {
        return $false
    }

    $ActualProcess = Get-Process -Id ([int]$Identity.pid) -ErrorAction SilentlyContinue
    if (-not $ActualProcess) { return $false }

    if ($ExpectedProcess -and $ExpectedProcess.Id -ne $ActualProcess.Id) {
        $RootProcess = Get-Process -Id $ExpectedProcess.Id -ErrorAction SilentlyContinue
        if (-not $RootProcess -or $RootProcess.StartTime -ne $ExpectedProcess.StartTime) { return $false }
        $ChildInfo = Get-CimInstance -ClassName Win32_Process -Filter ("ProcessId = " + $ActualProcess.Id)
        if (-not $ChildInfo -or [int]$ChildInfo.ParentProcessId -ne $ExpectedProcess.Id) { return $false }
    }

    $Started = if ($Identity.process_started_at -is [DateTime]) {
        $Identity.process_started_at.ToUniversalTime()
    } elseif ($Identity.process_started_at -is [DateTimeOffset]) {
        $Identity.process_started_at.UtcDateTime
    } else {
        [DateTimeOffset]::Parse([string]$Identity.process_started_at).UtcDateTime
    }

    return [Math]::Abs(($ActualProcess.StartTime.ToUniversalTime() - $Started).TotalMilliseconds) -lt 50
}

$Identity = $null
try {
    $Identity = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2
} catch {}

if ($Identity) {
    if ($Reset) {
        throw "Port $Port is already running (pid=$($Identity.pid)); stop the existing server before running with -Reset."
    }
    if (-not (Test-LocalInstance $Identity $null)) {
        throw "Port $Port is already responding, but its service/instance does not match $MarkerPath. Refusing to kill or reuse."
    }
    if (-not $NoBrowser) { Start-Process $BrowserUrl }
    Write-Host "GraspMemoEdu Japanese Grammar is already running at $BrowserUrl (pid=$($Identity.pid), instance=$($Identity.instance_id))." -ForegroundColor Green
    exit 0
}

$Listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($Listener) {
    throw "Port $Port is already in use by another process. Refusing to terminate other services."
}

New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
$WebDir = Join-Path $RepoRoot 'tools/japanese_grammar/web'
$Arguments = @(
    '-u',
    '-m', 'tools.japanese_grammar.backend.main',
    '--host', $BindHost,
    '--port', "$Port",
    '--data-dir', ('"' + $DataDir + '"'),
    '--web-dir', ('"' + $WebDir + '"')
)
if ($PackagesDir) {
    $Arguments += @('--packages-dir', ('"' + $PackagesDir + '"'))
}
if ($Reset) {
    $Arguments += '--reset'
}

Write-Host "Starting GraspMemoEdu Japanese Grammar Local-Personal Server on $BrowserUrl (data=$DataDir)..." -ForegroundColor Cyan
$ServerProcess = Start-Process -FilePath $PythonBin -ArgumentList $Arguments -WorkingDirectory $RepoRoot `
    -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $DataDir 'server.log') `
    -RedirectStandardError (Join-Path $DataDir 'server-error.log')

$Timer = [Diagnostics.Stopwatch]::StartNew()
while ($Timer.Elapsed.TotalSeconds -lt 15) {
    $ServerProcess.Refresh()
    if ($ServerProcess.HasExited) {
        throw "Local server exited early (code $($ServerProcess.ExitCode)). Inspect $DataDir\server-error.log."
    }
    try {
        $Identity = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 1
        if (Test-LocalInstance $Identity $ServerProcess) {
            if (-not $NoBrowser) { Start-Process $BrowserUrl }
            Write-Host "GraspMemoEdu Japanese Grammar Server ready at $BrowserUrl (pid=$($Identity.pid), instance=$($Identity.instance_id))." -ForegroundColor Green
            exit 0
        }
    } catch {}
    Start-Sleep -Milliseconds 200
}

throw "Local server did not pass /api/health instance verification within 15s. Inspect $DataDir\server-error.log."
