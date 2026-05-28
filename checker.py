from playwright.sync_api import sync_playwright
import time, csv, traceback, random, os, json

URL = "https://www.roblox.com/redeem"
BASE = os.path.dirname(os.path.abspath(__file__))
CODES_FILE = os.path.join(BASE, "codes.txt")
RESULTS_FILE = os.path.join(BASE, "results.csv")

CHROME_USER_DATA = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "Google", "Chrome", "User Data"
)


def get_chrome_profiles():
    """Находит все профили Chrome с их именами."""
    profiles = []
    local_state_path = os.path.join(CHROME_USER_DATA, "Local State")
    if not os.path.exists(local_state_path):
        return profiles
    try:
        with open(local_state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        info = state.get("profile", {}).get("info_cache", {})
        for folder, data in info.items():
            name = data.get("name", folder)
            profiles.append((folder, name))
    except:
        pass
    return profiles


def pick_profile():
    """Показывает список профилей и просит выбрать."""
    profiles = get_chrome_profiles()
    if not profiles:
        print("Профили Chrome не найдены. Буду использовать отдельный профиль.")
        return None, os.path.join(BASE, "bot-profile")

    print("\nДоступные профили Chrome:")
    for i, (folder, name) in enumerate(profiles, 1):
        print(f"  {i}. {name}  ({folder})")
    print(f"  0. Создать новый отдельный профиль")

    while True:
        try:
            choice = input("\nВыбери номер профиля: ").strip()
            idx = int(choice)
            if idx == 0:
                return None, os.path.join(BASE, "bot-profile")
            if 1 <= idx <= len(profiles):
                folder, name = profiles[idx - 1]
                print(f"Выбран профиль: {name}")
                return folder, CHROME_USER_DATA
        except:
            pass
        print("Введи число из списка.")


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


# ---- Выбор профиля ----
print("\n=== Roblox Code Checker ===")
print("ВАЖНО: Закрой Chrome перед запуском!\n")
profile_folder, user_data_dir = pick_profile()

# ---- Продолжение или заново ----
checked = set()
if os.path.exists(RESULTS_FILE):
    ans = input("\nПродолжить с прошлого места? (да/нет): ").strip().lower()
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

os.makedirs(user_data_dir if profile_folder else user_data_dir, exist_ok=True)

# ---- Запуск браузера ----
launch_args = []
if profile_folder:
    launch_args.append(f"--profile-directory={profile_folder}")

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        channel="chrome",
        headless=False,
        args=launch_args
    )
    page = browser.new_page()

    try:
        codes = read_codes()
        remaining = [c for c in codes if c not in checked]
        print(f"\nTotal codes: {len(codes)}, remaining: {len(remaining)}")

        if not remaining:
            input("No codes to check! Press Enter...")
            browser.close()
            exit()

        print("Opening site...")
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
