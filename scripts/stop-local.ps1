# Stop the NOVAHAUS servers started by run-local. Only stops the processes
# run-local started (recorded in .run-local.pids) or, as a fallback, the
# python/node processes listening on ports 8000 and 3000. Nothing else.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $Root ".run-local.pids"
$IsWin = ($env:OS -eq "Windows_NT")
# Process names run-local starts: python(.exe), npm (runs via cmd.exe on Windows), node.
$AllowedPattern = "^(python|py|node|npm|cmd)"

function Stop-Tree([int]$procId, [switch]$Child) {
  $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
  if (-not $p) { return }
  # The name check guards the top process only; its children were started by it.
  if (-not $Child -and $p.ProcessName.ToLower() -notmatch $AllowedPattern) {
    Write-Host "Skipping PID $procId ($($p.ProcessName)): not a shop process."
    return
  }
  Write-Host "Stopping $($p.ProcessName) (PID $procId)"
  if ($IsWin) {
    & taskkill.exe /PID $procId /T /F *> $null   # /T = include child processes
  } else {
    # Non-Windows (used for testing): stop children first, then the process.
    $kids = @(& ps -o pid= --ppid $procId 2>$null | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    foreach ($k in $kids) { Stop-Tree ([int]$k) -Child }
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
  }
}

function Test-PortInUse($port) {
  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $task = $client.ConnectAsync("127.0.0.1", $port)
    return ($task.Wait(1000) -and $client.Connected)
  } catch { return $false } finally { $client.Close() }
}

$stopped = $false
if (Test-Path $PidFile) {
  foreach ($line in Get-Content $PidFile) {
    if ($line -match "^\d+$") { Stop-Tree ([int]$line); $stopped = $true }
  }
  Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

# Fallback (e.g. servers started by an older run-local): whoever listens on 8000/3000.
if ($IsWin -and (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) {
  foreach ($port in 8000, 3000) {
    $owners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
      Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($o in $owners) { Stop-Tree ([int]$o); $stopped = $true }
  }
}

Start-Sleep -Seconds 2
$still = @(8000, 3000 | Where-Object { Test-PortInUse $_ })
if ($still.Count -gt 0) {
  Write-Host ""
  Write-Host "Port(s) $($still -join ', ') still in use. Close the NOVAHAUS server windows by hand" -ForegroundColor Yellow
  Write-Host "(titled python.exe / npm / node), or restart the PC."
  exit 1
}
if ($stopped) { Write-Host "NOVAHAUS stopped." -ForegroundColor Green } else { Write-Host "NOVAHAUS was not running." }
