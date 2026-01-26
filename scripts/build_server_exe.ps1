param(
  [string]$Name = "InventariosServer",
  [bool]$OneFile = $true,
  [bool]$Clean = $false
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "== Inventarios: build SERVER EXE (tablet/LAN) ==" -ForegroundColor Cyan

if ($Clean) {
  if (Test-Path "$repoRoot\build") { Remove-Item "$repoRoot\build" -Recurse -Force }
  if (Test-Path "$repoRoot\dist") { Remove-Item "$repoRoot\dist" -Recurse -Force }
}

# Prefer venv python (more reproducible)
$venvPy = Join-Path $repoRoot ".venv\Scripts\python.exe"
$py = "python"
if (Test-Path $venvPy) {
  $py = $venvPy
  Write-Host "Usando venv: $py" -ForegroundColor Green
} else {
  Write-Host "Aviso: no se encontro .venv. Usando 'python' del sistema." -ForegroundColor Yellow
}

# Ensure deps
& $py -m pip install -r requirements.txt
& $py -m pip install -r requirements-dev.txt

$iconPath = Join-Path $repoRoot "assets\app.ico"
$hasIcon = Test-Path $iconPath

# Web UI assets must be bundled for LAN/tablet.
$addDataWeb = "inventarios\ui\web;inventarios\ui\web"
$addDataAssets = "assets;assets"

$modeArgs = @()
if ($OneFile) { $modeArgs += "--onefile" } else { $modeArgs += "--onedir" }

# NOTE: Use --windowed so non-technical users don't see a console.
# The server will show a MessageBox with the LAN URL when frozen.
$cmd = @(
  $py, "-m", "PyInstaller",
  "--noconfirm",
  "--clean",
  "--windowed",
  "--name", $Name,
  "--add-data", $addDataWeb,
  "--add-data", $addDataAssets
) + $modeArgs

if ($hasIcon) {
  $cmd += @("--icon", $iconPath)
  Write-Host "Usando icono: $iconPath" -ForegroundColor Green
}

$cmd += "run_server.py"

Write-Host "\nEjecutando:" -ForegroundColor Cyan
Write-Host ($cmd -join " ")

& $cmd[0] $cmd[1..($cmd.Length-1)]

if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller (server) falló con código $LASTEXITCODE"
}

Write-Host "\nOK. Revisa dist\\$Name\\ o dist\\$Name.exe" -ForegroundColor Green
