@echo off
chcp 65001 >nul
title Roblox Code Checker

echo ========================================
echo     Roblox Code Checker - Установка
echo ========================================
echo.

:: Проверяем Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не установлен!
    echo Скачай с https://python.org и при установке отметь "Add to PATH"
    pause
    exit
)

echo [OK] Python найден
echo.

:: Устанавливаем зависимости
echo Устанавливаю библиотеки...
pip install playwright >nul 2>&1
echo [OK] Playwright установлен

echo Устанавливаю браузер (может занять 1-2 минуты)...
playwright install chromium >nul 2>&1
echo [OK] Браузер установлен

echo.

:: Проверяем codes.txt
if not exist "codes.txt" (
    echo [ОШИБКА] Файл codes.txt не найден!
    echo Создай файл codes.txt и положи в него коды - каждый с новой строки
    pause
    exit
)

echo [OK] codes.txt найден
echo.
echo ========================================
echo          Запускаю чекер...
echo ========================================
echo.

python checker.py

pause
