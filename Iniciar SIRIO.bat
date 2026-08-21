@echo off
title SIRIO
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado neste computador.
  echo Instale em https://www.python.org/downloads/
  echo IMPORTANTE: na instalacao, marque a caixinha "Add Python to PATH".
  pause
  exit /b
)
echo Iniciando o SIRIO com conexao HTTPS... o navegador abrira sozinho em instantes.
python sirio.py
pause
