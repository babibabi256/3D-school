# 文化財3D生成研究環境 - 開発PC（Mac）要件定義

## 目的

開発者はMac上で開発・実験管理を行い、重い計算処理は学校PC（GPUマシン）へ委譲する。

開発者はローカル環境で直接3D生成処理を行わず、Git経由でコードを同期し、学校PC上でDockerコンテナを実行する。

最終的に以下の運用を実現する。

```bash
git add .
git commit -m "update"
git push
```

↓

学校PC

```bash
git pull
./run.sh
```

または

```bash
./remote-run.sh
```

のみで全工程が実行される。

---

# システム構成

```text
MacBook (開発環境)
    │
    │ git push
    ▼
Git Repository
    │
    │ git pull
    ▼
School GPU PC
    │
    ├─ Cleansing
    ├─ COLMAP
    ├─ Gaussian Splatting
    ├─ Evaluation
    └─ Report Generation
```

---

# Mac側の役割

## 開発

* Python開発
* Docker構成管理
* AIエージェント開発
* 実験設定作成

## 管理

* Git管理
* 実験設定ファイル管理
* 結果確認

## 非担当

以下はMacでは実行しない。

* COLMAP
* Gaussian Splatting学習
* NeRF学習
* 大規模推論

これらは学校PCで実施する。

---

# 必須ソフトウェア

## Git

用途

* ソースコード管理
* 学校PCとの同期

確認

```bash
git --version
```

---

## Docker Desktop

用途

* ローカル検証
* コンテナ開発

確認

```bash
docker --version
docker compose version
```

---

## Python

推奨

```text
Python 3.11
```

用途

* スクリプト開発
* テスト

---

## VSCode

用途

* 開発環境

推奨拡張

* Python
* Docker
* Git Graph
* Remote SSH

---

## SSH

用途

学校PCへの接続

確認

```bash
ssh user@school-pc
```

---

# ディレクトリ構成

```text
heritage-3d-pipeline/

├── docker/
│
├── configs/
│
├── input/
│
├── output/
│
├── scripts/
│
├── src/
│
├── tests/
│
├── docs/
│
├── docker-compose.yml
│
├── run.sh
│
└── README.md
```

---

# Git運用

mainブランチのみで開始する。

基本フロー

```bash
git pull

開発

git add .
git commit -m "feature"
git push
```

学校PC

```bash
git pull
```

のみで最新化できる状態にする。

---

# 実験設定

実験条件はコードではなく設定ファイルで管理する。

例

```yaml
project_name: temple_001

cleansing:
  enabled: true

colmap:
  quality: high

gaussian:
  iterations: 30000
```

研究再現性確保を目的とする。

---

# 将来追加予定

## AI画像品質評価

入力画像を評価

* ブレ
* ノイズ
* 露出
* 重複

を検出

---

## AIクレンジング

自動で

* 画像除外
* 背景除去
* マスク生成

を実施

---

## 評価システム

生成結果について

* PSNR
* SSIM
* LPIPS
* 処理時間
* VRAM使用量

を保存

---

## レポート生成

実験終了後

```text
実験概要
評価結果
比較表
考察
```

を自動生成

---

# 最終目標

開発者はMacで

```bash
git push
```

のみ行う。

学校PCでは

```bash
git pull
./run.sh
```

のみで以下が自動実行される。

```text
画像投入
↓
AI品質評価
↓
クレンジング
↓
COLMAP
↓
Gaussian Splatting
↓
品質評価
↓
レポート生成
↓
結果保存
```

文化財3D生成実験を完全再現可能な研究環境として構築する。
