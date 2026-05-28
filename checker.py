from playwright.sync_api import sync_playwright
import time, csv, traceback, random, os

URL = "https://www.roblox.com/redeem"
BASE = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(BASE, "bot-profile")
CODES_FILE = os.path.join(BASE, "codes.txt")
RESULTS_FILE = os.path.join(BASE, "results.csv")


def read_codes():
    with open(CODES_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def is_captcha(page):
    try:
        all_text = ""
        for frame in page.frames:
            try:
                all_text += frame.inner_text("body").lower()
            except:
                pass
        signals = [
            "checking your browser" in all_text,
            "just a moment" in all_text,
            "проверяем ваш браузер" in all_text,
            "начать задачу" in all_text,
            "пожалуйста, выполните это задание" in all_text,
            "arkose" in all_text,
            "funcaptcha" in all_text,
            page.locator("iframe[src*='captcha']").count() > 0,
            page.locator("iframe[src*='recaptcha']").count() > 0,
            page.locator(".g-recaptcha").count() > 0,
            page.locator("[data-sitekey]").count() > 0,
        ]
        return any(signals)
    except:
        return False


def wait_for_captcha_to_clear(page):
    """Стоим и ждём пока капча не пройдёт. Обновляем страницу каждые 3-5 минут."""
    attempt = 0
    while True:
        if not is_captcha(page):
            print("  ✅ Капча прошла, продолжаю...")
            return

        attempt += 1
        wait_sec = random.randint(180, 300)  # 3-5 минут
        mins = wait_sec // 60
        secs = wait_sec % 60
        print(f"  🔒 Капча! (попытка {attempt}) Жду {mins} мин {secs} сек...")

        # Отсчёт каждые 30 секунд чтобы было видно что скрипт живой
        elapsed = 0
        while elapsed < wait_sec:
            chunk = min(30, wait_sec - elapsed)
            time.sleep(chunk)
            elapsed += chunk
            remaining = wait_sec - elapsed
            if remaining > 0:
                print(f"  ⏳ Осталось {remaining} сек...")

        print("  🔄 Обновляю страницу...")
        try:
            page.reload(wait_until="domcontentloaded", timeout=60000)
        except:
            try:
                page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            except:
                pass

        time.sleep(random.uniform(4, 6))


def wait_ready(page):
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except:
        pass
    time.sleep(random.uniform(5, 8))


def process_code(page, code):
    """Проверяет один код. Не уходит дальше пока капча не снята."""

    # Переходим на страницу
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    time.sleep(random.uniform(2, 4))

    # Если сразу капча — ждём пока не пройдёт
    if is_captcha(page):
        print("  🔒 Капча на загрузке страницы...")
        wait_for_captcha_to_clear(page)
        # После капчи заново загружаем страницу для чистого старта
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(random.uniform(2, 4))

    # Вводим код
    try:
        inp = page.get_by_label("Code")
    except:
        inp = page.locator("input, textarea").nth(1)

    inp.fill("")
    inp.fill(code)
    time.sleep(random.uniform(1, 2))

    # Нажимаем Redeem
    try:
        page.get_by_role("button", name="Redeem").click(timeout=15000)
    except:
        page.locator("text=Redeem").first.click(timeout=15000)

    # Ждём ответа
    wait_ready(page)

    # Если после нажатия появилась капча — ждём пока не пройдёт и пробуем код снова
    if is_captcha(page):
        print("  🔒 Капча после нажатия Redeem...")
        wait_for_captcha_to_clear(page)
        # Пробуем этот же код заново
        print("  🔁 Пробую код снова после капчи...")
        return process_code(page, code)

    return page.inner_text("body")


# ---- Старт / продолжение ----
checked = set()
if os.path.exists(RESULTS_FILE):
    ans = input("Продолжить с прошлого места? (да/нет): ").strip().lower()
    if ans in ("да", "д", "y", "yes"):
        try:
            with open(RESULTS_FILE, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                next(reader)
                for row in reader:
                    if row:
                        checked.add(row[0])
            print(f"Пропускаю уже проверенные: {len(checked)} кодов")
        except:
            pass
    else:
        os.remove(RESULTS_FILE)
        print("Начинаю заново.")

os.makedirs(PROFILE_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        PROFILE_DIR, channel="chrome", headless=False
    )
    page = browser.new_page()

    try:
        codes = read_codes()
        remaining = [c for c in codes if c not in checked]
        print(f"\nКодов всего: {len(codes)}, осталось проверить: {len(remaining)}")

        if not remaining:
            input("Нет кодов для проверки! Нажми Enter...")
            browser.close()
            exit()

        print("Открываю сайт...")
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)

        valid = 0
        invalid = 0
        errors = 0

        with open(RESULTS_FILE, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            if not checked:
                writer.writerow(["code", "status", "result"])

            for i, code in enumerate(remaining, 1):
                print(f"\n[{i}/{len(remaining)}] Проверяю: {code}")

                try:
                    result_text = process_code(page, code)
                    lo = result_text.lower()

                    if "success" in lo or "redeemed" in lo:
                        status = "VALID"
                        valid += 1
                    elif "invalid" in lo or "not valid" in lo or "expired" in lo:
                        status = "INVALID"
                        invalid += 1
                    else:
                        status = "UNKNOWN"
                        errors += 1

                    writer.writerow([code, status, result_text[:300]])
                    f.flush()
                    print(f"  → {status}")
                    time.sleep(random.uniform(2, 4))

                except Exception as e:
                    writer.writerow([code, "ERROR", str(e)])
                    f.flush()
                    errors += 1
                    print(f"  → ОШИБКА: {e}")
                    traceback.print_exc()

        print(f"\n========== ГОТОВО ==========")
        print(f"✅ Валидных:   {valid}")
        print(f"❌ Невалидных: {invalid}")
        print(f"⚠️  Ошибок:    {errors}")
        print(f"Результаты:   {RESULTS_FILE}")

    except Exception:
        print("КРИТИЧЕСКАЯ ОШИБКА:")
        traceback.print_exc()

    input("\nНажми Enter, чтобы закрыть браузер...")
    browser.close()
