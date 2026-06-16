# 接続確認手順書 — Mac → SSH → 学校PC → Docker → COLMAP / Gaussian Splatting

Tailscale導入済みの学校PC（Windows + GPU）へ、MacからSSH接続し、
Docker経由でCOLMAP / Gaussian Splattingを実行できる状態かを確認するための手順。

- 学校PC Tailscale IP: `100.107.213.78`
- 確認の流れ: **学校PC側の準備確認 → Mac側からの接続テスト**

### 確認済みの実環境（2026-06-16 時点）

| 項目 | 値 |
|------|-----|
| 学校PC ホスト名 | `DESKTOP-UKTTRVU` |
| 学校PC Tailscale IP | `100.107.213.78` |
| SSHユーザー名 | `NDE-LAB` |
| リモート作業ディレクトリ | `C:/heritage-3d-pipeline` |
| GPU | NVIDIA GeForce RTX 4050 Laptop (VRAM 6 GB) |
| ドライバ / Docker | 572.83 / Docker Server 29.5.3, compose v5.1.4 |
| 認証 | SSH鍵認証（ed25519） |

Mac側スクリプトの実行例:

```bash
SCHOOL_HOST=100.107.213.78 SCHOOL_USER=NDE-LAB ./scripts/check-connection.sh
```

スクリプトで一括確認する場合:

- 学校PC側: `scripts/check-school-pc.ps1`（PowerShell 管理者）
- Mac側: `scripts/check-connection.sh`

以下は各項目の手動確認コマンドと、失敗時の修正方法。

---

## 1. 学校PC側（Windows）

PowerShell を **管理者として実行** して確認する。

### 1-1. OpenSSH Server が有効か

```powershell
Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*'
```

`State : Installed` であればOK。未インストールなら:

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
```

### 1-2. sshd が起動しているか

```powershell
Get-Service sshd
```

`Status : Running` であればOK。停止中／自動起動設定は:

```powershell
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
```

待受ポート（22）の確認:

```powershell
Get-NetTCPConnection -State Listen -LocalPort 22
```

### 1-3. Windows Defender Firewall がSSHを許可しているか

```powershell
Get-NetFirewallRule -DisplayName '*SSH*' | Format-Table DisplayName, Enabled, Direction, Action
```

受信(Inbound)・許可(Allow)・有効(Enabled=True) のルールがあればOK。なければ作成:

```powershell
New-NetFirewallRule -Name sshd -DisplayName "OpenSSH Server (sshd)" `
  -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
```

### 1-4. Docker Engine が起動しているか

```powershell
docker --version
docker info
```

`docker info` がエラーなく情報を返せばOK。エラーの場合は Docker Desktop を起動する。

### 1-5. docker compose が利用可能か

```powershell
docker compose version
```

バージョンが表示されればOK（v2系）。

### 1-6. NVIDIA GPU が認識されているか

ホスト側:

```powershell
nvidia-smi
```

GPU名・ドライバ・VRAMが表示されればOK。

Dockerコンテナ内からのGPUアクセス（本パイプラインの実行前提）:

```powershell
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
```

> Windows + Docker Desktop の場合、WSL2バックエンドと NVIDIA Container Toolkit が
> 正しく構成されていればコンテナ内で `nvidia-smi` が動作する。

### 一括確認

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
cd C:\path\to\heritage-3d-pipeline
.\scripts\check-school-pc.ps1
```

---

## 2. Mac側

学校PCの準備ができたら、Macから順に接続テストする。

### 2-1. ping（到達性）

```bash
ping 100.107.213.78
```

応答がなければ、両機で Tailscale が起動しているか確認:

```bash
tailscale status
```

### 2-2. SSHポート(22)の到達確認

```bash
nc -z -v 100.107.213.78 22
```

### 2-3. SSHログイン

```bash
ssh user@100.107.213.78
```

`user` は学校PCのWindowsユーザー名に置き換える。初回は鍵の確認が出る。
パスワード認証ではなく鍵認証を推奨（`ssh-copy-id` 相当を手動で設定）。

`~/.ssh/config` に登録しておくと便利:

```text
Host school-pc
    HostName 100.107.213.78
    User user
    ServerAliveInterval 30
```

これで `ssh school-pc` で接続できる。

### 2-4. リモートでDocker / GPUを確認

ログインせずワンライナーで確認:

```bash
ssh user@100.107.213.78 "docker info --format '{{.ServerVersion}}'"
ssh user@100.107.213.78 "docker compose version"
ssh user@100.107.213.78 "nvidia-smi"
```

### 2-5. 一括確認スクリプト

```bash
chmod +x scripts/check-connection.sh
SCHOOL_HOST=100.107.213.78 SCHOOL_USER=user ./scripts/check-connection.sh
```

ping → ポート → SSHログイン → Docker → docker compose → GPU → コンテナ内GPU
の順に確認し、最後に成功／失敗サマリを表示する。

---

## 3. 確認後の実行

全項目がクリアできたら、Macから既存の `remote-run.sh` で実行できる:

```bash
SCHOOL_HOST=100.107.213.78 SCHOOL_USER=user \
REMOTE_DIR='~/heritage-3d-pipeline' \
./remote-run.sh configs/experiment.yaml
```

内部では学校PC上で `git pull` → `docker compose build` →
`docker compose run --rm pipeline ...` が実行され、
COLMAP / Gaussian Splatting のパイプラインが走る。

---

## トラブルシューティング早見表

| 症状 | 主な原因 | 確認・対処 |
|------|----------|-----------|
| ping不通 | Tailscale未起動 | 両機で `tailscale status` |
| port 22不通 | sshd停止 / Firewall | `Get-Service sshd` / Firewallルール |
| SSHログイン不可 | 鍵・ユーザー名誤り | `ssh -v user@IP` で詳細確認 |
| docker info失敗 | Docker Desktop未起動 | Docker Desktopを起動 |
| nvidia-smi無し | ドライバ未導入 | NVIDIAドライバ導入 |
| コンテナ内GPU不可 | Container Toolkit未設定 | WSL2 + NVIDIA Container Toolkit |

---

## Windows + OpenSSH 特有のハマりどころ（重要）

### A. 管理者アカウントの鍵は `administrators_authorized_keys`

`NDE-LAB` のようなローカル管理者アカウントでは、OpenSSHは個人の
`~/.ssh/authorized_keys` を**無視**し、
`C:\ProgramData\ssh\administrators_authorized_keys` のみを参照する。
`ssh-copy-id` は前者に入れてしまうため鍵認証が効かない。Macから次を実行して登録する:

```bash
KEY=$(cat ~/.ssh/id_ed25519.pub)
ssh NDE-LAB@100.107.213.78 "powershell -NoProfile -Command \"\$k='$KEY'; \$f='C:\ProgramData\ssh\administrators_authorized_keys'; if(!(Test-Path \$f)){New-Item -ItemType File -Path \$f -Force | Out-Null}; if(!(Select-String -Path \$f -SimpleMatch \$k -Quiet)){Add-Content -Path \$f -Value \$k}; icacls \$f /inheritance:r /grant 'Administrators:F' 'SYSTEM:F'\""
```

### B. リモートシェルが cmd.exe → シングルクォート問題

SSHログイン先の既定シェルは `cmd.exe`。cmd.exe はシングルクォート `'...'` を
区切り文字ではなく**文字そのもの**として扱うため、
`docker ... --format '{{.X}}'` を送ると出力にクォートが混入する。
リモートのdockerフォーマット指定はクォートを付けず `--format {{.X}}` とし、
受け取り側で余分なクォート/CRを除去する（本リポジトリの `check-connection.sh` は対応済み）。

### C. SSH非対話セッションでの `docker pull` / `build` 失敗

SSH越し（非対話）で `docker pull` や `docker compose build` を行うと、
Windowsの認証ヘルパーが次のエラーで失敗することがある:

```
error getting credentials ... A specified logon session does not exist.
```

公開イメージのpullは認証不要なので、学校PCの
`C:\Users\NDE-LAB\.docker\config.json` を開き
`"credsStore": "desktop"` の行を削除（または `"credsStore": ""`）すれば回避できる。
イメージがビルド済み（`heritage-3d-pipeline:latest`）であれば、検証スクリプトは
`--pull never` でpullを発生させないため影響を受けない。
