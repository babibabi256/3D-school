#!/bin/bash
# remote-run.sh — Mac側からSSH経由で学校PCのrun.shを起動する
# Usage: ./remote-run.sh [config_file]

set -euo pipefail

# 設定 — 環境変数または直接編集して使用
# 既定値は学校PC（Tailscale経由 / Windows）の確認済み環境に合わせている
SCHOOL_HOST=${SCHOOL_HOST:-"100.107.213.78"}      # 学校PCのTailscale IP
SCHOOL_USER=${SCHOOL_USER:-"NDE-LAB"}             # 学校PCのWindowsユーザー名
REMOTE_DIR=${REMOTE_DIR:-"C:/Users/NDE-LAB/3D-school/heritage-3d-pipeline"}
CONFIG=${1:-"configs/experiment.yaml"}

echo "======================================"
echo " リモート実行: $SCHOOL_USER@$SCHOOL_HOST"
echo " Config: $CONFIG"
echo "======================================"

# 学校PC（Windows）でPowerShell経由 run.ps1 を実行
# ※ ログイン先シェルが cmd.exe のため、bashのrun.shではなくrun.ps1を呼ぶ
# ※ run.ps1自体を取得するため、呼び出し前にここでgit pullしておく（初回ブートストラップ対策）
ssh "$SCHOOL_USER@$SCHOOL_HOST" \
  "powershell -NoProfile -ExecutionPolicy Bypass -Command \"cd '$REMOTE_DIR'; git pull; ./run.ps1 '$CONFIG'\""

echo "======================================"
echo " リモート実行完了"
echo "======================================"
