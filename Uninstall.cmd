@echo off
if exist "%LOCALAPPDATA%\Programs\DesktopStats\DesktopStats.exe" (
  start "" "%LOCALAPPDATA%\Programs\DesktopStats\DesktopStats.exe" --uninstall
) else (
  start "" "%~dp0DesktopStats.exe" --uninstall
)
