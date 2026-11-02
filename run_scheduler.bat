@echo off
cd /d "%~dp0"
".\.venv\Scripts\python.exe" newsletter_manager\execution\auto_publish_scheduler.py %*
