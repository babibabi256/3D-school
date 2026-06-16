#!/bin/bash
# remote-run-bg.sh — 学校PCでパイプラインをバックグラウンド実行する
#   SSHを切ってもMacを閉じても、学校PC側で処理が継続する。
#   進捗は ./remote-log.sh で確認する。
# Usage: ./remote-run-bg.sh [config_file]

set -uo pipefail

SCHOOL_HOST=${SCHOOL_HOST:-"100.107.213.78"}
SCHOOL_USER=${SCHOOL_USER:-"NDE-LAB"}
REMOTE_DIR=${REMOTE_DIR:-"C:/Users/NDE-LAB/3D-school/heritage-3d-pipeline"}
CONFIG=${1:-"configs/experiment.yaml"}
LOG="run.log"
ERRLOG="run.err.log"

echo "======================================"
echo " リモート バックグラウンド実行"
echo "  $SCHOOL_USER@$SCHOOL_HOST"
echo "  Config: $CONFIG"
echo "  Log:    $REMOTE_DIR/$LOG"
echo "======================================"

# 学校PCで run.ps1 を独立プロセスとして起動し、出力をログにリダイレクト。
# Start-Process はSSHセッションから切り離されるため、切断後も継続する。
ssh "$SCHOOL_USER@$SCHOOL_HOST" \
  "powershell -NoProfile -ExecutionPolicy Bypass -Command \"cd '$REMOTE_DIR'; if(Test-Path '$LOG'){Remove-Item '$LOG' -Force}; Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','run.ps1','$CONFIG' -RedirectStandardOutput '$LOG' -RedirectStandardError '$ERRLOG' -WindowStyle Hidden; Write-Host 'launched (background)'\""

echo ""
echo "起動しました。進捗確認:  ./remote-log.sh"
echo "完了の目印: ログに 'Done' / '研究用サマリー' が出れば終了です。"
