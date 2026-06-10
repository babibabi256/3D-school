#!/bin/bash
# run.sh — 学校PC上で実行するメインスクリプト
# Usage: ./run.sh [config_file]

set -euo pipefail

CONFIG=${1:-configs/experiment.yaml}

echo "======================================"
echo " 文化財3D生成パイプライン"
echo " Config: $CONFIG"
echo "======================================"

# 最新コードを取得
git pull

# Dockerイメージをビルド（変更があれば再ビルド）
docker compose build

# パイプライン実行
docker compose run --rm pipeline python scripts/run_pipeline.py --config "$CONFIG"

echo "======================================"
echo " 完了"
echo "======================================"
