@echo off
chcp 65001 >nul
title Roblox Checker

:: Запускаем от имени администратора если нужно
net session >nul 2>&1
if errorlevel 1 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit
)

set FOLDER=%~dp0

echo.
echo  ==========================================
echo        ROBLOX CODE CHECKER
echo  ==========================================
echo.

:: ---- Python ----
echo  [1/3] Проверяю Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo  Python не найден. Устанавливаю...
    winget install -e --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python_installer.exe'"
        "%TEMP%\python_installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    )
    set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts"
)
echo  [OK] Python готов

:: ---- Playwright ----
echo  [2/3] Устанавливаю библиотеки...
pip install playwright >nul 2>&1
echo  [OK] Playwright установлен

:: ---- Браузер ----
echo  [3/3] Проверяю браузер (первый раз ~2 мин)...
playwright install chromium >nul 2>&1
echo  [OK] Браузер готов

echo.

:: ---- Проверяем codes.txt ----
if not exist "%FOLDER%codes.txt" (
    echo  Файл codes.txt не найден!
    echo  Создай его в этой же папке и вставь коды - каждый с новой строки.
    echo.
    explorer "%FOLDER%"
    pause
    exit
)

:: ---- Проверяем checker.py ----
if not exist "%FOLDER%checker.py" (
    echo  Файл checker.py не найден!
    echo  Положи checker.py в эту же папку рядом с START.bat
    pause
    exit
)

echo  Запускаю чекер...
echo.
python "%FOLDER%checker.py"
pause
