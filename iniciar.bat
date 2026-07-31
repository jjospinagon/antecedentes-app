@echo off
title Certificados de Antecedentes
color 0B
echo ============================================================
echo   CERTIFICADOS DE ANTECEDENTES - corriendo desde tu PC
echo ============================================================
echo.

REM Verificar que Docker este disponible
where docker >nul 2>nul
if errorlevel 1 (
  echo [X] No se encontro Docker.
  echo.
  echo Instala Docker Desktop desde:
  echo   https://www.docker.com/products/docker-desktop/
  echo Abrelo y espera a que diga "Engine running", luego vuelve a
  echo hacer doble clic en este archivo.
  echo.
  pause
  exit /b 1
)

echo Encendiendo la app... la PRIMERA vez tarda 5-10 minutos.
echo Cuando veas "Uvicorn running on" ya esta lista.
echo.
echo   En este PC:   http://localhost:8000
echo   En el celular: http://[la-IP-de-tu-PC]:8000   (mismo wifi)
echo.
echo Para apagarla, cierra esta ventana.
echo ------------------------------------------------------------
echo.

docker compose up --build

echo.
echo La app se detuvo. Puedes cerrar esta ventana.
pause
