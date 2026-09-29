# NOVAHAUS local runner (Windows PowerShell 5.1+ and PowerShell 7).
# Safe to re-run: it never deletes data, it only creates what is missing.
#   -SetupOnly   install + migrate + seed, but don't start the servers
#   -NoBrowser   don't open the browser at the end
# To use PostgreSQL instead of the default SQLite file, edit DATABASE_URL in backend\.env.
param([switch]$SetupOnly, [switch]$NoBrowser)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$IsWin = ($env:OS -eq "Windows_NT")

function Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host ""; Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }
function Run($exe, [string[]]$argList) {
  & $exe @argList
  if ($LASTEXITCODE -ne 0) { Fail "Command failed: $exe $($argList -join ' ')" }
}

# ---------- 1. Prerequisites ----------
Step "Checking prerequisites"
$Python = $null
foreach ($cand in @(@("py", "-3"), @("python"), @("python3"))) {
  $exe = $cand[0]
  if (Get-Command $exe -ErrorAction SilentlyContinue) {
    $pyArgs = @($cand | Select-Object -Skip 1)
    $ver = $null
    # try/catch: the Windows Store "python" stub writes errors instead of running.
    try { $ver = & $exe @pyArgs -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null } catch { $ver = $null }
    if ($LASTEXITCODE -eq 0 -and $ver) {
      $parts = $ver.Trim().Split(".")
      if ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 11) { $Python = $cand; break }
    }
  }
}
if (-not $Python) {
  $hint = "Install it with:  winget install -e --id Python.Python.3.12`n  (or from https://www.python.org/downloads/ and tick 'Add python.exe to PATH')`nThen CLOSE this window, open a new Command Prompt and run run-local.cmd again."
  $stub = Get-Command python -ErrorAction SilentlyContinue
  if ($stub -and $stub.Source -like "*WindowsApps*") {
    $hint = "Only the Microsoft Store shortcut for 'python' was found, not a real Python.`n" + $hint
  }
  Fail "Python 3.11+ not found.`n$hint"
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Fail "Node.js not found.`nInstall it with:  winget install -e --id OpenJS.NodeJS.LTS`n  (or the LTS version from https://nodejs.org/)`nThen CLOSE this window, open a new Command Prompt and run run-local.cmd again."
}
$nodeMajor = [int]((& node -p "process.versions.node.split('.')[0]").Trim())
if ($nodeMajor -lt 20) { Fail "Node.js 20+ required (found $nodeMajor). Install the LTS version from https://nodejs.org/." }
$npm = "npm"
if ($IsWin) { $npm = "npm.cmd" }
Write-Host "Python: $($Python -join ' ')   Node: v$nodeMajor"

# ---------- 2. Backend ----------
Step "Backend: virtual environment and packages"
$venv = Join-Path $Backend ".venv"
if (-not (Test-Path $venv)) {
  $pyArgs = @($Python | Select-Object -Skip 1) + @("-m", "venv", $venv)
  Run $Python[0] $pyArgs
}
$VenvPy = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $VenvPy)) { $VenvPy = Join-Path $venv "bin/python" }
Run $VenvPy @("-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", (Join-Path $Backend "requirements.txt"))

Step "Backend: configuration"
$envFile = Join-Path $Backend ".env"
if (-not (Test-Path $envFile)) {
  $bytes = New-Object byte[] 24
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  $token = -join ($bytes | ForEach-Object { $_.ToString("x2") })
  $lines = Get-Content (Join-Path $Backend ".env.example") | ForEach-Object {
    if ($_ -match "^ADMIN_TOKEN=\s*$") { "ADMIN_TOKEN=$token" } else { $_ }
  }
  Set-Content -Path $envFile -Value $lines -Encoding ASCII
  Write-Host "Created backend\.env with a new random ADMIN_TOKEN (SQLite database, payments off)."
} else {
  Write-Host "Using existing backend\.env"
}
$adminToken = ""
foreach ($line in Get-Content $envFile) { if ($line -match "^ADMIN_TOKEN=(.*)$") { $adminToken = $Matches[1].Trim() } }

Step "Backend: database migrations and products"
Push-Location $Backend
try {
  Run $VenvPy @("-m", "alembic", "upgrade", "head")
  Run $VenvPy @("-m", "app.seed")
  $admins = & $VenvPy -m app.admin_users list
  $NeedsAdmin = ($admins -join " ") -match "No admin accounts"
} finally { Pop-Location }

# ---------- 3. Storefront ----------
Step "Storefront: packages"
if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
  Push-Location $Frontend
  try { Run $npm @("ci", "--no-audit", "--no-fund") } finally { Pop-Location }
} else {
  Write-Host "node_modules present (delete the folder to force a clean reinstall)."
}

if ($SetupOnly) {
  Step "Setup complete (servers not started because -SetupOnly was given)"
  exit 0
}

# ---------- 4. Start ----------
. (Join-Path $PSScriptRoot "common.ps1")

# Use the usual ports; if another program already uses one, leave that program
# alone and move the shop to the next free port.
function Resolve-ShopPort([int]$preferred, [string]$label) {
  $skipped = @()
  for ($p = $preferred; $p -le $preferred + 50; $p++) {
    if (-not (Test-PortInUse $p)) {
      if ($skipped.Count -gt 0) {
        Write-Host "Port(s) $($skipped -join '; ') in use by other programs (not the shop) - leaving them alone. The $label will use port $p." -ForegroundColor Yellow
      }
      return $p
    }
    $owners = @(Get-PortOwners $p)
    foreach ($o in $owners) {
      if ((Get-ShopAnchor $o) -gt 0) {
        Fail ("The shop is already running (port $p).`n" +
              "Run stop-local.cmd first, then run-local.cmd again.`n" +
              "(Setup and database updates above were applied; only the start was skipped.)")
      }
    }
    $who = ($owners | ForEach-Object { "$(Get-ProcName $_) PID $_" }) -join ", "
    if (-not $who) { $who = "another program" }
    $skipped += "$p ($who)"
  }
  Fail "No free port found near $preferred for the $label."
}
$BePort = Resolve-ShopPort 8000 "backend"
$FePort = Resolve-ShopPort 3000 "shop"
$ShopUrl = "http://localhost:$FePort"
$ApiUrl = "http://localhost:$BePort"

Step "Starting backend ($ApiUrl) and shop ($ShopUrl)"
# Child processes inherit these: the shop finds the backend, and links/redirects use the right port.
$env:API_URL = $ApiUrl
$env:PUBLIC_BASE_URL = $ShopUrl
$env:SITE_URL = $ShopUrl
# --app-dir puts the shop folder in the process command line, which is how
# stop-local recognises (and only stops) the shop's own processes.
$uvicornArgs = @("-m", "uvicorn", "app.main:app", "--app-dir", "`"$Backend`"", "--port", "$BePort")
$be = Start-Process -FilePath $VenvPy -ArgumentList $uvicornArgs -WorkingDirectory $Backend -PassThru
$fe = Start-Process -FilePath $npm -ArgumentList @("run", "dev", "--", "-p", "$FePort") -WorkingDirectory $Frontend -PassThru
# Remember what we started, so stop-local.cmd stops exactly these (and their children).
Set-Content -Path $PidFile -Value @($be.Id, $fe.Id) -Encoding ASCII
Set-Content -Path $PortsFile -Value @("backend=$BePort", "frontend=$FePort") -Encoding ASCII

function Wait-Url($url, $seconds) {
  $deadline = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
      if ($r.StatusCode -eq 200) { return $true }
    } catch { Start-Sleep -Seconds 1 }
  }
  return $false
}
if (-not (Wait-Url "$ApiUrl/api/health" 60)) { Fail "Backend did not start. Check its window for errors." }
if (-not (Wait-Url "$ShopUrl/shop" 120)) { Fail "Shop did not start. Check its window for errors." }

Write-Host ""
Write-Host "NOVAHAUS is running:" -ForegroundColor Green
Write-Host "  Shop:      $ShopUrl"
Write-Host "  Admin:     $ShopUrl/admin"
if ($NeedsAdmin) {
  Write-Host ""
  Write-Host "  Create your personal owner login (recommended), in this folder:" -ForegroundColor Yellow
  Write-Host "    admin-user.cmd create you@example.com --role owner"
  Write-Host "  Until then you can sign in with the shared token: $adminToken"
}
Write-Host "  API docs:  $ApiUrl/docs"
Write-Host ""
Write-Host "To stop: run stop-local.cmd (stops only the shop)."
if (-not $NoBrowser -and $IsWin) { Start-Process $ShopUrl }
