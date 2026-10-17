$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw 'Project environment is missing. Create .venv and install the runtime requirements first.'
}
& $projectPython scripts/run_project.py --warmup
