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

# Fallback (servers from older runs, or anything run-local's PIDs missed): whoever
# listens on 8000/3000. On Windows the backend is a chain of python processes
# (venv launcher -> reloader -> worker) that can all hold the port, so walk UP to
# the top-most shop process and stop that whole tree. Repeat until ports are free.
function Get-TopShopAncestor([int]$procId) {
  $top = $procId
  for ($i = 0; $i -lt 10; $i++) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $top" -ErrorAction SilentlyContinue
    if (-not $proc) { break }
    $parent = Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.ParentProcessId)" -ErrorAction SilentlyContinue
    if (-not $parent) { break }
    $pname = [System.IO.Path]::GetFileNameWithoutExtension($parent.Name).ToLower()
    if ($pname -notmatch $AllowedPattern) { break }   # stop at explorer/powershell/etc.
    $top = [int]$parent.ProcessId
  }
  return $top
}

if ($IsWin -and (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) {
  for ($round = 0; $round -lt 3; $round++) {
    $owners = @(Get-NetTCPConnection -LocalPort 8000, 3000 -State Listen -ErrorAction SilentlyContinue |
      Select-Object -ExpandProperty OwningProcess -Unique)
    if ($owners.Count -eq 0) { break }
    foreach ($o in $owners) {
      $p = Get-Process -Id ([int]$o) -ErrorAction SilentlyContinue
      if ($p -and $p.ProcessName.ToLower() -match $AllowedPattern) {
        Stop-Tree (Get-TopShopAncestor ([int]$o))
        Stop-Tree ([int]$o)   # in case it was not under that ancestor
        $stopped = $true
      } elseif ($p) {
        Write-Host "Port is used by $($p.ProcessName) (PID $o), which is not a shop process; leaving it alone."
      }
    }
    Start-Sleep -Seconds 2
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
