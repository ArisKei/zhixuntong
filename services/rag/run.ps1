$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$env:PYTHONPATH = "$root\packages;$PSScriptRoot"
Set-Location $PSScriptRoot
python -m uvicorn main:app --reload --host 0.0.0.0 --port 9380
