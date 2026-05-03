Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "Installing desktop build dependencies..."
python -m pip install -e .[desktop-build]

Write-Host "Installing Playwright Chromium runtime..."
python -m playwright install chromium

Write-Host "Building Windows GUI package..."
pyinstaller `
  --noconfirm `
  --clean `
  --windowed `
  --onedir `
  --name DeepWikiExporter `
  src/interface/gui_app.py

Write-Host "Build completed. Output is under .\dist\DeepWikiExporter"
