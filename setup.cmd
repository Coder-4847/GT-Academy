@echo off
setlocal
pushd "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
py -3.12 -m venv .venv
if not errorlevel 1 goto install
echo Install Python 3.12 from python.org, including the Python launcher, then run setup.cmd again.
popd
exit /b 1
:install
".venv\Scripts\python.exe" -m pip install -r requirements-lock.txt
if errorlevel 1 (
  echo Dependency installation failed. Check the error above and your internet connection.
  popd
  exit /b 1
)
".venv\Scripts\python.exe" -m pytest -q -p no:cacheprovider
set "result=%errorlevel%"
if %result%==0 echo Ready. Run launch.cmd to drive.
popd
exit /b %result%
