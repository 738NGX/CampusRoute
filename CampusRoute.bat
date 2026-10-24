@echo off
setlocal EnableExtensions
cd /d "%~dp0" || exit /b 1
if /I not "%~1"=="--run" (
    start "CampusRoute" cmd.exe /k ""%~s0" --run"
    exit /b 0
)
set "PYTHONDONTWRITEBYTECODE=1"
set "TASK_ROOT=%~sdp0"
set "TASK_PYTHON=%TASK_ROOT%.venv\Scripts\python.exe"
if exist "%TASK_PYTHON%" (
    "%TASK_PYTHON%" -B -c "import campusroute.console" >nul 2>&1
    if not errorlevel 1 goto run
)
echo Environment is incomplete.
echo 1  Install or repair
echo 0  Exit
set /p TASK_REPLY=Choose and press Enter:
if not "%TASK_REPLY%"=="1" exit /b 0
where py >nul 2>&1
if errorlevel 1 (
    echo Python 3.13 launcher was not found.
    pause
    exit /b 1
)
py -3.13 -c "import sys; raise SystemExit(0 if sys.version_info[:2]==(3,13) else 1)" >nul 2>&1
if errorlevel 1 (
    echo Python 3.13 was not found.
    pause
    exit /b 1
)
py -3.13 -m venv "%TASK_ROOT%.venv"
if errorlevel 1 goto install_failed
"%TASK_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto install_failed
"%TASK_PYTHON%" -m pip install -e "%TASK_ROOT%."
if errorlevel 1 goto install_failed
"%TASK_PYTHON%" -B -c "import campusroute.console"
if errorlevel 1 goto install_failed
:run
echo CampusRoute
"%TASK_PYTHON%" -B -m campusroute --root "%TASK_ROOT%."
set "TASK_STATUS=%ERRORLEVEL%"
if not "%TASK_STATUS%"=="0" pause
exit /b %TASK_STATUS%
:install_failed
echo Installation did not finish. Open this file again and choose 1.
pause
exit /b 1