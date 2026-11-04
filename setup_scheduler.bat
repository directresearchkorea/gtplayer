@echo off
cd /d "%~dp0"

echo ========================================================
echo   GTPlayer Windows Task Scheduler Setup (GTplayerNet)
echo ========================================================

schtasks /Create /F /TN "GTPlayer_MorningPipeline" /TR "\"%~dp0run_pipeline.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 06:00
schtasks /Create /F /TN "GTPlayer_PublishScheduler" /TR "\"%~dp0run_scheduler.bat\"" /SC MINUTE /MO 10

echo Done!
