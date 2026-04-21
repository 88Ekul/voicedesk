@echo off
:: Wait 35 seconds for the Windows shell and system tray to fully initialise.
timeout /t 35 /nobreak >nul 2>&1

:: Check if VoiceDesk (pythonw.exe) is already running.
:: Task Scheduler and this shortcut both use a delay, so the one that fires
:: first will be running by the time the second fires.
powershell -Command "if (Get-Process -Name 'pythonw' -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }" >nul 2>&1
if %errorlevel% equ 1 (
    exit /b 0
)

:: Launch VoiceDesk watchdog detached (no console window).
cd /d "C:\Users\<user>\Documents\voicedesk"
start "" "C:\Users\<user>\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe" "C:\Users\<user>\Documents\voicedesk\main.py"
