@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0\..\.."
where uv >nul 2>nul
if errorlevel 1 (
  echo uv를 찾지 못했습니다. 기존 서버 런처 설치 후 다시 실행하세요.
  pause
  exit /b 1
)
uv run --inexact --extra ui python -m dune_imperium.godot_client.launch %*
if errorlevel 1 (
  echo 시제품을 시작하지 못했습니다. 위 메시지와 tmp\godot 로그를 확인하세요.
  pause
  exit /b 1
)
