param(
  [string]$HostAlias = "gkguard-c1",
  [string]$RepoPath = "/home/speng/projects/GKGuard",
  [string]$Branch = "main",
  [string]$CondaSh = "/home/speng/miniforge3/etc/profile.d/conda.sh",
  [string]$CondaEnv = "campusvision-c1",
  [int]$Port = 8000,
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
  param([string]$Message, [scriptblock]$Command)
  Write-Host "==> $Message"
  & $Command
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed: $Message"
  }
}

$installCommand = if ($SkipInstall) {
  "echo '[deploy] dependency install skipped'"
} else {
  "python -m pip install -r requirements.txt"
}

$remoteScript = @'
set -euo pipefail

REPO_PATH='__REPO_PATH__'
BRANCH='__BRANCH__'
CONDA_SH='__CONDA_SH__'
CONDA_ENV='__CONDA_ENV__'
PORT='__PORT__'
SERVICE_DIR="$REPO_PATH/services/campusvision-c1"

echo "[deploy] repo: $REPO_PATH"
cd "$REPO_PATH"
git fetch --tags origin
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

cd "$SERVICE_DIR"
source "$CONDA_SH"
conda activate "$CONDA_ENV"
__INSTALL_COMMAND__

mkdir -p logs
pkill -f '[u]vicorn app.main:app' || true
sleep 2

cat > /tmp/gkguard-start-campusvision-c1.sh <<EOS
#!/usr/bin/env bash
set -euo pipefail
cd "$SERVICE_DIR"
source "$CONDA_SH"
conda activate "$CONDA_ENV"
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi
python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
EOS
chmod +x /tmp/gkguard-start-campusvision-c1.sh
nohup /tmp/gkguard-start-campusvision-c1.sh > logs/campusvision-c1.log 2>&1 &

echo "[deploy] waiting for health"
for i in {1..30}; do
  if curl -fsS "http://127.0.0.1:$PORT/health" >/tmp/gkguard-c1-health.json; then
    cat /tmp/gkguard-c1-health.json
    echo
    break
  fi
  sleep 1
  if [ "$i" -eq 30 ]; then
    echo "[deploy] health check failed"
    tail -80 logs/campusvision-c1.log || true
    exit 1
  fi
done

curl -fsS "http://127.0.0.1:$PORT/openapi.json" | grep -q 'query-faces'
echo "[deploy] CampusVision C1 is running on 127.0.0.1:$PORT"
'@

$remoteScript = $remoteScript.Replace("__REPO_PATH__", $RepoPath.Replace("'", "'\''")).Replace("__BRANCH__", $Branch.Replace("'", "'\''")).Replace("__CONDA_SH__", $CondaSh.Replace("'", "'\''")).Replace("__CONDA_ENV__", $CondaEnv.Replace("'", "'\''")).Replace("__PORT__", [string]$Port).Replace("__INSTALL_COMMAND__", $installCommand)
$remoteScript = $remoteScript -replace "`r`n", "`n" -replace "`r", "`n"

Invoke-CheckedCommand "Testing SSH alias $HostAlias" {
  ssh $HostAlias "echo ok"
}

Write-Host "==> Deploying CampusVision C1 on $HostAlias"
$sshProcessInfo = [System.Diagnostics.ProcessStartInfo]::new()
$sshProcessInfo.FileName = "ssh"
$sshProcessInfo.Arguments = "$HostAlias ""bash -s"""
$sshProcessInfo.RedirectStandardInput = $true
$sshProcessInfo.UseShellExecute = $false
$sshProcess = [System.Diagnostics.Process]::Start($sshProcessInfo)
$sshProcess.StandardInput.Write($remoteScript)
$sshProcess.StandardInput.Close()
$sshProcess.WaitForExit()
if ($sshProcess.ExitCode -ne 0) {
  throw "Remote deploy failed"
}

Write-Host "==> Done"
