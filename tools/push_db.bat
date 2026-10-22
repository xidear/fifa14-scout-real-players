@echo off
rem Push the scout databases to a rooted device. Optional first arg: path to adb.exe
setlocal
set "ADB=%~1"
if "%ADB%"=="" set "ADB=adb"
python "%~dp0push_db.py" --adb "%ADB%" --pkg com.ea.game.fifa14_row
pause