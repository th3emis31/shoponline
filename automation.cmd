@echo off
REM Run NOVAHAUS automation by hand. Examples:
REM   automation.cmd status              jobs, limits and last runs
REM   automation.cmd run                 run every job now
REM   automation.cmd run low_stock       run one job now
REM   automation.cmd report              show the latest daily report
setlocal
pushd "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  echo Run run-local.cmd once first, so Python and the database are set up.
  popd
  exit /b 1
)
".venv\Scripts\python.exe" -m app.automation_cli %*
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%
