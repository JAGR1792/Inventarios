param(
  [string]$Name = "InventariosPOS",
  [switch]$OneFile = $true,
  [switch]$Clean = $true
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "== Inventarios: build EXE ==" -ForegroundColor Cyan

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

# Web UI assets must be bundled for the embedded browser.
$addDataWeb = "inventarios\ui\web;inventarios\ui\web"
$addDataAssets = "assets;assets"

$modeArgs = @()
if ($OneFile) { $modeArgs += "--onefile" } else { $modeArgs += "--onedir" }

$cmd = @(
  $py, "-m", "PyInstaller",
  "--noconfirm",
  "--clean",
  "--windowed",
  "--name", $Name,
  "--add-data", $addDataWeb,
  "--add-data", $addDataAssets,
  "--collect-all", "webview"
) + $modeArgs

if ($hasIcon) {
  $cmd += @("--icon", $iconPath)
  Write-Host "Usando icono: $iconPath" -ForegroundColor Green
} else {
  Write-Host "Sin icono (pon assets\app.ico para personalizar)." -ForegroundColor Yellow
}

$cmd += "run_desktop.py"

Write-Host "\nEjecutando:" -ForegroundColor Cyan
Write-Host ($cmd -join " ")

& $cmd[0] $cmd[1..($cmd.Length-1)]

if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller falló con código $LASTEXITCODE"
}

Write-Host "\nOK. Revisa dist\\$Name\\ o dist\\$Name.exe" -ForegroundColor Green
