@echo off
title SIRIO - Rede da Unidade
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado. Instale em https://www.python.org/downloads/
  echo IMPORTANTE: marque "Add Python to PATH" na instalacao.
  pause
  exit /b
)
echo Iniciando o SIRIO com conexao HTTPS em modo REDE DA UNIDADE...
python sirio.py rede
pause
