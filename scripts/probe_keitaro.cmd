@echo off
cd /d "%~dp0\.."
set /p KEY=Paste API key (or Enter to use .env): 
if "%KEY%"=="" (
  for /f "tokens=2 delims==" %%a in ('findstr KEITARO_API_KEY .env') do set KEY=%%a
)
echo.
echo === GET campaigns (first bytes) ===
curl.exe -s -H "Api-Key: %KEY%" "https://tlgk.host/admin_api/v1/campaigns"
echo.
echo.
echo === POST minimal campaign ===
curl.exe -s -H "Api-Key: %KEY%" -H "Content-Type: application/json" -d "{\"name\":\"test_krylov_probe\",\"alias\":\"test-krylov-probe-%RANDOM%\"}" "https://tlgk.host/admin_api/v1/campaigns"
echo.
pause