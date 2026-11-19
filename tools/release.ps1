<#
 One command per new version:   .\tools\release.ps1 -Version 0.4.0 -Notes "what changed"
 Builds the installer, commits, tags vX.Y.Z, pushes, and publishes a GitHub Release with Setup.exe attached.
 The add-in checks the latest GitHub Release and offers it to every installed copy.
 Needs: GitHub CLI (gh) logged in (`gh auth login`), and everything build.ps1 needs.
#>
param(
  [Parameter(Mandatory = $true)][string]$Version,
  [string]$Notes = "",
  [string]$SWDir = "C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS"
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "Install the GitHub CLI (gh) and run: gh auth login" }

if (-not $Notes -and (Test-Path "$root\CHANGELOG.md")) {      # use the CHANGELOG section of this version
  $m = [regex]::Match((Get-Content "$root\CHANGELOG.md" -Raw), "(?s)## \[?$([regex]::Escape($Version))\]?.*?\r?\n(.*?)(?=\r?\n## |\z)")
  if ($m.Success) { $Notes = $m.Groups[1].Value.Trim() }
}
if (-not $Notes) { $Notes = "Smart Route $Version" }

Set-Content -Path "$root\VERSION" -Value $Version -NoNewline
& "$PSScriptRoot\build.ps1" -SWDir $SWDir
$setup = "$root\dist\SmartRoute-Setup-$Version.exe"
if (-not (Test-Path $setup)) { throw "Installer not found: $setup" }

git add -A
git commit -m "Release v$Version"
git tag "v$Version"
git push origin HEAD
git push origin "v$Version"
gh release create "v$Version" $setup --title "Smart Route $Version" --notes "$Notes"
Write-Host "Published v$Version"
