@echo off
title Sistema de Vigilancia y Escaneo con Dron - Iniciador Unificado
echo =======================================================================
echo    INICIANDO SISTEMA DE VIGILANCIA Y ESCANEO CON DRON (3D WEBOTS)
echo =======================================================================
echo.

:: 1. Iniciar Backend FastAPI
echo [1/3] Iniciando Servidor Backend (FastAPI)...
start "Backend FastAPI" /min cmd /c "cd /d "%~dp0" && python backend\run.py"

:: 2. Iniciar Frontend Dashboard React
echo [2/3] Iniciando Dashboard Frontend (React + Vite)...
start "Frontend React" /min cmd /c "cd /d "%~dp0frontend" && npm run dev"

:: Esperar 3 segundos a que los servidores inicialicen
timeout /t 3 /nobreak >nul

:: Abrir el navegador web en el Dashboard
start http://localhost:5173

:: 3. Abrir la Simulación 3D en Webots
echo [3/3] Abriendo Simulación 3D en Webots...
cd /d "%~dp0simulation\worlds"
if exist "%LOCALAPPDATA%\Programs\Webots\msys64\mingw64\bin\webotsw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Webots\msys64\mingw64\bin\webotsw.exe" --mode=realtime inspection_zone.wbt
) else if exist "C:\Program Files\Webots\msys64\mingw64\bin\webotsw.exe" (
    start "" "C:\Program Files\Webots\msys64\mingw64\bin\webotsw.exe" --mode=realtime inspection_zone.wbt
) else (
    start "" webots inspection_zone.wbt
)

echo.
echo =======================================================================
echo  ¡SISTEMA INICIADO CON ÉXITO!
echo  - Dashboard Web: http://localhost:5173
echo  - API Backend:   http://127.0.0.1:8000
echo =======================================================================
echo.
pause
