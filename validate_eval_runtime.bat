@echo off
python --version >nul 2>&1
if errorlevel 1 (
  echo Python was not found on PATH. Install Python and rerun.
  exit /b 1
)
python validate_eval_runtime.py
