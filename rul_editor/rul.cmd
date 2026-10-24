@echo off
cd /d "%~dp0.."
python -m rul_editor %*
if errorlevel 1 if "%~1"=="" pause
