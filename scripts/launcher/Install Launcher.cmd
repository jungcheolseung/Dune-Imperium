@echo off
rem Dune Imperium server launcher: first-time setup (docs/server-launcher-plan.md 5.10).
rem Double-click it once: it installs what the server needs, makes the
rem "Dune Imperium Server" shortcut in the project folder and opens the
rem launcher. After that, double-click the shortcut instead.
rem ASCII only: cmd.exe reads this file in the console code page.
setlocal
rem pushd also maps a network (UNC) folder to a drive letter; cd cannot.
pushd "%~dp0..\.." || (echo Cannot open the project folder: "%~dp0..\.." & pause & exit /b 1)

where uv >nul 2>nul
if errorlevel 1 if exist "%USERPROFILE%\.local\bin\uv.exe" set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>nul
if errorlevel 1 if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\uv.exe" set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
where uv >nul 2>nul
if errorlevel 1 (
  echo uv was not found. Install it first, in PowerShell:
  echo   winget install --id=astral-sh.uv -e
  pause
  exit /b 1
)

set "EXTRAS=--extra ui"
choice /c YN /n /m "Also install the search AI (downloads about 125 MB once)? [Y/N] "
if errorlevel 2 goto sync
set "EXTRAS=--extra ui --extra rl --extra train"
:sync
rem --inexact keeps the development and training packages already installed.
uv sync --locked --inexact %EXTRAS%
if errorlevel 1 (
  echo Installing the dependencies failed; see the messages above.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m dune_imperium.launcher.cli --make-shortcut
if errorlevel 1 (
  pause
  exit /b 1
)
start "" ".venv\Scripts\dune-imperium-launcher.exe"
echo Done. From now on, double-click "Dune Imperium Server" in the project folder.
pause
