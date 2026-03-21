$ErrorActionPreference = "Stop"

param(
    [string]$PythonExe = "python",
    [int]$PollSeconds = 1,
    [string]$LogPath = "C:\Users\29920\.codex\repair_backups\watch_mycodex_latest.log"
)

$repairScript = Join-Path $PSScriptRoot "repair_codex_sidebar_mycodex.py"
if (-not (Test-Path $repairScript)) {
    throw "Missing repair script: $repairScript"
}

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"
    Write-Host $line
    $logDir = Split-Path -Parent $LogPath
    if ($logDir -and -not (Test-Path $logDir)) {
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    }
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
}

Write-Log "[watch-mycodex-repair] waiting for Codex to exit..."
while (Get-Process -Name Codex, codex -ErrorAction SilentlyContinue) {
    Start-Sleep -Seconds $PollSeconds
}

Write-Log "[watch-mycodex-repair] Codex exited, starting repair..."
& $PythonExe $repairScript --force 2>&1 | ForEach-Object {
    Write-Log "$_"
}
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Log "[watch-mycodex-repair] repair failed with exit code $exitCode"
    exit $exitCode
}

Write-Log "[watch-mycodex-repair] repair completed"
