@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo invest 저장소를 깃허브에 올리는 중...
echo.
git push
echo.
echo 완료! 이 창은 닫으셔도 됩니다. (아무 키나 누르면 닫힘)
pause >nul
