@echo off
chcp 65001 > nul
title iTunes Code Checker

echo.
echo  Проверяю Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Python не найден. Скачай с https://python.org
    pause & exit /b 1
)

echo  Устанавливаю зависимости...
pip install playwright --quiet
python -m playwright install chromium --quiet

echo.
echo  ====================================================
echo   Файлы, которые нужно подготовить:
echo.
echo   codes.txt    - коды iTunes (по одному на строку)
echo   accounts.txt - аккаунты Apple ID (email:пароль)
echo   proxies.txt  - прокси (host:port) -- необязательно
echo  ====================================================
echo.

if not exist "codes.txt" (
    echo  [!] codes.txt не найден! Создай файл с кодами.
    pause & exit /b 1
)

python itunes_checker.py
pause
