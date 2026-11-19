<#
 Builds everything locally (Windows + SOLIDWORKS installed):
   1. stamps the version from the VERSION file (and the GitHub repo from `git remote`)
   2. builds the add-in DLL against YOUR SOLIDWORKS interop assemblies
   3. packages the Python engine into a standalone SmartRouteEngine.exe (PyInstaller)
   4. compiles the GUI installer with Inno Setup  ->  dist\SmartRoute-Setup-<version>.exe
 Prerequisites: .NET SDK (or Visual Studio), Python 64-bit, Inno Setup 6.3+, git.
#>
param(
  [string]$SWDir = "C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS",
  [switch]$SkipEngine,
  [switch]$SkipInstaller
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$version = (Get-Content "$root\VERSION" -Raw).Trim()
Write-Host "== Smart Route $version =="

# 1) stamp version + repo
$vcs = "$root\src\SmartRoute\Version.cs"
$txt = Get-Content $vcs -Raw
$txt = $txt -replace 'Version = "[^"]*"', "Version = `"$version`""
$remote = (git -C $root remote get-url origin 2>$null)
if ($remote -match 'github\.com[:/]+([^/]+)/([^/\.]+)') {
  $txt = $txt -replace 'Repo = "[^"]*"', "Repo = `"$($Matches[1])/$($Matches[2])`""
  Write-Host "Update repository: $($Matches[1])/$($Matches[2])"
} else { Write-Warning "No GitHub 'origin' remote yet: auto-update stays disabled until you add one and rebuild." }
Set-Content $vcs $txt -NoNewline
$py = "$root\src\engine\auto_cable_route.py"
(Get-Content $py -Raw) -replace 'ENGINE_VERSION = "[^"]*"', "ENGINE_VERSION = `"$version`"" | Set-Content $py -NoNewline

# 2) add-in
if (Test-Path "$root\build\addin") { Remove-Item "$root\build\addin" -Recurse -Force }
dotnet build "$root\src\SmartRoute\SmartRoute.csproj" -c Release /p:SWDir="$SWDir" -o "$root\build\addin"
if ($LASTEXITCODE -ne 0) { throw "add-in build failed (is SWDir correct? $SWDir)" }

# 3) engine exe
if (-not $SkipEngine) {
  python -m pip install -r "$root\src\engine\requirements.txt" pyinstaller
  if (Test-Path "$root\build\engine") { Remove-Item "$root\build\engine" -Recurse -Force }
  python -m PyInstaller --noconfirm --clean --name SmartRouteEngine --onedir --console `
    --distpath "$root\build\pyi" --workpath "$root\build\pyi-work" --specpath "$root\build" `
    --hidden-import win32com.client --hidden-import pythoncom --hidden-import pywintypes `
    $py
  if ($LASTEXITCODE -ne 0) { throw "engine packaging failed" }
  Move-Item "$root\build\pyi\SmartRouteEngine" "$root\build\engine"
}

# 4) installer
if (-not $SkipInstaller) {
  $iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $iscc) { throw "Inno Setup 6 not found (https://jrsoftware.org/isinfo.php)" }
  & $iscc "/DAppVersion=$version" "$root\installer\SmartRoute.iss"
  if ($LASTEXITCODE -ne 0) { throw "installer build failed" }
  Write-Host "Installer: $root\dist\SmartRoute-Setup-$version.exe"
}
