@echo off
title SIRIO - Rede da Unidade
cd /d "%~dp0"
if errorlevel 1 (
  pause
  exit /b
)
where python >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado neste computador.
  echo Instale em https://www.python.org/downloads/
  echo IMPORTANTE: na instalacao, marque "Add Python to PATH".
  pause
  exit /b 1
)
echo Iniciando o SIRIO com conexao HTTPS em modo REDE DA UNIDADE...
python sirio.py rede
pause
