@echo off
REM Back up the NOVAHAUS database and check the backup restores.
REM   backup.cmd                 make + verify a backup (saved in backend\backups)
REM   backup.cmd --list          list backups
REM   backup.cmd --verify FILE   check a backup
REM   backup.cmd --restore FILE --yes   put a backup back (stop the shop first)
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  echo Run run-local.cmd once first, so Python and the database are set up.
  exit /b 1
)
".venv\Scripts\python.exe" -m app.backup %*
