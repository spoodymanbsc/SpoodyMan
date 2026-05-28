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

:: ---- ШАГ 1: Python ----
echo  [1/4] Проверяю Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo  Python не найден. Устанавливаю автоматически...
    winget install -e --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo  Не удалось через winget. Скачиваю вручную...
        powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python_installer.exe'"
        "%TEMP%\python_installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    )
    :: Обновляем PATH
    call refreshenv >nul 2>&1
    set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts"
)
echo  [OK] Python готов

:: ---- ШАГ 2: Playwright ----
echo  [2/4] Устанавливаю Playwright...
pip install playwright >nul 2>&1
echo  [OK] Playwright установлен

:: ---- ШАГ 3: Браузер ----
echo  [3/4] Устанавливаю браузер (1-2 мин)...
playwright install chromium >nul 2>&1
echo  [OK] Браузер готов

:: ---- ШАГ 4: Создаём checker.py ----
echo  [4/4] Подготавливаю скрипт...

(
echo from playwright.sync_api import sync_playwright
echo import time, csv, traceback, random, os
echo.
echo URL = "https://www.roblox.com/redeem"
echo BASE = os.path.dirname^(os.path.abspath^(__file__^)^)
echo PROFILE_DIR = os.path.join^(BASE, "bot-profile"^)
echo CODES_FILE = os.path.join^(BASE, "codes.txt"^)
echo RESULTS_FILE = os.path.join^(BASE, "results.csv"^)
echo.
echo def read_codes^(^):
echo     with open^(CODES_FILE, "r", encoding="utf-8"^) as f:
echo         return [line.strip^(^) for line in f if line.strip^(^)]
echo.
echo def is_captcha^(page^):
echo     try:
echo         t = ""
echo         for fr in page.frames:
echo             try: t += fr.inner_text^("body"^).lower^(^)
echo             except: pass
echo         sigs = ["checking your browser" in t,"just a moment" in t,"arkose" in t,
echo                 "funcaptcha" in t,"проверяем" in t,"начать задачу" in t,
echo                 page.locator^("iframe[src*='captcha']"^).count^(^)^>0,
echo                 page.locator^(".g-recaptcha"^).count^(^)^>0]
echo         return any^(sigs^)
echo     except: return False
echo.
echo def wait_ready^(page^):
echo     try: page.wait_for_load_state^("networkidle", timeout=15000^)
echo     except: pass
echo     time.sleep^(random.uniform^(6,9^)^)
echo.
echo def try_code^(page, code^):
echo     page.goto^(URL, wait_until="domcontentloaded", timeout=60000^)
echo     time.sleep^(random.uniform^(2,4^)^)
echo     if is_captcha^(page^): return False
echo     try: inp = page.get_by_label^("Code"^)
echo     except: inp = page.locator^("input, textarea"^).nth^(1^)
echo     inp.fill^(""^); inp.fill^(code^)
echo     time.sleep^(random.uniform^(1,2^)^)
echo     try: page.get_by_role^("button", name="Redeem"^).click^(timeout=15000^)
echo     except: page.locator^("text=Redeem"^).first.click^(timeout=15000^)
echo     wait_ready^(page^)
echo     return not is_captcha^(page^)
echo.
echo def check^(page, code^):
echo     attempt = 0
echo     while True:
echo         attempt += 1
echo         print^(f"  Попытка {attempt}..."^)
echo         if try_code^(page, code^): return
echo         w = random.randint^(60,90^)
echo         print^(f"  Капча! Жду {w} сек..."^)
echo         time.sleep^(w^)
echo.
echo checked = set^(^)
echo if os.path.exists^(RESULTS_FILE^):
echo     ans = input^("Продолжить с прошлого места? (да/нет): "^).strip^(^).lower^(^)
echo     if ans in^("да","д","y","yes"^):
echo         try:
echo             with open^(RESULTS_FILE,"r",encoding="utf-8-sig"^) as f:
echo                 r=csv.reader^(f^); next^(r^)
echo                 for row in r:
echo                     if row: checked.add^(row[0]^)
echo             print^(f"Пропускаю уже проверенные: {len^(checked^)}"^)
echo         except: pass
echo     else:
echo         os.remove^(RESULTS_FILE^)
echo.
echo os.makedirs^(PROFILE_DIR, exist_ok=True^)
echo.
echo with sync_playwright^(^) as p:
echo     br = p.chromium.launch_persistent_context^(PROFILE_DIR, channel="chrome", headless=False^)
echo     page = br.new_page^(^)
echo     try:
echo         codes = read_codes^(^)
echo         rem = [c for c in codes if c not in checked]
echo         print^(f"\nКодов всего: {len^(codes^)}, осталось: {len^(rem^)}"^)
echo         if not rem:
echo             input^("Нет кодов! Нажми Enter..."^)
echo             br.close^(^); exit^(^)
echo         page.goto^(URL, wait_until="domcontentloaded", timeout=60000^)
echo         time.sleep^(5^)
echo         ok=0; bad=0; err=0
echo         with open^(RESULTS_FILE,"a",encoding="utf-8-sig",newline=""^) as f:
echo             w=csv.writer^(f^)
echo             if not checked: w.writerow^(["code","status","result"]^)
echo             for i,code in enumerate^(rem,1^):
echo                 print^(f"\n[{i}/{len^(rem^)}] {code}"^)
echo                 try:
echo                     check^(page, code^)
echo                     txt = page.inner_text^("body"^)
echo                     lo = txt.lower^(^)
echo                     if "success" in lo or "redeemed" in lo: st="VALID"; ok+=1
echo                     elif "invalid" in lo or "expired" in lo: st="INVALID"; bad+=1
echo                     else: st="UNKNOWN"; err+=1
echo                     w.writerow^([code,st,txt[:300]]^); f.flush^(^)
echo                     print^(f"  → {st}"^)
echo                     time.sleep^(random.uniform^(2,4^)^)
echo                 except Exception as e:
echo                     w.writerow^([code,"ERROR",str^(e^)]^); f.flush^(^)
echo                     err+=1; print^(f"  → ОШИБКА"^)
echo         print^(f"\n=== ГОТОВО === Валид: {ok}  Невалид: {bad}  Ошибки: {err}"^)
echo         print^(f"Результаты: {RESULTS_FILE}"^)
echo     except Exception: traceback.print_exc^(^)
echo     input^("\nНажми Enter для выхода..."^)
echo     br.close^(^)
) > "%FOLDER%checker.py"

echo  [OK] Всё готово!
echo.

:: ---- Проверяем codes.txt ----
if not exist "%FOLDER%codes.txt" (
    echo  ⚠  Создай файл codes.txt в папке со скриптом
    echo     и напиши туда коды - каждый с новой строки
    echo.
    echo  Открываю папку...
    explorer "%FOLDER%"
    pause
    exit
)

:: ---- ЗАПУСК ----
echo  Запускаю чекер...
echo.
python "%FOLDER%checker.py"
pause
