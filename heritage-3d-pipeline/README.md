# 文化財3D生成パイプライン

COLMAP + Gaussian Splatting を用いた文化財の3D再構成を、完全再現可能な研究環境として構築したものです。

## システム構成

```
MacBook（開発）
    │ git push
    ▼
Git Repository
    │ git pull
    ▼
School GPU PC
    ├─ Cleansing
    ├─ COLMAP
    ├─ Gaussian Splatting
    ├─ Evaluation
    └─ Report Generation
```

## クイックスタート

### Mac（開発側）

```bash
git add .
git commit -m "update"
git push
```

リモート実行する場合（環境変数を設定してから）:

```bash
export SCHOOL_HOST=school-pc
export SCHOOL_USER=user
export REMOTE_DIR=~/heritage-3d-pipeline
./remote-run.sh
```

### 学校PC

```bash
git pull
./run.sh
```

特定の設定ファイルを指定する場合:

```bash
./run.sh configs/experiment_002.yaml
```

## ディレクトリ構成

```
heritage-3d-pipeline/
├── docker/
│   ├── Dockerfile
│   └── requirements.txt
├── configs/
│   └── experiment.yaml       # 実験設定ファイル
├── input/                    # 入力画像
├── output/                   # 出力結果
│   ├── cleansed/             # クレンジング後の画像
│   ├── colmap/               # COLMAP出力
│   ├── gaussian/             # Gaussian Splatting出力
│   ├── evaluation/           # 評価結果 (metrics.json)
│   └── report.md             # 自動生成レポート
├── scripts/
│   └── run_pipeline.py       # パイプライン本体
├── src/
│   ├── cleansing/            # 画像クレンジング
│   ├── colmap/               # COLMAP実行
│   ├── gaussian/             # Gaussian Splatting
│   ├── evaluation/           # PSNR/SSIM評価
│   └── report/               # レポート生成
├── docker-compose.yml
├── run.sh                    # 学校PC実行スクリプト
└── remote-run.sh             # MacからSSHで学校PCを起動
```

## 実験設定

`configs/experiment.yaml` で実験条件を管理します。コードを変更せずにパラメータを切り替えられます。

```yaml
project_name: temple_001

cleansing:
  enabled: true
  blur_threshold: 100.0

colmap:
  quality: high

gaussian:
  iterations: 30000
```

## パイプライン処理フロー

```
入力画像
  ↓
AI品質評価・クレンジング（ブレ・露出・重複検出）
  ↓
COLMAP（SfM・カメラ姿勢推定）
  ↓
Gaussian Splatting（3D学習）
  ↓
品質評価（PSNR / SSIM / LPIPS）
  ↓
レポート自動生成
  ↓
output/ に結果保存
```

## 必要環境

### Mac（開発）

- Git
- Docker Desktop
- Python 3.11
- VSCode

### 学校PC

- NVIDIA GPU（CUDA 11.8以上）
- Docker + NVIDIA Container Toolkit
- Git

## SSH設定例

`~/.ssh/config` に追加:

```
Host school-pc
    HostName 192.168.x.x
    User username
    IdentityFile ~/.ssh/id_ed25519
```
