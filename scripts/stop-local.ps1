# Stop the NOVAHAUS shop. Only stops processes started from this shoponline
# folder (or recorded by run-local); every other program is left alone.
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")

$stopped = $false
$ports = Read-ShopPorts

# 1. Processes run-local recorded. A recorded PID is trusted only if it still
#    belongs to the shop (PIDs can be reused by other programs after a restart).
if (Test-Path $PidFile) {
  $written = (Get-Item $PidFile -Force).LastWriteTime
  foreach ($line in Get-Content $PidFile) {
    if ($line -notmatch "^\d+$") { continue }
    $id = [int]$line
    $p = Get-Process -Id $id -ErrorAction SilentlyContinue
    if (-not $p) { continue }
    $startedByRunLocal = $false
    try { $startedByRunLocal = ($p.StartTime -le $written.AddSeconds(5)) -and ($p.StartTime -ge $written.AddMinutes(-10)) } catch { }
    if ((Get-ShopAnchor $id) -gt 0 -or $startedByRunLocal) {
      if (Stop-ProcessTree $id) { $stopped = $true }
    } else {
      Write-Host "PID $id now belongs to another program ($(Get-ProcName $id)); leaving it alone."
    }
  }
  Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

# 2. Anything still listening on the shop's ports that comes from the shop folder
#    (e.g. servers started by an older version of run-local).
for ($round = 0; $round -lt 3; $round++) {
  $found = $false
  foreach ($port in @($ports.backend, $ports.frontend)) {
    foreach ($owner in (Get-PortOwners $port)) {
      $anchor = Get-ShopAnchor $owner
      if ($anchor -gt 0) {
        if (Stop-ProcessTree $anchor) { $stopped = $true; $found = $true }
        if (Stop-ProcessTree $owner) { $stopped = $true; $found = $true }
      } elseif ($round -eq 0) {
        Write-Host "Port $port is used by $(Get-ProcName $owner) (PID $owner), which is not the shop; leaving it alone."
      }
    }
  }
  if (-not $found) { break }
  Start-Sleep -Seconds 2
}

if ($stopped) { Write-Host "NOVAHAUS stopped." -ForegroundColor Green } else { Write-Host "NOVAHAUS was not running." }
Remove-Item $PortsFile -Force -ErrorAction SilentlyContinue
exit 0
