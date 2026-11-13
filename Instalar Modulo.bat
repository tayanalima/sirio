@echo off
cd /d "%~dp0"
echo Feche o SIRIO antes de continuar.
pause
python -m pip install python-docx Pillow
if errorlevel 1 (
 echo Falha ao instalar dependencias. Verifique sua conexao e o Python.
 pause
 exit /b 1
)
python instalar_modulo.py
if errorlevel 1 (
 pause
 exit /b 1
)
echo Abra o SIRIO normalmente e acesse Comunicacoes de servico.
pause
