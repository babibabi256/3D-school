#!/bin/bash
# remote-run.sh — Mac側からSSH経由で学校PCのrun.shを起動する
# Usage: ./remote-run.sh [config_file]

set -euo pipefail

# 設定 — 環境変数または直接編集して使用
SCHOOL_HOST=${SCHOOL_HOST:-"school-pc"}
SCHOOL_USER=${SCHOOL_USER:-"user"}
REMOTE_DIR=${REMOTE_DIR:-"~/heritage-3d-pipeline"}
CONFIG=${1:-"configs/experiment.yaml"}

echo "======================================"
echo " リモート実行: $SCHOOL_USER@$SCHOOL_HOST"
echo " Config: $CONFIG"
echo "======================================"

# 学校PCで git pull + run.sh を実行
ssh "$SCHOOL_USER@$SCHOOL_HOST" "cd $REMOTE_DIR && ./run.sh $CONFIG"

echo "======================================"
echo " リモート実行完了"
echo "======================================"
