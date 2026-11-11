@echo off
rem Prepend the project-local uv and venv to this cmd session's PATH.
rem Usage: call scripts\env.cmd
set "PATH=%~dp0..\.tools\uv;%~dp0..\.venv\Scripts;%PATH%"
uv --version
