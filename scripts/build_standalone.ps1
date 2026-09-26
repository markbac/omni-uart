# PowerShell script to automate local PyInstaller standalone executable compilation and verify asset resolution.

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Building OmniUART Standalone Executable via PyInstaller " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Ensure PyInstaller is installed
Write-Host "`n[1/3] Checking PyInstaller installation..." -ForegroundColor Yellow
python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller not found in environment. Installing..." -ForegroundColor Yellow
    pip install pyinstaller
}

# 2. Execute PyInstaller compilation
Write-Host "`n[2/3] Compiling standalone executable from omniuart.spec..." -ForegroundColor Yellow
pyinstaller --clean omniuart.spec

if (-not (Test-Path "dist/omni-uart.exe")) {
    Write-Error "Compilation failed: dist/omni-uart.exe not found!"
    exit 1
}

# 3. Perform smoke test verification
Write-Host "`n[3/3] Running executable smoke test verification..." -ForegroundColor Yellow
$output = & "dist/omni-uart.exe" --help
if ($output -match "OmniUART") {
    Write-Host "`n✅ Build Successful! Executable dist/omni-uart.exe compiled and verified." -ForegroundColor Green
} else {
    Write-Error "Smoke test failed: Executable output did not contain expected text."
    exit 1
}
