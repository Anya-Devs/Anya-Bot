# Anya Bot Startup Script
# Starts both the Node.js Image API and the Python bot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "       ANYA BOT STARTUP SCRIPT         " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Start Node.js Image API in background
Write-Host "[1/2] Starting Image API..." -ForegroundColor Yellow
$apiProcess = Start-Process -FilePath "npm" -ArgumentList "start" -WorkingDirectory "$PSScriptRoot\image-api" -PassThru -WindowStyle Hidden

Start-Sleep -Seconds 2

# Check if API started
try {
    $null = Invoke-WebRequest -Uri "http://localhost:3456/health" -UseBasicParsing -TimeoutSec 5
    Write-Host "[OK] Image API is running on port 3456" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Image API may not be running - bot will use fallback" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[2/2] Starting Anya Bot..." -ForegroundColor Yellow
Write-Host ""

# Start Python bot
& "$PSScriptRoot\.venv\Scripts\python.exe" "$PSScriptRoot\main.py"

# Cleanup on exit
Write-Host ""
Write-Host "Shutting down..." -ForegroundColor Yellow
if ($apiProcess -and !$apiProcess.HasExited) {
    Stop-Process -Id $apiProcess.Id -Force
    Write-Host "[OK] Image API stopped" -ForegroundColor Green
}
