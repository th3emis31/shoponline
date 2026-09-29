@echo off
REM Manage NOVAHAUS admin logins. Examples:
REM   admin-user.cmd create you@example.com --role owner
REM   admin-user.cmd create helper@example.com --role staff
REM   admin-user.cmd list
REM   admin-user.cmd reset-password you@example.com
REM   admin-user.cmd disable helper@example.com
setlocal
REM pushd/popd: return to the folder you started in when done.
pushd "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  echo Run run-local.cmd once first, so Python and the database are set up.
  popd
  exit /b 1
)
".venv\Scripts\python.exe" -m app.admin_users %*
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%
