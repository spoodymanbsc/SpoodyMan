from playwright.sync_api import sync_playwright
import time
import csv
import traceback
import random
import os

URL = "https://www.roblox.com/redeem"
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot-profile")
CODES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codes.txt")
RESULTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.csv")


def read_codes():
    with open(CODES_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def is_captcha_present(page):
    try:
        all_text = ""
        for frame in page.frames:
            try:
                all_text += frame.inner_text("body").lower()
            except:
                pass

        captcha_signals = [
            "проверяем ваш браузер" in all_text,
            "checking your browser" in all_text,
            "just a moment" in all_text,
            "начать задачу" in all_text,
            "пожалуйста, выполните это задание" in all_text,
            "arkose" in all_text,
            "funcaptcha" in all_text,
            page.locator("iframe[src*='captcha']").count() > 0,
            page.locator("iframe[src*='recaptcha']").count() > 0,
            page.locator(".g-recaptcha").count() > 0,
            page.locator("[data-sitekey]").count() > 0,
        ]
        return any(captcha_signals)
    except:
        return False


def wait_for_page_ready(page):
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except:
        pass
    time.sleep(random.uniform(6, 9))


def try_redeem_code(page, code):
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    time.sleep(random.uniform(2, 4))

    if is_captcha_present(page):
        return False

    try:
        code_input = page.get_by_label("Code")
        code_input.fill("")
        code_input.fill(code)
    except:
        code_input = page.locator("input, textarea").nth(1)
        code_input.fill("")
        code_input.fill(code)

    time.sleep(random.uniform(1, 2))

    try:
        page.get_by_role("button", name="Redeem").click(timeout=15000)
    except:
        page.locator("text=Redeem").first.click(timeout=15000)

    wait_for_page_ready(page)

    if is_captcha_present(page):
        return False

    return True


def redeem_with_retry(page, code):
    attempt = 0
    while True:
        attempt += 1
        print(f"  Попытка {attempt}...")

        success = try_redeem_code(page, code)

        if success:
            return True

        wait_time = random.randint(60, 90)
        print(f"  ⚠️  Капча! Жду {wait_time} сек...")
        time.sleep(wait_time)


# Спрашиваем начать заново или продолжить
checked_codes = set()
if os.path.exists(RESULTS_FILE):
    answer = input("results.csv уже существует. Начать заново? (да/нет): ").strip().lower()
    if answer in ("да", "д", "y", "yes"):
        os.remove(RESULTS_FILE)
        print("results.csv удалён, начинаю заново.")
    else:
        try:
            with open(RESULTS_FILE, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                next(reader)
                for row in reader:
                    if row:
                        checked_codes.add(row[0])
            print(f"Уже проверено: {len(checked_codes)} кодов, пропускаю их.")
        except:
            pass

os.makedirs(PROFILE_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        channel="chrome",
        headless=False
    )

    page = browser.new_page()

    try:
        codes = read_codes()
        remaining_codes = [c for c in codes if c not in checked_codes]
        print(f"\nНайдено кодов: {len(codes)}, осталось проверить: {len(remaining_codes)}")

        if len(remaining_codes) == 0:
            print("Нет кодов для проверки!")
            input("Нажми Enter для выхода...")
            browser.close()
            exit()

        print("Открываю сайт...")
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)

        valid_count = 0
        invalid_count = 0
        error_count = 0

        with open(RESULTS_FILE, "a", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file)

            if len(checked_codes) == 0:
                writer.writerow(["code", "status", "result"])

            for i, code in enumerate(remaining_codes, start=1):
                print(f"\n[{i}/{len(remaining_codes)}] Проверяю: {code}")

                try:
                    redeem_with_retry(page, code)

                    result_text = page.inner_text("body")
                    result_lower = result_text.lower()

                    if "success" in result_lower or "redeemed" in result_lower:
                        status = "VALID"
                        valid_count += 1
                    elif "invalid" in result_lower or "not valid" in result_lower or "expired" in result_lower:
                        status = "INVALID"
                        invalid_count += 1
                    else:
                        status = "UNKNOWN"
                        error_count += 1

                    writer.writerow([code, status, result_text[:300]])
                    file.flush()

                    print(f"  → {status}")
                    time.sleep(random.uniform(2, 4))

                except Exception as e:
                    writer.writerow([code, "ERROR", str(e)])
                    file.flush()
                    error_count += 1
                    print(f"  → ОШИБКА: {e}")
                    traceback.print_exc()

        print("\n========== ГОТОВО ==========")
        print(f"✅ Валидных:    {valid_count}")
        print(f"❌ Невалидных:  {invalid_count}")
        print(f"⚠️  Ошибок:     {error_count}")
        print(f"Результаты в: {RESULTS_FILE}")

    except Exception:
        print("КРИТИЧЕСКАЯ ОШИБКА:")
        traceback.print_exc()

    input("\nНажми Enter, чтобы закрыть браузер...")
    browser.close()
