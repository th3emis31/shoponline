# Shared helpers for run-local.ps1 and stop-local.ps1 (Windows PowerShell 5.1+ and PowerShell 7).
# A process counts as "the shop" only if it, or one of its parent processes, was
# started from this shoponline folder. Anything else is never stopped.

$ShopRoot = Split-Path -Parent $PSScriptRoot
$IsWin = ($env:OS -eq "Windows_NT")
$PortsFile = Join-Path $ShopRoot ".run-local.ports"
$PidFile = Join-Path $ShopRoot ".run-local.pids"

function Get-CmdLine([int]$procId) {
  try {
    if ($IsWin) {
      $p = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
      if ($p) { return [string]$p.CommandLine }
      return $null
    }
    $f = "/proc/$procId/cmdline"
    if (Test-Path $f) { return ((Get-Content $f -Raw) -replace "`0", " ") }
  } catch { }
  return $null
}

function Get-ParentId([int]$procId) {
  try {
    if ($IsWin) {
      $p = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
      if ($p) { return [int]$p.ParentProcessId }
      return 0
    }
    $f = "/proc/$procId/stat"
    if (Test-Path $f) {
      $stat = Get-Content $f -Raw
      # Fields after ") " are: state ppid ...
      return [int](($stat.Substring($stat.LastIndexOf(")") + 2)).Split(" ")[1])
    }
  } catch { }
  return 0
}

function Test-FromShopFolder([string]$cmd) {
  if (-not $cmd) { return $false }
  $c = $cmd.ToLower().Replace("\", "/")
  return $c.Contains($ShopRoot.ToLower().Replace("\", "/"))
}

# Highest process in the parent chain that was started from the shop folder
# (0 if none). Stopping that one with its children stops the whole shop server.
function Get-ShopAnchor([int]$procId) {
  $anchor = 0
  $id = $procId
  for ($i = 0; $i -lt 8 -and $id -gt 1; $i++) {
    if (Test-FromShopFolder (Get-CmdLine $id)) { $anchor = $id }
    $id = Get-ParentId $id
  }
  return $anchor
}

function Test-PortInUse([int]$port) {
  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $task = $client.ConnectAsync("127.0.0.1", $port)
    return ($task.Wait(1000) -and $client.Connected)
  } catch { return $false } finally { $client.Close() }
}

function Get-PortOwners([int]$port) {
  try {
    if ($IsWin) {
      return @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { [int]$_ })
    }
    $found = @()
    if (Get-Command lsof -ErrorAction SilentlyContinue) {
      $found = @(& lsof -t "-iTCP:$port" -sTCP:LISTEN 2>$null | ForEach-Object { [int]$_ })
    }
    if ($found.Count -eq 0 -and (Get-Command fuser -ErrorAction SilentlyContinue)) {
      $found = @((& fuser -n tcp $port 2>$null) -split "\s+" | Where-Object { $_ -match "^\d+$" } | ForEach-Object { [int]$_ })
    }
    return @($found | Select-Object -Unique)
  } catch { }
  return @()
}

function Get-ProcName([int]$procId) {
  try {
    $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($p -and $p.ProcessName) { return $p.ProcessName }
  } catch { }
  return "unknown"
}

# Stop a process and all its children. Never throws (it may already have exited).
function Stop-ProcessTree([int]$procId) {
  try {
    $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if (-not $p -or $p.HasExited) { return $false }
    Write-Host "Stopping $(Get-ProcName $procId) (PID $procId)"
    if ($IsWin) {
      & taskkill.exe /PID $procId /T /F *> $null
    } else {
      $kids = @(& ps -o pid= --ppid $procId 2>$null | ForEach-Object { $_.Trim() } | Where-Object { $_ })
      foreach ($k in $kids) { [void](Stop-ProcessTree ([int]$k)) }
      Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
    return $true
  } catch { return $false }
}

function Read-ShopPorts {
  $ports = @{ backend = 8000; frontend = 3000 }
  if (Test-Path $PortsFile) {
    foreach ($line in Get-Content $PortsFile) {
      if ($line -match "^(backend|frontend)=(\d+)$") { $ports[$Matches[1]] = [int]$Matches[2] }
    }
  }
  return $ports
}
