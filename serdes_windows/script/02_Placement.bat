@echo off
setlocal DisableDelayedExpansion
"%~dpn0.exe" %*
exit /b %ERRORLEVEL%
