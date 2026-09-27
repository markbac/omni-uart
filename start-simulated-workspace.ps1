# ==============================================================================
# OmniUART Simulated Workspace Launcher
# Starts the Virtual MCU Simulator and OmniUART Application side-by-side
# ==============================================================================

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " ⚡ Starting OmniUART Virtual MCU Simulator..." -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$simExe = Join-Path $PSScriptRoot "omni-uart-simulator.exe"
$desktopExe = Join-Path $PSScriptRoot "omni-uart-desktop.exe"
$webExe = Join-Path $PSScriptRoot "omni-uart-web.exe"

if (Test-Path $simExe) {
    Start-Process -FilePath $simExe -WindowStyle Normal
    Start-Sleep -Seconds 1
} else {
    Write-Host "[!] Virtual MCU Simulator binary not found ($simExe), running in python environment..." -ForegroundColor Yellow
}

if (Test-Path $desktopExe) {
    Write-Host "[+] Launching OmniUART Native Desktop Application..." -ForegroundColor Green
    Start-Process -FilePath $desktopExe
} elseif (Test-Path $webExe) {
    Write-Host "[+] Launching OmniUART Interactive Web UI..." -ForegroundColor Green
    Start-Process -FilePath $webExe
} else {
    Write-Host "[!] OmniUART Application executable not found in directory." -ForegroundColor Red
}
