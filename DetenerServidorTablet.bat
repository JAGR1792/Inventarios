@echo off
setlocal

REM Detiene el servidor tablet (mata el proceso que está escuchando en el puerto 8000).
REM Si cambiaste el puerto, ajusta PORT.

set "PORT=8000"

REM Usamos PowerShell para encontrar el PID que escucha el puerto y matarlo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$port=%PORT%; $pids=@(); try { $pids=(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue).OwningProcess | Select-Object -Unique } catch { $pids=@() }; if(-not $pids -or $pids.Count -eq 0){ Write-Host ('No hay servidor escuchando en el puerto {0}.' -f $port); exit 0 }; foreach($procId in $pids){ Write-Host ('Deteniendo servidor (PID={0}) en puerto {1}...' -f $procId,$port); Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue }; Write-Host 'Listo.'"

exit /b %ERRORLEVEL%
