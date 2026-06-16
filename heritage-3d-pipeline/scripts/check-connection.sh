#!/bin/bash
# check-connection.sh — Mac → SSH → 学校PC → Docker → GPU の疎通を順に確認する
#
# Mac (開発機)
#   ↓ ping / ssh (Tailscale経由)
# 学校PC (Windows + GPU)
#   ↓ docker / docker compose
# COLMAP / Gaussian Splatting
#
# Usage:
#   ./check-connection.sh
#   SCHOOL_HOST=100.107.213.78 SCHOOL_USER=user ./check-connection.sh

set -uo pipefail

# ---- 設定（環境変数で上書き可）-------------------------------
SCHOOL_HOST=${SCHOOL_HOST:-"100.107.213.78"}   # 学校PCのTailscale IP
SCHOOL_USER=${SCHOOL_USER:-"user"}             # 学校PCのWindowsユーザー名
SSH_TARGET="${SCHOOL_USER}@${SCHOOL_HOST}"
SSH_OPTS="-o ConnectTimeout=8 -o BatchMode=yes -o StrictHostKeyChecking=accept-new"

PASS=0; FAILN=0
ok()   { echo "  [OK]   $1"; PASS=$((PASS+1)); }
ng()   { echo "  [FAIL] $1"; FAILN=$((FAILN+1)); }
hdr()  { echo ""; echo "======================================"; echo " $1"; echo "======================================"; }

echo "対象: ${SSH_TARGET}"

# ---- 1. ping -------------------------------------------------
hdr "1. ping (ネットワーク到達性)"
if ping -c 3 -t 5 "$SCHOOL_HOST" >/dev/null 2>&1; then
    ok "ping 応答あり ($SCHOOL_HOST)"
else
    ng "ping 応答なし。Tailscaleが両機で起動しているか確認 (tailscale status)"
fi

# ---- 2. SSHポート開放確認 ------------------------------------
hdr "2. SSH ポート(22) 到達確認"
if nc -z -G 5 "$SCHOOL_HOST" 22 >/dev/null 2>&1; then
    ok "TCP 22 に接続可能"
else
    ng "TCP 22 に接続不可。学校PCのsshd起動とFirewallを確認"
fi

# ---- 3. SSHログイン ------------------------------------------
hdr "3. SSH ログイン"
SSH_WHOAMI=$(ssh $SSH_OPTS "$SSH_TARGET" "whoami" 2>/dev/null)
if [ -n "$SSH_WHOAMI" ]; then
    ok "SSHログイン成功 (リモートユーザー: $SSH_WHOAMI)"
    SSH_LOGIN_OK=1
else
    ng "SSHログイン失敗。鍵設定・ユーザー名・sshd を確認"
    echo "       手動テスト: ssh ${SSH_TARGET}"
    SSH_LOGIN_OK=0
fi

# 以降のリモートチェックはSSHログイン成功時のみ
if [ "$SSH_LOGIN_OK" -eq 1 ]; then

    # ---- 4. リモート: Docker Engine --------------------------
    hdr "4. 学校PC: Docker Engine"
    # cmd.exe対策: フォーマット文字列にクォートを付けず、出力のクォート/CRを除去
    if ssh $SSH_OPTS "$SSH_TARGET" "docker info --format {{.ServerVersion}}" >/tmp/_docker_ver 2>/dev/null; then
        ok "Docker デーモン応答 (Server $(tr -d "'\"\r" </tmp/_docker_ver))"
    else
        ng "Docker に接続不可。Docker Desktop が起動しているか確認"
    fi

    # ---- 5. リモート: docker compose -------------------------
    hdr "5. 学校PC: docker compose"
    CV=$(ssh $SSH_OPTS "$SSH_TARGET" "docker compose version --short" 2>/dev/null | tr -d "'\"\r")
    if [ -n "$CV" ]; then
        ok "docker compose 利用可能 (v$CV)"
    else
        ng "docker compose が利用不可"
    fi

    # ---- 6. リモート: NVIDIA GPU -----------------------------
    hdr "6. 学校PC: NVIDIA GPU (ホスト)"
    GPU=$(ssh $SSH_OPTS "$SSH_TARGET" "nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader" 2>/dev/null)
    if [ -n "$GPU" ]; then
        ok "GPU認識: $GPU"
    else
        ng "nvidia-smi 失敗。NVIDIAドライバを確認"
    fi

    # ---- 7. リモート: コンテナ内GPU（任意）-------------------
    # 注意: SSH非対話セッションではWindowsの認証ヘルパー不具合により
    #       docker pull が失敗する場合があるため、ローカルに既存の
    #       イメージを --pull never で使い、pullを発生させない。
    hdr "7. 学校PC: Docker コンテナ内GPU (任意)"
    # 学校PC上に既にあるCUDA系イメージを自動選択（無ければpipelineイメージ）
    # 注意: リモートシェルがcmd.exeのためフォーマット文字列にクォートを付けない
    #       （cmd.exeはシングルクォートを文字として扱うため）。出力の余分な
    #       クォート/CRは除去する。
    GPU_IMG=$(ssh $SSH_OPTS "$SSH_TARGET" \
        "docker images --format {{.Repository}}:{{.Tag}} | findstr /i cuda" 2>/dev/null | head -n1 | tr -d "'\"\r")
    if [ -z "$GPU_IMG" ]; then
        GPU_IMG="heritage-3d-pipeline:latest"
    fi
    echo "  使用イメージ: $GPU_IMG (pullしない)"
    if ssh $SSH_OPTS "$SSH_TARGET" \
        "docker run --rm --pull never --gpus all $GPU_IMG nvidia-smi --query-gpu=name --format=csv,noheader" \
        >/tmp/_cgpu 2>/dev/null; then
        ok "コンテナからGPUアクセスOK: $(tr -d '\r' </tmp/_cgpu)"
    else
        ng "コンテナからGPUにアクセス不可。NVIDIA Container Toolkit / --gpus 設定を確認"
        echo "       手動確認: ssh $SSH_TARGET \"docker run --rm --pull never --gpus all $GPU_IMG nvidia-smi\""
    fi
fi

# ---- まとめ --------------------------------------------------
hdr "結果サマリ"
echo "  成功: $PASS  /  失敗: $FAILN"
if [ "$FAILN" -eq 0 ]; then
    echo "  → 全項目クリア。 ./remote-run.sh で実行可能です。"
    exit 0
else
    echo "  → 失敗項目を確認してください（docs/connection-check.md 参照）。"
    exit 1
fi
