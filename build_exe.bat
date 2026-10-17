@echo off
setlocal
cd /d "%~dp0"
echo Installing dependencies and Windows packager...
py -m pip install --upgrade pip
if errorlevel 1 goto failed
py -m pip install -r requirements.txt
if errorlevel 1 goto failed
py -m PyInstaller --noconfirm --clean --onefile --windowed --name expense_tracker expense_tracker.py
if errorlevel 1 goto failed
echo.
echo BUILD COMPLETE: %~dp0dist\expense_tracker.exe
echo Copy the EXE into a writable folder. It does not need Python on the target PC.
pause
exit /b 0
:failed
echo Build failed. Check that Python is installed and available with the py command.
pause
exit /b 1
