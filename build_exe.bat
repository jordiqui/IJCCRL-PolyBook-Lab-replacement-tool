@echo off
setlocal
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"
python -m pip install -r requirements-dev.txt
python -m PyInstaller --noconfirm --clean --onefile --name ijccrl-polybook polybook.py
if errorlevel 1 exit /b 1
if not exist dist\examples mkdir dist\examples
if not exist dist\reports mkdir dist\reports
if not exist dist\books mkdir dist\books
copy /Y README_EXECUTABLE.txt dist\README_EXECUTABLE.txt >nul

echo Build complete: dist\ijccrl-polybook.exe
endlocal
