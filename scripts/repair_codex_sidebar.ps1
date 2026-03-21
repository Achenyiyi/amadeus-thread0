$repoRoot = Split-Path -Parent $PSScriptRoot
python "$PSScriptRoot\repair_codex_sidebar.py" @args
