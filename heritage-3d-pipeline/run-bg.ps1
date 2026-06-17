<#
.SYNOPSIS
  run-bg.ps1 - wrapper that runs run.ps1 and captures ALL output streams to run.log.
.DESCRIPTION
  ASCII-only (Windows PowerShell 5.1 reads .ps1 as cp932 unless BOM).
  Launched detached by remote-run-bg.sh so the pipeline survives SSH disconnect.
  Using '*>' captures every stream (including Write-Host / native stdout+stderr),
  unlike Start-Process -RedirectStandardOutput which only captures stdout.
.USAGE
  powershell -NoProfile -ExecutionPolicy Bypass -File run-bg.ps1 [config_file]
#>
param(
    [string]$Config = "configs/experiment.yaml"
)
Set-Location $PSScriptRoot
& "$PSScriptRoot\run.ps1" $Config *> "$PSScriptRoot\run.log"
