param(
    [Parameter(Mandatory = $true)]
    [string]$ParticipantId,

    [Parameter(Mandatory = $true)]
    [ValidateSet("A", "B")]
    [string]$Condition
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$conditionLower = $Condition.ToLower()
$participantLower = $ParticipantId.ToLower()

$runtimeDir = Join-Path (Join-Path (Join-Path $PSScriptRoot "runtime") $ParticipantId) $Condition
$threadId = "study-" + $participantLower + "-" + $conditionLower
$userId = "study-user-" + $participantLower

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$env:AMADEUS_DATA_DIR = $runtimeDir
$env:AMADEUS_THREAD_ID = $threadId
$env:AMADEUS_USER_ID = $userId
$env:AMADEUS_TTS_ENABLED = "0"
$env:AMADEUS_USER_FACING_MODE = "1"
$env:AMADEUS_AUTO_APPROVE_MEMORY_WRITES = "1"
$env:AMADEUS_HIDE_TOOL_APPROVAL_LOGS = "1"
$env:AMADEUS_CANON_COUNTERPART_ID = "okabe_rintaro"
$env:AMADEUS_CANON_COUNTERPART_NAME = "冈部伦太郎"

Remove-Item Env:AMADEUS_ABLATE_PERSONA_ALIGNMENT -ErrorAction SilentlyContinue
Remove-Item Env:AMADEUS_ABLATE_WORLDLINE_MEMORY -ErrorAction SilentlyContinue

if ($Condition -eq "B") {
    $env:AMADEUS_ABLATE_PERSONA_ALIGNMENT = "1"
    $env:AMADEUS_ABLATE_WORLDLINE_MEMORY = "1"
}

$personaAblation = if ($Condition -eq "B") { "1" } else { "0" }
$worldlineAblation = if ($Condition -eq "B") { "1" } else { "0" }

Write-Host "[user-study] participant_id=$ParticipantId"
Write-Host "[user-study] condition=$Condition"
Write-Host "[user-study] data_dir=$runtimeDir"
Write-Host "[user-study] thread_id=$threadId"
Write-Host "[user-study] tts=off"
Write-Host "[user-study] user_facing_mode=1"
Write-Host "[user-study] auto_approve_memory_writes=1"
Write-Host "[user-study] hide_tool_approval_logs=1"
Write-Host "[user-study] canon_counterpart=冈部伦太郎"
Write-Host "[user-study] ablate_persona_alignment=$personaAblation"
Write-Host "[user-study] ablate_worldline_memory=$worldlineAblation"

Push-Location $repoRoot
try {
    python -m amadeus_thread0.cli
}
finally {
    Pop-Location
}

