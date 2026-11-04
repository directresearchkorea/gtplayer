@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================================
echo   GTPlayer Windows 작업 스케줄러 경로 업데이트 (GTplayerNet)
echo ========================================================

set "PIPELINE_BAT=%~dp0run_pipeline.bat"
set "SCHEDULER_BAT=%~dp0run_scheduler.bat"

echo.
echo [1/2] 매일 오전 06:00 뉴스레터 데이터 수집 및 원고 생성 작업 등록 중...
schtasks /Create /F /TN "GTPlayer_MorningPipeline" /TR "\"%PIPELINE_BAT%\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 06:00

echo.
echo [2/2] 10분 주기 예약 발행 체크(07:00 웹/이메일/SNS 자동 발행) 작업 등록 중...
schtasks /Create /F /TN "GTPlayer_PublishScheduler" /TR "\"%SCHEDULER_BAT%\"" /SC MINUTE /MO 10

echo.
echo ✅ 작업 스케줄러 경로 업데이트가 완료되었습니다!

