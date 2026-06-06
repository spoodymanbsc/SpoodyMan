from playwright.sync_api import sync_playwright
import time, csv, traceback, random, os, sys, datetime

BASE          = os.path.dirname(os.path.abspath(__file__))
CODES_FILE    = os.path.join(BASE, "codes.txt")
ACCOUNTS_FILE = os.path.join(BASE, "accounts.txt")   # email:password  (по одному на строку)
PROXIES_FILE  = os.path.join(BASE, "proxies.txt")    # host:port  или  user:pass@host:port
RESULTS_FILE  = os.path.join(BASE, "results.csv")
PROFILES_DIR  = os.path.join(BASE, "profiles")

REDEEM_URL = "https://apps.apple.com/redeem"

# --- Настройки ---
MAX_PER_SESSION   = 3       # сколько проверок до смены аккаунта/прокси
HOLD_SECS_MIN     = 7500    # минимальное ожидание при полной блокировке (~2ч 5м)
HOLD_SECS_MAX     = 8400    # максимальное ожидание (~2ч 20м)
DELAY_MIN         = 5       # минимум секунд между кодами
DELAY_MAX         = 12      # максимум секунд между кодами

os.makedirs(PROFILES_DIR, exist_ok=True)


# ─────────────────────────────── helpers ──────────────────────────────────

def read_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]


def load_checked():
    done = {}
    if not os.path.exists(RESULTS_FILE):
        return done
    with open(RESULTS_FILE, "r", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if len(row) >= 2 and row[0] != "code":
                done[row[0]] = row[1]
    return done


def fmt_time(secs):
    h, m = divmod(int(secs), 3600)
    m, s = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def countdown(secs, reason=""):
    print(f"\n  [{reason}] Ожидаю {fmt_time(secs)}...")
    end = time.time() + secs
    while True:
        left = end - time.time()
        if left <= 0:
            break
        print(f"  Осталось: {fmt_time(left)}", end="\r", flush=True)
        time.sleep(min(30, left))
    print()


def parse_proxy(raw):
    """Возвращает dict для Playwright или None."""
    if not raw:
        return None
    raw = raw.strip()
    if "://" not in raw:
        raw = "http://" + raw
    return {"server": raw}


# ─────────────────────────────── browser ──────────────────────────────────

def make_browser(pw, account_idx, proxy_raw=None):
    profile = os.path.join(PROFILES_DIR, f"acc_{account_idx}")
    os.makedirs(profile, exist_ok=True)
    kwargs = dict(
        user_data_dir=profile,
        headless=False,
        args=[
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
        no_viewport=True,
        ignore_default_args=["--enable-automation"],
    )
    if proxy_raw:
        p = parse_proxy(proxy_raw)
        if p:
            kwargs["proxy"] = p
    ctx = pw.chromium.launch_persistent_context(**kwargs)
    page = ctx.new_page()
    page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    return ctx, page


def ensure_logged_in(page, account_idx, accounts):
    """Открывает страницу Apple и убеждается что залогинены. Возвращает True/False."""
    try:
        page.goto("https://appleid.apple.com", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
    except:
        pass

    already = "manage" in page.url or "account" in page.url
    if already:
        print(f"  Аккаунт {account_idx}: уже залогинен")
        return True

    if account_idx < len(accounts):
        email, *pwd_parts = accounts[account_idx].split(":")
        password = ":".join(pwd_parts)
        print(f"\n  Аккаунт #{account_idx+1}: {email}")
        print("  Войди в Apple ID в открывшемся браузере.")
        print("  (Если требуется 2FA — подтверди на устройстве)")
    else:
        print(f"\n  Аккаунт #{account_idx+1}: войди в Apple ID вручную.")

    input("  Нажми Enter после успешного входа: ")
    return True


# ─────────────────────────────── checker ──────────────────────────────────

RATE_LIMIT_HINTS = [
    "too many", "try again later", "please wait", "verification required",
    "security check", "слишком много", "подождите", "заблокирован",
]

def is_rate_limited(page):
    try:
        text = ""
        for frame in page.frames:
            try:
                text += frame.inner_text("body").lower()
            except:
                pass
        return any(h in text for h in RATE_LIMIT_HINTS)
    except:
        return False


def attempt_check(page, code):
    """
    Делает одну попытку проверки кода.
    Возвращает (status, detail):
      VALID    – код действителен / успешно применён
      USED     – уже использован
      INVALID  – не существует / истёк
      RATELIMIT – Apple поставил холд
      NEED_LOGIN – сессия протухла
      ERROR    – неизвестная ошибка
    """
    try:
        page.goto(REDEEM_URL, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        return "ERROR", f"Навигация: {e}"

    time.sleep(random.uniform(3, 5))

    # Проверяем, не выбросило ли нас на страницу входа
    if "sign-in" in page.url or "appleid.apple.com" in page.url:
        return "NEED_LOGIN", "Сессия истекла"

    if is_rate_limited(page):
        return "RATELIMIT", "Холд сразу после открытия"

    # Находим поле ввода кода
    selectors = [
        "input[name='code']",
        "input[id*='code']",
        "input[placeholder*='code' i]",
        "input[aria-label*='code' i]",
        "input[type='text']",
    ]
    inp = None
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=3000):
                inp = loc
                break
        except:
            pass

    if inp is None:
        return "ERROR", "Поле ввода не найдено"

    try:
        inp.fill("")
        time.sleep(0.5)
        inp.fill(code)
        time.sleep(random.uniform(1, 2))
    except Exception as e:
        return "ERROR", f"Заполнение поля: {e}"

    # Кнопка Redeem / Apply
    btn_selectors = [
        "button[type='submit']",
        "button:has-text('Redeem')",
        "button:has-text('Apply')",
        "button:has-text('Continue')",
        "[class*='submit']",
    ]
    clicked = False
    for sel in btn_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                btn.click(timeout=8000)
                clicked = True
                break
        except:
            pass

    if not clicked:
        try:
            inp.press("Enter")
        except:
            return "ERROR", "Кнопка не найдена"

    try:
        page.wait_for_load_state("networkidle", timeout=25000)
    except:
        pass
    time.sleep(random.uniform(4, 7))

    if is_rate_limited(page):
        return "RATELIMIT", "Холд после отправки"

    if "sign-in" in page.url or "appleid.apple.com" in page.url:
        return "NEED_LOGIN", "Выброс на логин"

    try:
        body = page.inner_text("body").lower()
    except:
        return "ERROR", "Не удалось прочитать страницу"

    if any(w in body for w in ["success", "enjoy", "already in your", "added to"]):
        return "VALID", "Принят"
    if "already" in body and any(w in body for w in ["redeemed", "used", "claimed"]):
        return "USED", "Уже использован"
    if any(w in body for w in ["not valid", "invalid", "cannot be found", "does not exist", "expired"]):
        return "INVALID", "Недействителен"
    if any(h in body for h in RATE_LIMIT_HINTS):
        return "RATELIMIT", "Холд в тексте ответа"

    # Возвращаем первые 300 символов для ручного анализа
    try:
        preview = page.inner_text("body")[:300].replace("\n", " ")
    except:
        preview = "?"
    return "UNKNOWN", preview


# ─────────────────────────────── session manager ──────────────────────────

class SessionManager:
    """Ротирует пары (аккаунт, прокси) с учётом лимитов."""

    def __init__(self, accounts, proxies):
        self.accounts = accounts
        self.proxies  = proxies if proxies else [None]
        self._build_pairs()
        self.pair_idx   = 0
        self.checks     = 0
        self.ctx        = None
        self.page       = None
        self._pw        = None

    def _build_pairs(self):
        # Каждый аккаунт работает со всеми прокси по очереди
        self.pairs = []
        accs = self.accounts if self.accounts else [None]
        for ai, acc in enumerate(accs):
            for pr in self.proxies:
                self.pairs.append((ai, pr))
        random.shuffle(self.pairs)

    def _current(self):
        return self.pairs[self.pair_idx % len(self.pairs)]

    def _open_session(self, pw):
        ai, pr = self._current()
        if self.ctx:
            try: self.ctx.close()
            except: pass
        self.ctx, self.page = make_browser(pw, ai, pr)
        if self.accounts:
            ensure_logged_in(self.page, ai, self.accounts)
        self.checks = 0
        proxy_str = f" | прокси: {pr}" if pr else ""
        acc_str = f"аккаунт #{ai+1}" if self.accounts else "без аккаунта"
        print(f"\n  Сессия: {acc_str}{proxy_str}")

    def start(self, pw):
        self._pw = pw
        self._open_session(pw)

    def rotate(self, reason="лимит"):
        print(f"\n  Ротация ({reason})...")
        self.pair_idx += 1
        if self.pair_idx >= len(self.pairs):
            # Все пары исчерпаны – ждём холд и сбрасываем цикл
            wait = random.randint(HOLD_SECS_MIN, HOLD_SECS_MAX)
            countdown(wait, "Все сессии на холде, ждём")
            self.pair_idx = 0
            random.shuffle(self.pairs)
        self._open_session(self._pw)

    def check_code(self, code):
        """Проверяет код, обрабатывает ротацию и холды. Возвращает (status, detail)."""
        while True:
            status, detail = attempt_check(self.page, code)

            if status == "RATELIMIT":
                self.rotate("холд от Apple")
                continue

            if status == "NEED_LOGIN":
                ai, pr = self._current()
                print(f"\n  Сессия #{ ai+1} протухла, перелогиниваюсь...")
                ensure_logged_in(self.page, ai, self.accounts)
                continue  # повтор той же пары

            self.checks += 1
            if self.checks >= MAX_PER_SESSION:
                # Плановая ротация до следующего кода
                self.rotate("плановая ротация")

            return status, detail

    def close(self):
        if self.ctx:
            try: self.ctx.close()
            except: pass


# ─────────────────────────────── main ─────────────────────────────────────

def main():
    print("\n" + "="*52)
    print("   iTunes / Apple Gift Card Code Checker")
    print("="*52 + "\n")

    codes    = read_lines(CODES_FILE)
    accounts = read_lines(ACCOUNTS_FILE)
    proxies  = read_lines(PROXIES_FILE)

    if not codes:
        print(f"ОШИБКА: {CODES_FILE} пуст или не существует!")
        input("Enter для выхода...")
        return

    checked = {}
    if os.path.exists(RESULTS_FILE):
        ans = input("Продолжить с прошлого места? (да/нет): ").strip().lower()
        if ans in ("да", "д", "y", "yes"):
            checked = load_checked()
            print(f"  Пропускаю уже проверенных: {len(checked)}")
        else:
            os.remove(RESULTS_FILE)

    remaining = [c for c in codes if c not in checked]
    total     = len(remaining)

    print(f"\n  Кодов всего:     {len(codes)}")
    print(f"  Уже проверено:   {len(checked)}")
    print(f"  Осталось:        {total}")
    print(f"  Аккаунтов:       {len(accounts) if accounts else 'нет (один браузер)'}")
    print(f"  Прокси:          {len(proxies) if proxies else 'нет'}")
    print(f"  Макс. на сессию: {MAX_PER_SESSION}")
    print()

    if not remaining:
        print("Все коды уже проверены!")
        input("Enter...")
        return

    stats = {"VALID": 0, "USED": 0, "INVALID": 0, "UNKNOWN": 0, "ERROR": 0}
    start_ts = time.time()

    sm = SessionManager(accounts, proxies)

    with sync_playwright() as pw:
        sm.start(pw)

        with open(RESULTS_FILE, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            if not checked:
                writer.writerow(["code", "status", "detail", "checked_at"])

            for i, code in enumerate(remaining, 1):
                elapsed = time.time() - start_ts
                speed   = i / elapsed * 3600 if elapsed > 0 else 0
                eta_sec = (total - i) / (i / elapsed) if elapsed > 0 and i > 0 else 0
                print(
                    f"[{i:>5}/{total}] {code:<30} "
                    f"| {fmt_time(elapsed)} прошло | ETA {fmt_time(eta_sec)}"
                )

                try:
                    status, detail = sm.check_code(code)
                except Exception as e:
                    status, detail = "ERROR", str(e)
                    traceback.print_exc()

                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                writer.writerow([code, status, detail[:300], ts])
                f.flush()

                key = status if status in stats else "ERROR"
                stats[key] = stats.get(key, 0) + 1

                tag = {
                    "VALID":   "✓ VALID  ",
                    "USED":    "~ USED   ",
                    "INVALID": "✗ INVALID",
                    "UNKNOWN": "? UNKNOWN",
                    "ERROR":   "! ERROR  ",
                }.get(status, status)
                print(f"           -> {tag}  {detail[:80]}")

                time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

        sm.close()

    print("\n" + "="*52)
    print("  ГОТОВО!")
    print(f"  VALID:   {stats.get('VALID', 0)}")
    print(f"  USED:    {stats.get('USED', 0)}")
    print(f"  INVALID: {stats.get('INVALID', 0)}")
    print(f"  UNKNOWN: {stats.get('UNKNOWN', 0)}")
    print(f"  ERROR:   {stats.get('ERROR', 0)}")
    print(f"\n  Результаты: {RESULTS_FILE}")
    print("="*52)
    input("\nНажми Enter для выхода...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nОстановлено пользователем.")
    except Exception:
        traceback.print_exc()
        input("Enter для выхода...")
