@echo off
setlocal
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup.cmd first.
  popd
  exit /b 1
)
".venv\Scripts\python.exe" -m tools.package_game %*
set "result=%errorlevel%"
popd
exit /b %result%
