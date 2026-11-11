@echo off
rem Project-local uv shim: use .tools\uv\uv.exe instead of a global install.
"%~dp0.tools\uv\uv.exe" %*
