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

# Build only when the image is missing.
# In non-interactive sessions, 'docker compose build' can hang on the registry
# credential helper (docker-credential-desktop). Since src/ is volume-mounted and
# numpy is pinned at runtime, a rebuild is only needed for Dockerfile changes.
$img = docker images -q heritage-3d-pipeline:latest
if (-not $img) {
    Write-Host "Image not found - building..."
    docker compose build
} else {
    Write-Host "Image exists - skipping build (run 'docker compose build' manually after Dockerfile changes)."
}

# Run the pipeline.
# torch (cu118) is built against NumPy 1.x, but the image ships NumPy 2.x, which
# breaks torch.from_numpy ("Numpy is not available"). We pin numpy<2 at runtime
# in the SAME container, targeting the same interpreter that runs the pipeline
# (python -m pip), so it works even when the image rebuild is skipped.
docker compose run --rm pipeline bash -lc "python -m pip install --quiet 'numpy<2' && python scripts/run_pipeline.py --config $Config"

Write-Host "======================================"
Write-Host " Done"
Write-Host "======================================"
