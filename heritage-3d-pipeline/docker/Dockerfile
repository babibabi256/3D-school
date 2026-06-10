# ==============================================================
# 文化財3D生成パイプライン — GPU環境
# Base: CUDA 11.8 + cuDNN 8 + Ubuntu 22.04
# ==============================================================
FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV CUDA_HOME=/usr/local/cuda

# --------------------------------------------------
# 1. システムパッケージ
# --------------------------------------------------
RUN apt-get update && apt-get install -y \
    # Python 3.11
    python3.11 \
    python3.11-dev \
    python3.11-distutils \
    python3-pip \
    # ビルドツール
    git \
    cmake \
    ninja-build \
    build-essential \
    pkg-config \
    # COLMAP 依存
    libboost-all-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libmetis-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    # COLMAP 本体
    colmap \
    # 画像・映像
    ffmpeg \
    libopencv-dev \
    # ユーティリティ
    wget \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# --------------------------------------------------
# 2. Python 3.11 をデフォルトに
# --------------------------------------------------
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

# --------------------------------------------------
# 3. PyTorch (CUDA 11.8 対応版)
# --------------------------------------------------
RUN pip install --no-cache-dir \
    torch==2.0.1+cu118 \
    torchvision==0.15.2+cu118 \
    torchaudio==2.0.2+cu118 \
    --index-url https://download.pytorch.org/whl/cu118

# --------------------------------------------------
# 4. Python 依存ライブラリ
# --------------------------------------------------
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# --------------------------------------------------
# 5. Gaussian Splatting リポジトリ & 追加依存
# --------------------------------------------------
RUN git clone --depth 1 https://github.com/graphdeco-inria/gaussian-splatting /opt/gaussian-splatting \
    --recurse-submodules

# submodule: diff-gaussian-rasterization & simple-knn
RUN cd /opt/gaussian-splatting && \
    pip install --no-cache-dir \
        submodules/diff-gaussian-rasterization \
        submodules/simple-knn

# その他 GS 依存
RUN pip install --no-cache-dir \
    plyfile \
    tensorboard

# --------------------------------------------------
# 6. 動作確認スクリプト
# --------------------------------------------------
COPY docker/check_env.sh /usr/local/bin/check_env.sh
RUN chmod +x /usr/local/bin/check_env.sh

WORKDIR /workspace
