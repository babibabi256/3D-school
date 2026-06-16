<#
.SYNOPSIS
  run.ps1 — 学校PC（Windows）上で実行するメインスクリプト（run.sh のPowerShell版）
.USAGE
  PowerShellで:
    .\run.ps1 [config_file]
  既定 config は configs/experiment.yaml
#>
param(
    [string]$Config = "configs/experiment.yaml"
)
$ErrorActionPreference = "Stop"

Write-Host "======================================"
Write-Host " 文化財3D生成パイプライン"
Write-Host " Config: $Config"
Write-Host "======================================"

# 最新コードを取得（input/output はgitignoreのため別途転送が必要）
git pull

# Dockerイメージをビルド（変更があれば再ビルド）
docker compose build

# パイプライン実行
docker compose run --rm pipeline python scripts/run_pipeline.py --config $Config

Write-Host "======================================"
Write-Host " 完了"
Write-Host "======================================"
