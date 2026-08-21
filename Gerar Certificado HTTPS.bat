@echo off
title SIRIO - Gerar certificado HTTPS
cd /d "%~dp0"

echo ============================================================
echo  SIRIO - Certificado HTTPS do computador principal
echo ============================================================
echo.
echo  Execute este arquivo SOMENTE no computador principal
echo  (o servidor). Os computadores clientes nao precisam dele.
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado neste computador.
  echo Instale em https://www.python.org/downloads/
  echo IMPORTANTE: na instalacao, marque "Add Python to PATH".
  pause
  exit /b
)

python -m pip install cryptography --disable-pip-version-check --quiet
if errorlevel 1 (
  echo Nao foi possivel instalar o componente para gerar o certificado.
  echo Conecte este computador a internet e tente novamente.
  pause
  exit /b
)

if exist "certificados\sirio-chave-privada.pem" goto JA_EXISTE

python sirio_gerar_certificado.py
echo.
echo Anote o endereco mostrado acima. E o endereco que os
echo computadores clientes devem digitar no navegador.
pause
exit /b

:JA_EXISTE
echo  ATENCAO: este computador JA TEM um certificado.
echo.
echo  Gerar um novo certificado e necessario apenas quando:
echo    - o nome do computador principal mudou; ou
echo    - o endereco IP do computador principal mudou; ou
echo    - o SIRIO passou a rodar em outro computador; ou
echo    - o certificado atual venceu (validade de 3 anos).
echo.
echo  IMPORTANTE: ao gerar um novo certificado, o antigo deixa de
echo  valer. Todos os computadores clientes vao voltar a mostrar
echo  aviso de seguranca ate que o novo arquivo
echo  certificados\sirio-certificado.cer seja instalado neles.
echo.
set /p RESP="  Gerar um novo certificado e substituir o atual? (S/N): "
if /i not "%RESP%"=="S" (
  echo.
  echo  Nada foi alterado. O certificado atual continua valendo.
  pause
  exit /b
)

echo.
echo  Guardando copia do certificado antigo...
for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set SELO=%%c-%%b-%%a
set DESTINO=certificados\anterior_%SELO%
if not exist "%DESTINO%" mkdir "%DESTINO%"
copy /y "certificados\sirio-chave-privada.pem" "%DESTINO%\" >nul 2>nul
copy /y "certificados\sirio-certificado.pem" "%DESTINO%\" >nul 2>nul
copy /y "certificados\sirio-certificado.cer" "%DESTINO%\" >nul 2>nul
echo  Copia guardada em %DESTINO%
echo.

python sirio_gerar_certificado.py --substituir
echo.
echo ============================================================
echo  PROXIMO PASSO OBRIGATORIO
echo ============================================================
echo  Copie o arquivo certificados\sirio-certificado.cer para
echo  CADA computador cliente e instale novamente, seguindo o
echo  Manual de Instalacao em Rede (secao 6).
echo  Ate isso ser feito, os clientes verao aviso de seguranca.
echo ============================================================
pause
