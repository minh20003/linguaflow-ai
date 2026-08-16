@echo off
setlocal
set "REPO_ROOT=%~dp0.."
node "%REPO_ROOT%\scripts\codex_log.mjs" %*
exit /b %ERRORLEVEL%
