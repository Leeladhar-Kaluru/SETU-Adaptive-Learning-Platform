Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'uvicorn|app\.worker' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
$listening = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($listening) { Write-Output "PORT_STILL_BUSY" } else { Write-Output "PORT_FREE" }
