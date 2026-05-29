import time, csv, traceback, random, os, json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

URL = "https://www.roblox.com/redeem"
BASE = os.path.dirname(os.path.abspath(__file__))
CODES_FILE = os.path.join(BASE, "codes.txt")
RESULTS_FILE = os.path.join(BASE, "results.csv")

CHROME_USER_DATA = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "Google", "Chrome", "User Data"
)


def get_chrome_profiles():
    profiles = []
    try:
        with open(os.path.join(CHROME_USER_DATA, "Local State"), "r", encoding="utf-8") as f:
            state = json.load(f)
        for folder, data in state.get("profile", {}).get("info_cache", {}).items():
            profiles.append((folder, data.get("name", folder)))
    except:
        pass
    return profiles


def pick_profile():
    profiles = get_chrome_profiles()
    if not profiles:
        print("Профили Chrome не найдены.")
        return None, None
    print("\nИз какого профиля Chrome взять сессию Roblox?")
    for i, (folder, name) in enumerate(profiles, 1):
        print(f"  {i}. {name}")
    while True:
        try:
            choice = int(input("\nВыбери номер: ").strip())
            if 1 <= choice <= len(profiles):
                folder, name = profiles[choice - 1]
                print(f"Выбран профиль: {name} ({folder})")
                return CHROME_USER_DATA, folder
        except:
            pass
        print("Введи число из списка.")


def read_codes():
    with open(CODES_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def is_captcha(driver):
    try:
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        signals = [
            "checking your browser" in body,
            "just a moment" in body,
            "проверяем ваш браузер" in body,
            "начать задачу" in body,
            "arkose" in body,
            "funcaptcha" in body,
        ]
        iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='captcha'], iframe[src*='recaptcha']")
        return any(signals) or len(iframes) > 0
    except:
        return False


def wait_for_captcha_to_clear(driver):
    attempt = 0
    while True:
        if not is_captcha(driver):
            print("  Captcha cleared!")
            return
        attempt += 1
        wait_sec = random.randint(180, 300)
        print(f"  Captcha! Waiting {wait_sec // 60}m {wait_sec % 60}s... (attempt {attempt})")
        elapsed = 0
        while elapsed < wait_sec:
            chunk = min(30, wait_sec - elapsed)
            time.sleep(chunk)
            elapsed += chunk
            if wait_sec - elapsed > 0:
                print(f"  {wait_sec - elapsed}s left...")
        print("  Refreshing...")
        driver.refresh()
        time.sleep(random.uniform(4, 6))


def process_code(driver, code):
    driver.get(URL)
    time.sleep(random.uniform(3, 5))

    if is_captcha(driver):
        print("  Captcha on load...")
        wait_for_captcha_to_clear(driver)
        driver.get(URL)
        time.sleep(random.uniform(3, 5))

    try:
        wait = WebDriverWait(driver, 15)
        inp = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[placeholder*='ode'], input[aria-label*='ode'], #redemption-code-input")
        ))
    except:
        inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input:not([type])")
        inp = inputs[0] if inputs else None

    if not inp:
        return driver.find_element(By.TAG_NAME, "body").text

    inp.clear()
    inp.send_keys(code)
    time.sleep(random.uniform(1, 2))

    try:
        btn = driver.find_element(By.XPATH, "//button[contains(translate(text(),'REDEEM','redeem'),'redeem')]")
        btn.click()
    except:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], .redeem-btn")
            btn.click()
        except:
            pass

    time.sleep(random.uniform(7, 10))

    if is_captcha(driver):
        print("  Captcha after click...")
        wait_for_captcha_to_clear(driver)
        return process_code(driver, code)

    return driver.find_element(By.TAG_NAME, "body").text


# ---- Старт ----
print("\n=== Roblox Code Checker ===\n")
print("ВАЖНО: Закрой Chrome перед запуском!\n")

user_data_dir, profile_dir = pick_profile()

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
            print(f"Пропускаю уже проверенные: {len(checked)}")
        except:
            pass
    else:
        os.remove(RESULTS_FILE)

# ---- Запуск Chrome ----
print("\nЗапускаю Chrome...")
options = uc.ChromeOptions()
if user_data_dir:
    options.add_argument(f"--user-data-dir={user_data_dir}")
if profile_dir:
    options.add_argument(f"--profile-directory={profile_dir}")
options.add_argument("--start-maximized")

try:
    driver = uc.Chrome(options=options)
except Exception as e:
    print(f"\nОШИБКА запуска Chrome: {e}")
    print("Убедись что Chrome полностью закрыт и попробуй снова.")
    input("Нажми Enter...")
    exit()

try:
    codes = read_codes()
    remaining = [c for c in codes if c not in checked]
    print(f"\nКодов всего: {len(codes)}, осталось: {len(remaining)}")

    if not remaining:
        input("Нет кодов! Нажми Enter...")
        driver.quit()
        exit()

    print("Открываю сайт...")
    driver.get(URL)
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
                result_text = process_code(driver, code)
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

    print(f"\n===== ГОТОВО =====")
    print(f"Valid:   {valid}")
    print(f"Invalid: {invalid}")
    print(f"Errors:  {errors}")
    print(f"Results: {RESULTS_FILE}")

except Exception:
    traceback.print_exc()

input("\nНажми Enter для выхода...")
driver.quit()
