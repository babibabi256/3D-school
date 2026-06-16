<#
.SYNOPSIS
  run.ps1 - main pipeline launcher for the Windows school PC (PowerShell port of run.sh)
.DESCRIPTION
  ASCII-only on purpose: Windows PowerShell 5.1 reads .ps1 files using the
  system ANSI codepage (cp932 on Japanese Windows) unless the file has a UTF-8
  BOM. Non-ASCII characters would be mis-decoded and break parsing, so keep
  this script ASCII-only.
.USAGE
  PowerShell:
    .\run.ps1 [config_file]
  Default config: configs/experiment.yaml
#>
param(
    [string]$Config = "configs/experiment.yaml"
)
$ErrorActionPreference = "Stop"

Write-Host "======================================"
Write-Host " Heritage 3D pipeline"
Write-Host " Config: $Config"
Write-Host "======================================"

# Pull latest code (input/ and output/ are gitignored -> transfer separately via scp)
git pull

# Build the Docker image (rebuilds only if changed)
docker compose build

# Run the pipeline
docker compose run --rm pipeline python scripts/run_pipeline.py --config $Config

Write-Host "======================================"
Write-Host " Done"
Write-Host "======================================"
