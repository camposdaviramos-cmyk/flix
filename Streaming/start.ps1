$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$streamPython = Get-Command python -ErrorAction SilentlyContinue
$streamLocalPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe'
if (Test-Path $streamLocalPython) { $streamPythonPath = $streamLocalPython } elseif ($streamPython) { $streamPythonPath = $streamPython.Source } else { throw 'Instale Python 3.11 ou superior.' }
if (-not (Test-Path '.packages\flask')) { & $streamPythonPath -m pip install --target .packages -r requirements.txt }
& $streamPythonPath run.py
