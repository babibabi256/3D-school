<#
.SYNOPSIS
  学校PC（Windows + GPU）側のSSH/Docker/GPU環境を一括確認する。
.DESCRIPTION
  Mac → SSH → Docker → COLMAP → Gaussian Splatting の前提が
  整っているかを確認するためのチェックスクリプト。
  学校PC上で PowerShell を「管理者として実行」して実行する。
.USAGE
  PowerShell（管理者）で:
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\check-school-pc.ps1
#>

$ErrorActionPreference = "Continue"

function Section($title) {
    Write-Host ""
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host " $title" -ForegroundColor Cyan
    Write-Host "======================================" -ForegroundColor Cyan
}
function Ok($msg)   { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

# ------------------------------------------------------------
Section "0. 基本情報"
Write-Host "Hostname : $($env:COMPUTERNAME)"
Write-Host "User     : $($env:USERNAME)"
try {
    $ts = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like "100.*" }).IPAddress
    if ($ts) { Write-Host "Tailscale IP : $ts" } else { Warn "100.x.x.x のTailscale IPが見つかりません" }
} catch { Warn "IPアドレス取得に失敗しました" }

# ------------------------------------------------------------
Section "1. OpenSSH Server が有効か"
$cap = Get-WindowsCapability -Online | Where-Object Name -like "OpenSSH.Server*"
if ($cap) {
    Write-Host ("Name  : {0}" -f $cap.Name)
    Write-Host ("State : {0}" -f $cap.State)
    if ($cap.State -eq "Installed") { Ok "OpenSSH Server はインストール済み" }
    else {
        Fail "OpenSSH Server が未インストール"
        Write-Host "  → 修正: Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0"
    }
} else {
    Fail "OpenSSH.Server 機能が見つかりません"
}

# ------------------------------------------------------------
Section "2. sshd サービスが起動しているか"
$svc = Get-Service sshd -ErrorAction SilentlyContinue
if ($svc) {
    Write-Host ("Status     : {0}" -f $svc.Status)
    Write-Host ("StartType  : {0}" -f $svc.StartType)
    if ($svc.Status -eq "Running") { Ok "sshd は起動中" }
    else {
        Fail "sshd が停止中"
        Write-Host "  → 修正: Start-Service sshd"
    }
    if ($svc.StartType -ne "Automatic") {
        Warn "自動起動が無効。再起動後に止まります"
        Write-Host "  → 修正: Set-Service -Name sshd -StartupType Automatic"
    } else { Ok "自動起動 (Automatic) 設定済み" }
    # 待受ポート確認
    $port = Get-NetTCPConnection -State Listen -LocalPort 22 -ErrorAction SilentlyContinue
    if ($port) { Ok "TCP 22 を待受中" } else { Warn "TCP 22 の待受が確認できません" }
} else {
    Fail "sshd サービスが存在しません（OpenSSH Server未導入の可能性）"
}

# ------------------------------------------------------------
Section "3. Windows Defender Firewall がSSHを許可しているか"
$rules = Get-NetFirewallRule -ErrorAction SilentlyContinue | Where-Object {
    $_.DisplayName -like "*OpenSSH*" -or $_.DisplayName -like "*SSH*"
}
if ($rules) {
    $rules | ForEach-Object {
        $pf = ($_ | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue)
        Write-Host ("{0} | Enabled={1} | Action={2} | Dir={3} | Port={4}" -f `
            $_.DisplayName, $_.Enabled, $_.Action, $_.Direction, $pf.LocalPort)
    }
    $allow = $rules | Where-Object { $_.Enabled -eq "True" -and $_.Action -eq "Allow" -and $_.Direction -eq "Inbound" }
    if ($allow) { Ok "受信SSHを許可するルールが有効" }
    else {
        Warn "有効な受信許可ルールが見つかりません"
        Write-Host '  → 修正: New-NetFirewallRule -Name sshd -DisplayName "OpenSSH Server (sshd)" -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22'
    }
} else {
    Fail "SSH関連のFirewallルールが見つかりません"
    Write-Host '  → 修正: New-NetFirewallRule -Name sshd -DisplayName "OpenSSH Server (sshd)" -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22'
}

# ------------------------------------------------------------
Section "4. Docker Engine が起動しているか"
$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker) {
    docker --version
    docker info --format 'Server Version: {{.ServerVersion}} | OS/Arch: {{.OSType}}/{{.Architecture}}' 2>$null
    if ($LASTEXITCODE -eq 0) { Ok "Docker デーモンに接続OK" }
    else {
        Fail "Docker デーモンに接続できません（Docker Desktop未起動の可能性）"
        Write-Host "  → 修正: Docker Desktop を起動してください"
    }
} else {
    Fail "docker コマンドが見つかりません"
    Write-Host "  → 修正: Docker Desktop をインストールしてください"
}

# ------------------------------------------------------------
Section "5. docker compose が利用可能か"
docker compose version 2>$null
if ($LASTEXITCODE -eq 0) { Ok "docker compose (v2) 利用可能" }
else {
    Warn "docker compose が利用できません"
    Write-Host "  → 旧形式の docker-compose も確認:"
    docker-compose --version 2>$null
}

# ------------------------------------------------------------
Section "6. NVIDIA GPU が認識されているか"
$smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($smi) {
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
    if ($LASTEXITCODE -eq 0) { Ok "ホストでGPU認識OK" }
} else {
    Fail "nvidia-smi が見つかりません（NVIDIAドライバ未導入の可能性）"
}

Write-Host ""
Section "6b. Docker コンテナ内からのGPUアクセス（任意）"
Write-Host "次のコマンドでコンテナ内のGPUアクセスを確認できます:" -ForegroundColor Gray
Write-Host "  docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi" -ForegroundColor Gray

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host " チェック完了" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
