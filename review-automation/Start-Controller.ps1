param([switch]$Background)
$ErrorActionPreference = 'Stop'
$controllerPath = Join-Path $PSScriptRoot 'controller.py'
$pythonPath = (Get-Command python.exe -ErrorAction Stop).Source
if ($Background) {
    $statePath = Join-Path $PSScriptRoot '.state'
    New-Item -ItemType Directory -Path $statePath -Force | Out-Null
    $process = Start-Process -FilePath $pythonPath -ArgumentList @('"' + $controllerPath + '"', 'watch') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $statePath 'service.log') -RedirectStandardError (Join-Path $statePath 'service-error.log')
    Write-Output "Started controller PID $($process.Id). Use controller.py status and controller.py stop."
} else {
    & $pythonPath $controllerPath watch
    exit $LASTEXITCODE
}
