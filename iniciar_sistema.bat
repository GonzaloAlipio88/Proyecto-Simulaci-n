```bat
@echo off
setlocal
title Sistema de Vigilancia y Escaneo con Dron

cd /d "%~dp0"

echo ============================================================
echo   SISTEMA DE VIGILANCIA Y ESCANEO CON DRON
echo ============================================================
echo.

:: Verificar archivos necesarios
if not exist "backend\.venv312\Scripts\python.exe" (
    echo ERROR: No se encontro Python 3.12.
    pause
    exit /b 1
)

if not exist "backend\run.py" (
    echo ERROR: No se encontro backend\run.py.
    pause
    exit /b 1
)

if not exist "frontend\package.json" (
    echo ERROR: No se encontro frontend\package.json.
    pause
    exit /b 1
)

if not exist "simulation\worlds\inspection_zone.wbt" (
    echo ERROR: No se encontro el mundo de Webots.
    pause
    exit /b 1
)

echo Archivos necesarios encontrados.
echo.

:: Comprobar backend
echo [1/3] Comprobando backend...

powershell -NoProfile -Command "$c = Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue; if ($c) { exit 0 } else { exit 1 }"

if errorlevel 1 (
    echo Iniciando backend...
    start "Backend FastAPI" "%ComSpec%" /k "cd /d ""%~dp0backend"" && ""%~dp0backend\.venv312\Scripts\python.exe"" run.py"
) else (
    echo Backend ya activo. No se iniciara otra instancia.
)

:: Comprobar frontend
echo.
echo [2/3] Comprobando frontend...

powershell -NoProfile -Command "$c = Get-NetTCPConnection -State Listen -LocalPort 5173 -ErrorAction SilentlyContinue; if ($c) { exit 0 } else { exit 1 }"

if errorlevel 1 (
    echo Iniciando frontend...
    start "Frontend React" "%ComSpec%" /k "cd /d ""%~dp0frontend"" && npm run dev"
) else (
    echo Frontend ya activo. No se iniciara otra instancia.
)

:: Abrir dashboard
echo.
echo Abriendo dashboard...
start "" "http://localhost:5173"

:: Abrir Webots
echo.
echo [3/3] Abriendo simulacion Webots...

if exist "%LOCALAPPDATA%\Programs\Webots\msys64\mingw64\bin\webotsw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Webots\msys64\mingw64\bin\webotsw.exe" --mode=realtime "%~dp0simulation\worlds\inspection_zone.wbt"
) else if exist "C:\Program Files\Webots\msys64\mingw64\bin\webotsw.exe" (
    start "" "C:\Program Files\Webots\msys64\mingw64\bin\webotsw.exe" --mode=realtime "%~dp0simulation\worlds\inspection_zone.wbt"
) else (
    start "" webots --mode=realtime "%~dp0simulation\worlds\inspection_zone.wbt"
)

echo.
echo Solicitudes de inicio enviadas.
echo Dashboard: http://localhost:5173
echo API:       http://127.0.0.1:8000
echo.
pause
```