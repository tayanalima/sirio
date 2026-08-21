@echo off
title SIRIO - Ativar importacao de BO (PDF)
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado. Instale em https://www.python.org/downloads/
  echo IMPORTANTE: marque "Add Python to PATH" na instalacao.
  pause
  exit /b
)
echo Instalando o componente de leitura de PDF (pypdf)...
echo Isso so precisa ser feito uma vez e exige internet neste momento.
python -m pip install --upgrade pip
python -m pip install pypdf
if errorlevel 1 (
  echo.
  echo Nao foi possivel instalar. Verifique a conexao com a internet.
) else (
  echo.
  echo Pronto! Feche e abra o SIRIO. O menu "Importar BO" estara disponivel.
)
pause
