@echo off
title SIRIO - Diagnostico de leitura do BO
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado neste computador.
  pause
  exit /b
)
python -m pip install pypdf --disable-pip-version-check --quiet
python sirio_diagnostico_bo.py %1
pause
