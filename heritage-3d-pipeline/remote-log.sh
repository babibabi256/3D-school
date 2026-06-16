#!/bin/bash
# remote-log.sh — 学校PCで実行中のパイプラインのログ末尾を表示する
# Usage:
#   ./remote-log.sh         # 末尾40行を一度表示
#   ./remote-log.sh -f      # 5秒ごとに更新表示（Ctrl-Cで終了）
#   ./remote-log.sh 80      # 末尾80行を表示

set -uo pipefail

SCHOOL_HOST=${SCHOOL_HOST:-"100.107.213.78"}
SCHOOL_USER=${SCHOOL_USER:-"NDE-LAB"}
REMOTE_DIR=${REMOTE_DIR:-"C:/Users/NDE-LAB/3D-school/heritage-3d-pipeline"}
LOG="$REMOTE_DIR/run.log"

show() {
  local n="$1"
  ssh "$SCHOOL_USER@$SCHOOL_HOST" \
    "powershell -NoProfile -Command \"if(Test-Path '$LOG'){Get-Content '$LOG' -Tail $n}else{Write-Host 'ログ未生成（まだ開始直後の可能性）'}\""
}

if [ "${1:-}" = "-f" ]; then
  echo "5秒ごとに更新（Ctrl-Cで終了）"
  while true; do
    clear
    show 40
    sleep 5
  done
else
  N="${1:-40}"
  show "$N"
fi
