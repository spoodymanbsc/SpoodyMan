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
        return any([
            "checking your browser" in all_text,
            "just a moment" in all_text,
            "проверяем ваш браузер" in all_text,
            "arkose" in all_text,
            "funcaptcha" in all_text,
            page.locator("iframe[src*='captcha']").count() > 0,
        ])
    except:
        return False


def wait_captcha(page):
    attempt = 0
    while is_captcha(page):
        attempt += 1
        wait_sec = random.randint(180, 300)
        print(f"  Captcha! Waiting {wait_sec//60}m {wait_sec%60}s (attempt {attempt})...")
        elapsed = 0
        while elapsed < wait_sec:
            chunk = min(30, wait_sec - elapsed)
            time.sleep(chunk)
            elapsed += chunk
            if wait_sec - elapsed > 0:
                print(f"  {wait_sec - elapsed}s left...")
        print("  Refreshing...")
        try:
            page.reload(wait_until="domcontentloaded", timeout=30000)
        except:
            pass
        time.sleep(5)
    print("  OK, continuing...")


def process_code(page, code):
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    time.sleep(random.uniform(3, 5))

    if is_captcha(page):
        wait_captcha(page)
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

    try:
        inp = page.get_by_label("Code")
    except:
        inp = page.locator("input").first

    inp.fill("")
    inp.fill(code)
    time.sleep(random.uniform(1, 2))

    try:
        page.get_by_role("button", name="Redeem").click(timeout=10000)
    except:
        page.locator("button:has-text('Redeem')").first.click(timeout=10000)

    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except:
        pass
    time.sleep(random.uniform(6, 9))

    if is_captcha(page):
        wait_captcha(page)
        return process_code(page, code)

    return page.inner_text("body")


# ---- Старт ----
print("\n=== Roblox Code Checker ===\n")
os.makedirs(PROFILE_DIR, exist_ok=True)

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
            print(f"Пропускаю уже проверенные: {len(checked)}")
        except:
            pass
    else:
        os.remove(RESULTS_FILE)

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        args=[
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
        no_viewport=True,
        ignore_default_args=["--enable-automation"],
    )
    page = browser.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    # Проверяем логин
    already_logged = os.path.exists(os.path.join(PROFILE_DIR, "Default", "Cookies"))
    if already_logged:
        page.goto("https://www.roblox.com/home", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        already_logged = "login" not in page.url.lower()

    if not already_logged:
        print("\n" + "="*50)
        print("  Войди в Roblox в открытом браузере")
        print("  Потом вернись сюда и нажми Enter")
        print("="*50 + "\n")
        page.goto("https://www.roblox.com/login", wait_until="domcontentloaded", timeout=30000)
        input("Нажми Enter после входа: ")

    try:
        codes = read_codes()
        remaining = [c for c in codes if c not in checked]
        print(f"\nКодов: {len(codes)}, осталось: {len(remaining)}\n")

        if not remaining:
            input("Нет кодов! Нажми Enter...")
            browser.close()
            exit()

        valid = invalid = errors = 0

        with open(RESULTS_FILE, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            if not checked:
                writer.writerow(["code", "status", "result"])

            for i, code in enumerate(remaining, 1):
                print(f"[{i}/{len(remaining)}] {code}")
                try:
                    result_text = process_code(page, code)
                    lo = result_text.lower()
                    if "success" in lo or "redeemed" in lo:
                        status = "VALID"; valid += 1
                    elif "invalid" in lo or "not valid" in lo or "expired" in lo:
                        status = "INVALID"; invalid += 1
                    else:
                        status = "UNKNOWN"; errors += 1
                    writer.writerow([code, status, result_text[:300]])
                    f.flush()
                    print(f"  -> {status}")
                    time.sleep(random.uniform(2, 4))
                except Exception as e:
                    writer.writerow([code, "ERROR", str(e)])
                    f.flush()
                    errors += 1
                    print(f"  -> ERROR")

        print(f"\n===== DONE =====")
        print(f"Valid: {valid}  Invalid: {invalid}  Errors: {errors}")
        print(f"Results: {RESULTS_FILE}")

    except Exception:
        traceback.print_exc()

    input("\nНажми Enter для выхода...")
    browser.close()
