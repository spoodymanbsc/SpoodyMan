from playwright.sync_api import sync_playwright
import time, csv, traceback, random, os, json, sqlite3, shutil, tempfile

URL = "https://www.roblox.com/redeem"
BASE = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(BASE, "bot-profile")
CODES_FILE = os.path.join(BASE, "codes.txt")
RESULTS_FILE = os.path.join(BASE, "results.csv")

CHROME_USER_DATA = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "Google", "Chrome", "User Data"
)


def get_chrome_profiles():
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
    profiles = get_chrome_profiles()
    if not profiles:
        return None

    print("\nИз какого профиля Chrome взять сессию Roblox?")
    for i, (folder, name) in enumerate(profiles, 1):
        print(f"  {i}. {name}")
    print(f"  0. Войти вручную")

    while True:
        try:
            choice = int(input("\nВыбери номер: ").strip())
            if choice == 0:
                return None
            if 1 <= choice <= len(profiles):
                folder, name = profiles[choice - 1]
                print(f"Беру куки из профиля: {name}")
                return folder
        except:
            pass
        print("Введи число из списка.")


def get_roblox_cookies(profile_folder):
    """Извлекает куки Roblox из Chrome профиля."""
    try:
        import win32crypt
        from Crypto.Cipher import AES
        import base64

        # Читаем ключ шифрования
        local_state_path = os.path.join(CHROME_USER_DATA, "Local State")
        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)

        encrypted_key = base64.b64decode(
            local_state["os_crypt"]["encrypted_key"]
        )
        encrypted_key = encrypted_key[5:]  # убираем DPAPI префикс
        key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]

        # Копируем файл куки (Chrome блокирует прямой доступ)
        cookies_path = os.path.join(CHROME_USER_DATA, profile_folder, "Network", "Cookies")
        if not os.path.exists(cookies_path):
            cookies_path = os.path.join(CHROME_USER_DATA, profile_folder, "Cookies")

        tmp = tempfile.mktemp(suffix=".db")
        shutil.copy2(cookies_path, tmp)

        conn = sqlite3.connect(tmp)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, encrypted_value, domain FROM cookies WHERE host_key LIKE '%roblox.com%'"
        )

        cookies = []
        for name, enc_val, domain in cursor.fetchall():
            try:
                if enc_val[:3] == b'v10':
                    nonce = enc_val[3:15]
                    ciphertext = enc_val[15:-16]
                    tag = enc_val[-16:]
                    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
                    value = cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8")
                else:
                    value = win32crypt.CryptUnprotectData(enc_val, None, None, None, 0)[1].decode("utf-8")

                cookies.append({
                    "name": name,
                    "value": value,
                    "domain": domain if domain.startswith(".") else "." + domain,
                    "path": "/",
                    "secure": True,
                    "httpOnly": False,
                    "sameSite": "None",
                })
            except:
                pass

        conn.close()
        os.remove(tmp)
        print(f"  Найдено {len(cookies)} куки Roblox")
        return cookies

    except ImportError:
        print("  Устанавливаю нужные библиотеки...")
        os.system("pip install pywin32 pycryptodome -q")
        print("  Перезапусти скрипт.")
        input("  Нажми Enter...")
        exit()
    except Exception as e:
        print(f"  Не удалось прочитать куки: {e}")
        return []


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


# ---- Старт ----
print("\n=== Roblox Code Checker ===\n")
print("ВАЖНО: Закрой Chrome перед запуском!\n")

profile_folder = pick_profile()
chrome_cookies = []
if profile_folder:
    chrome_cookies = get_roblox_cookies(profile_folder)

os.makedirs(PROFILE_DIR, exist_ok=True)

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

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        args=[
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
        ],
        no_viewport=True,
        ignore_default_args=["--enable-automation"],
    )
    page = browser.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    # Загружаем куки из Chrome
    if chrome_cookies:
        try:
            browser.add_cookies(chrome_cookies)
            print(f"Куки загружены ({len(chrome_cookies)} шт)")
        except Exception as e:
            print(f"Ошибка загрузки куки: {e}")

    # Проверяем вход
    try:
        page.goto("https://www.roblox.com/home", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        if "login" in page.url.lower():
            print("\nНе удалось залогиниться через куки.")
            print("Войди вручную в браузере, потом нажми Enter.")
            input("Нажми Enter после входа: ")
        else:
            print("Залогинен успешно!")
    except Exception as e:
        print(f"Ошибка проверки входа: {e}")
        input("Войди вручную и нажми Enter: ")

    try:
        codes = read_codes()
        remaining = [c for c in codes if c not in checked]
        print(f"\nTotal codes: {len(codes)}, remaining: {len(remaining)}")

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
