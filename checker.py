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


def is_logged_in(page):
    try:
        page.goto("https://www.roblox.com/home", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        return "login" not in page.url.lower()
    except:
        return False


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
    attempt = 0
    while True:
        if not is_captcha(page):
            print("  Captcha cleared, continuing...")
            return

        attempt += 1
        wait_sec = random.randint(180, 300)
        mins = wait_sec // 60
        secs = wait_sec % 60
        print(f"  Captcha! (attempt {attempt}) Waiting {mins}m {secs}s...")

        elapsed = 0
        while elapsed < wait_sec:
            chunk = min(30, wait_sec - elapsed)
            time.sleep(chunk)
            elapsed += chunk
            remaining = wait_sec - elapsed
            if remaining > 0:
                print(f"  {remaining}s remaining...")

        print("  Refreshing page...")
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
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    time.sleep(random.uniform(2, 4))

    if is_captcha(page):
        print("  Captcha on page load...")
        wait_for_captcha_to_clear(page)
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(random.uniform(2, 4))

    try:
        inp = page.get_by_label("Code")
    except:
        inp = page.locator("input, textarea").nth(1)

    inp.fill("")
    inp.fill(code)
    time.sleep(random.uniform(1, 2))

    try:
        page.get_by_role("button", name="Redeem").click(timeout=15000)
    except:
        page.locator("text=Redeem").first.click(timeout=15000)

    wait_ready(page)

    if is_captcha(page):
        print("  Captcha after Redeem click...")
        wait_for_captcha_to_clear(page)
        print("  Retrying code after captcha...")
        return process_code(page, code)

    return page.inner_text("body")


print("\n=== Roblox Code Checker ===\n")

os.makedirs(PROFILE_DIR, exist_ok=True)
first_login = not os.path.exists(os.path.join(PROFILE_DIR, "Default", "Cookies"))

# ---- Продолжение или заново ----
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
            print(f"Skipping already checked: {len(checked)} codes")
        except:
            pass
    else:
        os.remove(RESULTS_FILE)
        print("Starting fresh.")

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        args=[
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--disable-dev-shm-usage",
        ],
        no_viewport=True,
        ignore_default_args=["--enable-automation"],
    )
    page = browser.new_page()
    # Скрываем что это автоматизированный браузер
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    # Первый запуск — просим залогиниться
    if first_login or not is_logged_in(page):
        print("\n" + "="*50)
        print("  Войди в аккаунт Roblox в открытом браузере")
        print("  После входа вернись сюда и нажми Enter")
        print("="*50)
        page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
        input("\n  Нажми Enter когда залогинишься: ")
        print("  Отлично! Сессия сохранена, в следующий раз вход не нужен.\n")

    try:
        codes = read_codes()
        remaining = [c for c in codes if c not in checked]
        print(f"Total codes: {len(codes)}, remaining: {len(remaining)}")

        if not remaining:
            input("No codes to check! Press Enter...")
            browser.close()
            exit()

        print("Opening redeem page...")
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
                print(f"\n[{i}/{len(remaining)}] {code}")

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
                    print(f"  -> {status}")
                    time.sleep(random.uniform(2, 4))

                except Exception as e:
                    writer.writerow([code, "ERROR", str(e)])
                    f.flush()
                    errors += 1
                    print(f"  -> ERROR: {e}")
                    traceback.print_exc()

        print(f"\n===== DONE =====")
        print(f"Valid:   {valid}")
        print(f"Invalid: {invalid}")
        print(f"Errors:  {errors}")
        print(f"Results: {RESULTS_FILE}")

    except Exception:
        traceback.print_exc()

    input("\nPress Enter to close browser...")
    browser.close()
