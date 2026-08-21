@echo off
title SIRIO - Preparar pacote para outra unidade
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado neste computador.
  echo Instale em https://www.python.org/downloads/
  pause
  exit /b
)
python sirio_preparar_distribuicao.py
pause
