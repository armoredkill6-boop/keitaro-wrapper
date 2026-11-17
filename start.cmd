@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONPATH=%CD%
title Keitaro Wrapper
echo.
echo === Keitaro Wrapper ===
echo Folder: %CD%
echo.

set PYEXE=
if exist ".venv\Scripts\python.exe" set PYEXE=.venv\Scripts\python.exe

if "%PYEXE%"=="" (
  where py >nul 2>&1
  if %errorlevel%==0 (
    echo [1/4] Creating venv via py -3 ...
    py -3 -m venv .venv
  ) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
      echo [1/4] Creating venv via python ...
      python -m venv .venv
    ) else (
      echo.
      echo ERROR: Python not found. Install from https://www.python.org/downloads/
      echo Tick "Add python.exe to PATH" during install.
      pause
      exit /b 1
    )
  )
  if not exist ".venv\Scripts\python.exe" (
    echo.
    echo ERROR: venv was not created. Try: py -3 -m venv .venv
    pause
    exit /b 1
  )
  set PYEXE=.venv\Scripts\python.exe
  echo venv OK
) else (
  echo [1/4] venv already exists
)

echo [2/4] pip install ...
"%PYEXE%" -m pip install --upgrade pip
"%PYEXE%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo ERROR: pip install failed
  pause
  exit /b 1
)

echo [3/4] database ...
"%PYEXE%" scripts\init_db.py
if errorlevel 1 (
  echo ERROR: init_db failed
  pause
  exit /b 1
)

echo.
netstat -ano | findstr /C:"127.0.0.1:8000" | findstr LISTENING >nul 2>&1
if %errorlevel%==0 (
  echo.
  echo ERROR: Port 8000 is already in use.
  echo Close the other black window with the server ^(Ctrl+C^) and run start.cmd again.
  echo Do NOT click start.cmd twice — only one server.
  pause
  exit /b 1
)

echo [4/4] Server starting...
echo.
echo   Open in browser NOT Google search — this exact address:
echo   http://127.0.0.1:8000/
echo.
echo   Leave this window open while you work.
echo   Stop server: Ctrl+C
echo.

"%PYEXE%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
if errorlevel 1 (
  echo.
  echo ERROR: uvicorn failed to start
  pause
)