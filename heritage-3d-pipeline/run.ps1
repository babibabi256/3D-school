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
# in the SAME container, targeting the same interpreter that runs the pipeline.
#
# IMPORTANT for logging in detached (no-console) runs:
#   -T  : disable pseudo-TTY so the container writes to the stdout PIPE
#         (captured by run-bg.ps1 '*>'), not to a console handle that is lost.
#   PYTHONUNBUFFERED=1 : flush python/rich/tqdm output immediately.
#   '2>&1' merges stderr into stdout so tracebacks (e.g. CUDA OOM) are logged.
$env:PYTHONUNBUFFERED = "1"
docker compose run --rm -T pipeline bash -lc "export PYTHONUNBUFFERED=1; python -m pip install --quiet 'numpy<2' && python scripts/run_pipeline.py --config $Config" 2>&1
$code = $LASTEXITCODE
Write-Host "PIPELINE EXIT CODE: $code"
if ($code -ne 0) {
    Write-Host "PIPELINE FAILED (non-zero exit). See the traceback above in this log."
}

Write-Host "======================================"
Write-Host " Done"
Write-Host "======================================"
