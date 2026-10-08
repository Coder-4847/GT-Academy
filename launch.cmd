@echo off
setlocal
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup.cmd first to create the Python environment.
  popd
  exit /b 1
)
".venv\Scripts\python.exe" -m tools.play %*
set "result=%errorlevel%"
popd
exit /b %result%
