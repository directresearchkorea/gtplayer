@echo off
cd /d "%~dp0"

echo ========================================================
echo   GTPlayer Windows Task Scheduler Setup (GTplayerNet)
echo ========================================================

schtasks /Create /F /TN "GTPlayer_MorningPipeline" /TR "\"%~dp0run_pipeline.bat\" --now" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 06:00
schtasks /Change /TN "GTPlayer_MorningPipeline" /ENABLE
schtasks /Change /TN "GTPlayer_PublishScheduler" /DISABLE 2>nul

powershell -NoProfile -Command "$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Hours 4); Set-ScheduledTask -TaskName 'GTPlayer_MorningPipeline' -Settings $s; Enable-ScheduledTask -TaskName 'GTPlayer_MorningPipeline' | Out-Null"

echo Done!
