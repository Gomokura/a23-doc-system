# Kill anything on port 8000
$pids = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess | Select-Object -Unique
foreach ($p in $pids) {
    Write-Host "Killing PID $p"
    Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2

# Verify port is free
$remaining = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($remaining) {
    Write-Host "WARNING: port 8000 still in use"
} else {
    Write-Host "Port 8000 is free. Starting backend..."
}

# Start backend with correct venv
Set-Location "D:\桌面\a23-doc-system"
Start-Process -FilePath "D:\桌面\a23-doc-system\venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "main:app", "--reload", "--port", "8000" `
    -WorkingDirectory "D:\桌面\a23-doc-system" `
    -NoNewWindow
Write-Host "Backend started."
