#!/bin/bash
# check_env.sh — コンテナ内の依存関係を確認する
# Usage: docker compose run --rm pipeline check_env.sh

set -euo pipefail

OK="\033[1;32m[OK]\033[0m"
FAIL="\033[1;31m[FAIL]\033[0m"
errors=0

echo "======================================"
echo " 環境チェック"
echo "======================================"

# CUDA (nvidia-smi)
echo -n "  nvidia-smi ... "
if nvidia-smi > /dev/null 2>&1; then
    gpu=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
    echo -e "$OK ($gpu)"
else
    echo -e "$FAIL"
    ((errors++))
fi

# Python
echo -n "  Python 3.11 ... "
py_ver=$(python --version 2>&1)
if echo "$py_ver" | grep -q "3.11"; then
    echo -e "$OK ($py_ver)"
else
    echo -e "$FAIL ($py_ver)"
    ((errors++))
fi

# COLMAP
echo -n "  colmap ... "
if colmap -h > /dev/null 2>&1; then
    colmap_ver=$(colmap -h 2>&1 | head -1)
    echo -e "$OK"
else
    echo -e "$FAIL"
    ((errors++))
fi

# PyTorch + CUDA
echo -n "  torch.cuda.is_available() ... "
cuda_available=$(python -c "import torch; print(torch.cuda.is_available())" 2>&1)
if [ "$cuda_available" = "True" ]; then
    torch_ver=$(python -c "import torch; print(torch.__version__)")
    echo -e "$OK (torch=$torch_ver)"
else
    echo -e "$FAIL (cuda_available=$cuda_available)"
    ((errors++))
fi

# Gaussian Splatting リポジトリ
echo -n "  Gaussian Splatting repo ... "
if [ -f /opt/gaussian-splatting/train.py ]; then
    echo -e "$OK (/opt/gaussian-splatting/train.py)"
else
    echo -e "$FAIL"
    ((errors++))
fi

# diff-gaussian-rasterization
echo -n "  diff_gaussian_rasterization ... "
if python -c "import diff_gaussian_rasterization" 2>/dev/null; then
    echo -e "$OK"
else
    echo -e "$FAIL"
    ((errors++))
fi

echo "======================================"
if [ $errors -eq 0 ]; then
    echo -e "  \033[1;32m全チェック通過\033[0m"
else
    echo -e "  \033[1;31m$errors 件の問題が検出されました\033[0m"
    exit 1
fi
echo "======================================"
