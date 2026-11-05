$ErrorActionPreference = 'Stop'
$policyPath = Join-Path $PSScriptRoot 'policy.json'
$policy = Get-Content -LiteralPath $policyPath -Raw | ConvertFrom-Json
if ($policy.mode -ne 'dry-run') { throw 'Only dry-run task installation is allowed.' }
$pythonPath = (Get-Command python.exe -ErrorAction Stop).Source
$windowlessPythonPath = Join-Path (Split-Path -Parent $pythonPath) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $windowlessPythonPath)) { throw 'pythonw.exe is required for hidden scheduled execution.' }
$controllerPath = Join-Path $PSScriptRoot 'controller.py'
$account = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $windowlessPythonPath -Argument ('"' + $controllerPath + '" watch') -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $account
$principal = New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -Hidden -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName 'AI Documentation Review - Read Only' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Local PR review. Dry-run only. No automatic restart after authorization or quota failures.' -Force | Select-Object TaskName,State
