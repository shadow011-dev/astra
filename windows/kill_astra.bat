@echo off
taskkill /F /IM Astra.exe /T >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -match 'shadow_app\.py|mcq_blink\.py|popup\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Astra / Shadow has been force-quit.
