param(
  [string]$Name = "Inventarios POS",
  [string]$SourceExe = "",
  [string]$InstallDir = "",
  [switch]$StartMenu = $true,
  [switch]$Desktop = $true
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  return (Split-Path -Parent $PSScriptRoot)
}

function Get-DefaultSourceExe($repoRoot) {
  $candidates = @(
    (Join-Path $repoRoot "dist\InventariosPOS.exe"),
    (Join-Path $repoRoot "dist\Inventarios POS.exe")
  )
  foreach ($p in $candidates) {
    if (Test-Path $p) { return $p }
  }
  throw "No se encontró el .exe en dist/. Primero corre: .\scripts\build_exe.ps1"
}

function Get-DefaultInstallDir($appName) {
  $base = $env:LOCALAPPDATA
  if (-not $base) { $base = $env:APPDATA }
  if (-not $base) { $base = $HOME }

  $safe = ($appName -replace "[^A-Za-z0-9 _-]", "").Trim()
  if (-not $safe) { $safe = "InventariosPOS" }
  $safe = $safe -replace " ", "_"
  return (Join-Path $base $safe)
}

function New-Shortcut(
  [string]$ShortcutPath,
  [string]$TargetPath,
  [string]$WorkingDirectory,
  [string]$IconLocation,
  [string]$Description
) {
  $wsh = New-Object -ComObject WScript.Shell
  $sc = $wsh.CreateShortcut($ShortcutPath)
  $sc.TargetPath = $TargetPath
  $sc.WorkingDirectory = $WorkingDirectory
  if ($IconLocation) { $sc.IconLocation = $IconLocation }
  if ($Description) { $sc.Description = $Description }
  $sc.Save()
}

$repoRoot = Get-RepoRoot

if (-not $SourceExe) {
  $SourceExe = Get-DefaultSourceExe $repoRoot
}
if (-not (Test-Path $SourceExe)) {
  throw "No existe SourceExe: $SourceExe"
}

if (-not $InstallDir) {
  $InstallDir = Get-DefaultInstallDir $Name
}

# Normalize path (PowerShell 5.1 compatible)
$InstallDir = [Environment]::ExpandEnvironmentVariables($InstallDir)
if (-not [System.IO.Path]::IsPathRooted($InstallDir)) {
  $InstallDir = Join-Path (Get-Location).Path $InstallDir
}
$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

$targetExe = Join-Path $InstallDir "InventariosPOS.exe"
Copy-Item -Force $SourceExe $targetExe

$iconPath = Join-Path $repoRoot "assets\app.ico"
$iconLoc = ""
if (Test-Path $iconPath) {
  $destIcon = Join-Path $InstallDir "app.ico"
  Copy-Item -Force $iconPath $destIcon
  $iconLoc = "$destIcon,0"
} else {
  $iconLoc = "$targetExe,0"
}

# Desktop shortcut
if ($Desktop) {
  $desktopDir = [Environment]::GetFolderPath('DesktopDirectory')
  $desktopLnk = Join-Path $desktopDir ("$Name.lnk")
  New-Shortcut -ShortcutPath $desktopLnk -TargetPath $targetExe -WorkingDirectory $InstallDir -IconLocation $iconLoc -Description $Name
  Write-Host "Creado acceso directo en Escritorio: $desktopLnk" -ForegroundColor Green
}

# Start Menu shortcut
if ($StartMenu) {
  $startDir = [Environment]::GetFolderPath('Programs')
  $startLnk = Join-Path $startDir ("$Name.lnk")
  New-Shortcut -ShortcutPath $startLnk -TargetPath $targetExe -WorkingDirectory $InstallDir -IconLocation $iconLoc -Description $Name
  Write-Host "Creado acceso directo en Menú Inicio: $startLnk" -ForegroundColor Green
}

Write-Host "\nInstalado en: $InstallDir" -ForegroundColor Cyan
Write-Host "Puedes mover el .exe sin perder datos: la DB queda en %LOCALAPPDATA% cuando está empaquetado." -ForegroundColor DarkGray
