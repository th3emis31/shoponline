@echo off
REM NOVAHAUS: stop the local shop (backend on port 8000, storefront on port 3000).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-local.ps1" %*
