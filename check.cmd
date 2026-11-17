@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Check Python and project
echo.
where py 2>nul && py -3 --version
where python 2>nul && python --version
echo.
if exist .venv\Scripts\python.exe (
  echo venv: OK
  .venv\Scripts\python.exe --version
) else (
  echo venv: NOT FOUND
)
echo.
if exist requirements.txt (echo requirements.txt: OK) else (echo requirements.txt: MISSING)
if exist .env (echo .env: OK) else (echo .env: MISSING)
echo.
pause