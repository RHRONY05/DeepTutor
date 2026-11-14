@echo off
REM Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
REM One-click launcher: starts backend + frontend and opens the browser.
REM Close this window (or press Ctrl+C) to stop DeepTutor.
title DeepTutor
cd /d "%~dp0..\.."
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

REM Already running? Just open it instead of starting a second copy.
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:3782 | Out-Null; exit 0 } catch { exit 1 }"
if %errorlevel%==0 (
  echo DeepTutor is already running. Opening it...
  start "" http://127.0.0.1:3782/chat
  timeout /t 3 >nul
  exit /b 0
)

if not exist ".venv\Scripts\deeptutor.exe" (
  echo The Python environment is missing: D:\Projects\DeepTutor\.venv
  echo Recreate it with the install steps in FORK_NOTICE.md, then try again.
  pause
  exit /b 1
)

echo Starting DeepTutor. The first start after a code change rebuilds the web app (a few minutes).
echo Close this window to stop DeepTutor.

REM Open the browser ourselves on 127.0.0.1, not "localhost": in Chrome the chat
REM WebSocket fails on localhost (IPv6 first) while 127.0.0.1 works.
REM This helper waits up to 15 minutes for the web app, then opens it once.
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "$u='http://127.0.0.1:3782/chat'; for ($i=0; $i -lt 450; $i++) { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:3782 | Out-Null; Start-Process $u; break } catch { Start-Sleep -Seconds 2 } }"

".venv\Scripts\deeptutor.exe" start --no-browser
if errorlevel 1 pause
