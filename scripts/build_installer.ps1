param(
  [string]$Name = "InstalarInventarios",
  [string]$AppExe = "dist\InventariosPOS.exe",
  [switch]$Clean = $true
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

# Prefer venv python
$venvPy = Join-Path $repoRoot ".venv\Scripts\python.exe"
$py = "python"
if (Test-Path $venvPy) {
  $py = $venvPy
  Write-Host "Usando venv: $py" -ForegroundColor Green
} else {
  Write-Host "Aviso: no se encontro .venv. Usando 'python' del sistema." -ForegroundColor Yellow
}

if ($Clean) {
  if (Test-Path "$repoRoot\build") { Remove-Item "$repoRoot\build" -Recurse -Force }
  if (Test-Path "$repoRoot\dist_installer") { Remove-Item "$repoRoot\dist_installer" -Recurse -Force }
}

# Ensure build deps
& $py -m pip install -r requirements-dev.txt

$iconPath = Join-Path $repoRoot "assets\app.ico"
$hasIcon = Test-Path $iconPath

if (-not (Test-Path $AppExe)) {
  throw "No se encontro AppExe: $AppExe. Primero corre: .\scripts\build_exe.ps1"
}

# Bundle the app exe + icon inside the installer executable
$addDataApp = "$AppExe;."
$addDataIcon = "assets\app.ico;."

$cmd = @(
  $py, "-m", "PyInstaller",
  "--noconfirm",
  "--clean",
  "--windowed",
  "--name", $Name,
  "--distpath", "dist_installer",
  "--onefile",
  "--add-data", $addDataApp,
  "--add-data", $addDataIcon,
  "installer.py"
)

if ($hasIcon) {
  $cmd += @("--icon", $iconPath)
}

Write-Host "\nEjecutando:" -ForegroundColor Cyan
Write-Host ($cmd -join " ")

& $cmd[0] $cmd[1..($cmd.Length-1)]

if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller (installer) falló con código $LASTEXITCODE"
}

Write-Host "\nOK. Instalador en dist_installer\$Name.exe" -ForegroundColor Green
