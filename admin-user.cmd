@echo off
REM Manage NOVAHAUS admin logins. Examples:
REM   admin-user.cmd create you@example.com --role owner
REM   admin-user.cmd create helper@example.com --role staff
REM   admin-user.cmd list
REM   admin-user.cmd reset-password you@example.com
REM   admin-user.cmd disable helper@example.com
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  echo Run run-local.cmd once first, so Python and the database are set up.
  exit /b 1
)
".venv\Scripts\python.exe" -m app.admin_users %*
