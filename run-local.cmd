@echo off
REM NOVAHAUS: set up and start the whole shop locally on Windows.
REM Usage: double-click, or run "run-local.cmd" from Command Prompt in this folder.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run-local.ps1" %*
if errorlevel 1 (
  echo.
  echo Setup failed - read the message above.
  pause
  exit /b 1
)
