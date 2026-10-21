@echo off
rem PvzTrainer mod gui launcher
chcp 65001 >nul
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw "%~dp0PvzTrainerGUI.pyw"
) else (
  start "" python "%~dp0PvzTrainerGUI.pyw"
)