import time, csv, traceback, random, os, json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

URL = "https://www.roblox.com/redeem"
BASE = os.path.dirname(os.path.abspath(__file__))
CODES_FILE = os.path.join(BASE, "codes.txt")
RESULTS_FILE = os.path.join(BASE, "results.csv")
CHROME_USER_DATA = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data")


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
        return "Default"
    print("\nКакой профиль Chrome использовать?")
    for i, (folder, name) in enumerate(profiles, 1):
        print(f"  {i}. {name}")
    while True:
        try:
            choice = int(input("\nВыбери номер: ").strip())
            if 1 <= choice <= len(profiles):
                folder, name = profiles[choice - 1]
                print(f"Выбран: {name} ({folder})")
                return folder
        except:
            pass


def read_codes():
    with open(CODES_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def is_captcha(driver):
    try:
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        return any(x in body for x in ["checking your browser", "just a moment", "arkose", "funcaptcha", "начать задачу"])
    except:
        return False


def wait_captcha(driver):
    attempt = 0
    while is_captcha(driver):
        attempt += 1
        wait_sec = random.randint(180, 300)
        print(f"  Captcha! Жду {wait_sec//60}м {wait_sec%60}с (попытка {attempt})...")
        elapsed = 0
        while elapsed < wait_sec:
            chunk = min(30, wait_sec - elapsed)
            time.sleep(chunk)
            elapsed += chunk
            if wait_sec - elapsed > 0:
                print(f"  Осталось {wait_sec-elapsed}с...")
        driver.refresh()
        time.sleep(5)
    print("  Капча прошла!")


def process_code(driver, code):
    driver.get(URL)
    time.sleep(random.uniform(3, 5))
    if is_captcha(driver):
        wait_captcha(driver)
        driver.get(URL)
        time.sleep(3)
    try:
        inp = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']"))
        )
        inp.clear()
        inp.send_keys(code)
    except:
        pass
    time.sleep(random.uniform(1, 2))
    try:
        btn = driver.find_element(By.XPATH, "//button[contains(translate(., 'REDEM', 'redem'), 'edeem')]")
        btn.click()
    except:
        pass
    time.sleep(random.uniform(7, 10))
    if is_captcha(driver):
        wait_captcha(driver)
        return process_code(driver, code)
    return driver.find_element(By.TAG_NAME, "body").text


# ---- Старт ----
print("\n=== Roblox Code Checker ===")
print("ВАЖНО: Chrome должен быть закрыт!\n")

profile_folder = pick_profile()

checked = set()
if os.path.exists(RESULTS_FILE):
    ans = input("\nПродолжить с прошлого места? (да/нет): ").strip().lower()
    if ans in ("да", "д", "y", "yes"):
        try:
            with open(RESULTS_FILE, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                next(reader)
                for row in reader:
                    if row: checked.add(row[0])
            print(f"Пропускаю уже проверенные: {len(checked)}")
        except:
            pass
    else:
        os.remove(RESULTS_FILE)

print("\nЗапускаю Chrome...")
options = Options()
options.add_argument(f"--user-data-dir={CHROME_USER_DATA}")
options.add_argument(f"--profile-directory={profile_folder}")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--start-maximized")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

try:
    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
except Exception as e:
    print(f"\nОШИБКА: {e}")
    print("Убедись что Chrome полностью закрыт!")
    input("Нажми Enter...")
    exit()

print("Chrome запущен!")

try:
    codes = read_codes()
    remaining = [c for c in codes if c not in checked]
    print(f"Кодов: {len(codes)}, осталось: {len(remaining)}\n")

    if not remaining:
        input("Нет кодов! Нажми Enter...")
        driver.quit()
        exit()

    valid = invalid = errors = 0

    with open(RESULTS_FILE, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        if not checked:
            writer.writerow(["code", "status", "result"])

        for i, code in enumerate(remaining, 1):
            print(f"[{i}/{len(remaining)}] {code}")
            try:
                result_text = process_code(driver, code)
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
                print(f"  -> ERROR: {e}")

    print(f"\n===== ГОТОВО =====")
    print(f"Valid: {valid}  Invalid: {invalid}  Errors: {errors}")
    print(f"Результаты: {RESULTS_FILE}")

except Exception:
    traceback.print_exc()

input("\nНажми Enter для выхода...")
driver.quit()
