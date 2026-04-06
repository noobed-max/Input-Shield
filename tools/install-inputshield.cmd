@echo off
:: install-inputshield.cmd
:: ========================
:: Installs the InputShield kernel driver.
:: Must be run from an elevated (Administrator) Command Prompt.
::
:: Usage:
::   install-inputshield.cmd /install
::   install-inputshield.cmd /uninstall
::
:: Before running, ensure inputshield.sys has been placed into
::   %SystemRoot%\System32\drivers\
:: (Use patch_driver.py to produce it from the original interception.sys)

setlocal

set SVC_NAME=inputshield
set DRV_PATH=%SystemRoot%\System32\drivers\%SVC_NAME%.sys

if /I "%~1"=="/install" goto :install
if /I "%~1"=="/uninstall" goto :uninstall

echo Usage:
echo   install-inputshield.cmd /install
echo   install-inputshield.cmd /uninstall
goto :eof

:install
echo [*] Installing %SVC_NAME% driver service...

if not exist "%DRV_PATH%" (
    echo [!] Driver not found at %DRV_PATH%
    echo     Run patch_driver.py first to generate inputshield.sys
    exit /b 1
)

sc create %SVC_NAME% ^
    binPath= "%DRV_PATH%" ^
    type= kernel ^
    start= auto ^
    DisplayName= "InputShield HID Filter"

if %errorlevel% neq 0 (
    echo [!] sc create failed. The service may already exist.
    echo     Try: sc delete %SVC_NAME%  then re-run.
    exit /b 1
)

sc description %SVC_NAME% "Keyboard and mouse input filter driver (InputShield)"

echo [*] Starting %SVC_NAME%...
sc start %SVC_NAME%

if %errorlevel% neq 0 (
    echo [!] Failed to start service. Check Event Viewer for details.
    exit /b 1
)

echo [+] InputShield driver installed and running.
goto :eof

:uninstall
echo [*] Stopping %SVC_NAME%...
sc stop %SVC_NAME%

echo [*] Deleting service entry...
sc delete %SVC_NAME%

echo [+] InputShield driver uninstalled.
echo     You may want to delete: %DRV_PATH%
goto :eof
