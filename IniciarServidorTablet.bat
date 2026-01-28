@echo off
setlocal

REM Inicia el servidor Flask (modo tablet/LAN) en segundo plano.
REM - Usa el Python que esté configurado en esta PC (PATH / Python Launcher)
REM - Desacoplado: aunque cierres esta ventana, el server sigue corriendo

for %%I in ("%~dp0.") do set "ROOT=%%~fI"

if not exist "%ROOT%\instance" mkdir "%ROOT%\instance" >nul 2>nul

set "PORT=8000"
set "HOST=0.0.0.0"

REM Elegir el comando de Python.
REM - Si existe .venv local, úsalo (más confiable).
REM - Si no, usa pyw/pythonw/python del sistema.
set "PY_CMD="
set "PY_ARGS="

if exist "%ROOT%\.venv\Scripts\pythonw.exe" (
	set "PY_CMD=%ROOT%\.venv\Scripts\pythonw.exe"
) else if exist "%ROOT%\.venv\Scripts\python.exe" (
	set "PY_CMD=%ROOT%\.venv\Scripts\python.exe"
)

if "%PY_CMD%"=="" (
	where pyw >nul 2>nul
	if %ERRORLEVEL%==0 (
		set "PY_CMD=pyw"
		set "PY_ARGS=-3"
	)
)

if "%PY_CMD%"=="" (
	where pythonw >nul 2>nul
	if %ERRORLEVEL%==0 set "PY_CMD=pythonw"
)

if "%PY_CMD%"=="" set "PY_CMD=python"

REM Arranca desacoplado (no /b). Si PY_CMD es pyw/pythonw no se verá ninguna ventana.
pushd "%ROOT%" >nul
if /i "%PY_CMD%"=="pyw" (
	start "Inventarios Server" %PY_CMD% %PY_ARGS% run_server.py --host %HOST% --port %PORT% --ui
) else (
	start "Inventarios Server" "%PY_CMD%" run_server.py --host %HOST% --port %PORT% --ui
)
popd >nul



REM Obtener IPv4 activa
for /f "tokens=2 delims=:" %%A in ('
    ipconfig ^| findstr /R /C:"IPv4"
') do (
    set "LOCAL_IP=%%A"
    goto :got_ip
)

:got_ip
set "LOCAL_IP=%LOCAL_IP: =%"

REM Esperar un poco a que Flask arranque
timeout /t 2 /nobreak >nul

REM Abrir navegador
start "" "http://desktop-hjl8q77:8000/store.html"
exit /b 0