<#
 NOTE: this project already lives in https://github.com/Moza4y/claude-code - you do NOT need this script.
 It is only for creating a brand-new repository from this folder.
 Run ONCE after unzipping/cloning this project: creates the GitHub repository from this folder and
 pushes all commits and tags (v0.2.0, v0.3.0, ...).
 IMPORTANT: keep the repository PUBLIC - the installed add-in reads releases anonymously to find updates.
#>
param([string]$Name = "smart-route")
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "Install the GitHub CLI (gh) and run: gh auth login" }
gh auth status
gh repo create $Name --public --source . --remote origin --push
git push origin --tags
Write-Host "Done. Next: .\tools\release.ps1 -Version 0.3.0   (publishes the installer as a GitHub Release)"
