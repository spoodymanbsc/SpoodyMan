"""
Обновление цен WB — запускать вручную.
Использование:
    python update_prices.py <файл_wb.xlsx> [выходной_файл.xlsx]

Если выходной файл не указан — сохраняется как <имя>_updated.xlsx
"""

import sys
import re
import math
import json
import urllib.request
import urllib.error
from pathlib import Path

import openpyxl


# ─────────────────────────────────────────
# 1. КУРСЫ ЦБ РФ
# ─────────────────────────────────────────

def get_cbr_rates() -> dict:
    url = "https://www.cbr-xml-daily.ru/daily_json.js"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    valute = data["Valute"]
    return {
        "USD": valute["USD"]["Value"],
        "EUR": valute["EUR"]["Value"],
        "TRY": valute["TRY"]["Value"],
        "PLN": valute["PLN"]["Value"],
    }


# ─────────────────────────────────────────
# 2. ПАРСИНГ ЦЕНЫ С PLATI.MARKET
# ─────────────────────────────────────────

def parse_plati_price(url: str) -> float | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        # <meta itemprop="price" content="1234">
        m = re.search(r'<meta[^>]+itemprop=["\']price["\'][^>]+content=["\']([0-9.]+)["\']', html)
        if not m:
            m = re.search(r'content=["\']([0-9.]+)["\'][^>]+itemprop=["\']price["\']', html)
        if m:
            return float(m.group(1))
    except Exception as e:
        print(f"  [!] Ошибка парсинга {url}: {e}")
    return None


PLATI_URLS = {
    "arc raiders":      "https://plati.market/itm/arc-raiders-steam-ru-cis/5521625",
    "gta 5":            "https://plati.market/itm/grand-theft-auto-v-enhanced-online-gta-5-region-free/3359876",
    "gta5":             "https://plati.market/itm/grand-theft-auto-v-enhanced-online-gta-5-region-free/3359876",
    "ghost recon":      "https://plati.market/itm/tom-clancy-s-ghost-recon-breakpoint-ubisoft-key/3431967",
    "forza":            "https://plati.market/itm/forza-horizon-6-standard-deluxe-premium-steam-ru/5659814",
}


# ─────────────────────────────────────────
# 3. ROBLOX — оптимальная комбинация карт
# ─────────────────────────────────────────

# карта (робуксов): цена в рублях
ROBUX_CARDS = {
    100:   235,
    200:   235,
    800:   644,
    1000:  851,
    2000:  1574,
    4500:  3427,
    10000: 7105,
}

def best_robux_price(need: int) -> int | None:
    """Минимальная стоимость через комбинацию карт (DP)."""
    denominations = sorted(ROBUX_CARDS.keys())
    INF = float("inf")
    # dp[i] = (min_cost, list_of_cards)
    dp = [INF] * (need + 1)
    dp[0] = 0
    prev = [-1] * (need + 1)
    card_used = [0] * (need + 1)

    for i in range(1, need + 1):
        for d in denominations:
            if d <= i and dp[i - d] + ROBUX_CARDS[d] < dp[i]:
                dp[i] = dp[i - d] + ROBUX_CARDS[d]
                prev[i] = i - d
                card_used[i] = d

    if dp[need] == INF:
        # Если точной суммы нет — берём ближайшее сверху кратное
        for extra in range(1, 200):
            target = need + extra
            if target >= len(dp):
                dp2 = [INF] * (target + 1)
                dp2[:len(dp)] = dp
                dp = dp2
                prev += [-1] * (target + 1 - len(prev))
                card_used += [0] * (target + 1 - len(card_used))
            for d in denominations:
                if d <= target and dp[target - d] + ROBUX_CARDS.get(d, INF) < dp[target]:
                    dp[target] = dp[target - d] + ROBUX_CARDS[d]
                    prev[target] = target - d
                    card_used[target] = d
            if dp[target] < INF:
                return round(dp[target])
        return None
    return round(dp[need])


# ─────────────────────────────────────────
# 4. PUBG UC — цены карт в $
# ─────────────────────────────────────────

PUBG_UC_CARDS_USD = {
    60:   0.9297,
    325:  4.6786,
    660:  9.3652,
    1800: 23.428,
    3850: 46.8667,
    8100: 93.739,
}

def best_pubg_price(need: int, usd_rate: float) -> int | None:
    """Минимальная стоимость UC через комбинацию карт (DP), в рублях."""
    if need == 10:
        return 50

    denominations = sorted(PUBG_UC_CARDS_USD.keys())
    INF = float("inf")

    # DP по количеству UC
    max_uc = need + max(denominations)
    dp = [INF] * (max_uc + 1)
    dp[0] = 0.0

    for i in range(1, max_uc + 1):
        for d in denominations:
            if d <= i and dp[i - d] + PUBG_UC_CARDS_USD[d] < dp[i]:
                dp[i] = dp[i - d] + PUBG_UC_CARDS_USD[d]

    # Ищем минимум для >= need
    best_usd = INF
    for i in range(need, max_uc + 1):
        if dp[i] < best_usd:
            best_usd = dp[i]
            break

    if best_usd == INF:
        return None
    return round(best_usd * usd_rate * 1.55)


# ─────────────────────────────────────────
# 5. CoC / CR ГЕМЫ — комбинация
# ─────────────────────────────────────────

COC_CARDS = {
    80:    78,
    500:   398,
    1200:  798,
    2500:  1597,
    6500:  3993,
    14000: 7986,
}

def best_coc_price(need: int) -> int | None:
    denominations = sorted(COC_CARDS.keys())
    INF = float("inf")
    max_gems = need + max(denominations)
    dp = [INF] * (max_gems + 1)
    dp[0] = 0

    for i in range(1, max_gems + 1):
        for d in denominations:
            if d <= i and dp[i - d] + COC_CARDS[d] < dp[i]:
                dp[i] = dp[i - d] + COC_CARDS[d]

    for i in range(need, max_gems + 1):
        if dp[i] < INF:
            return dp[i]
    return None


# ─────────────────────────────────────────
# 6. BRAWL STARS ГЕМЫ — комбинация
# ─────────────────────────────────────────

BRAWL_CARDS = {
    30:  158,
    80:  398,
    170: 798,
    360: 1597,
    950: 3993,
}

def best_brawl_price(need: int) -> int | None:
    denominations = sorted(BRAWL_CARDS.keys())
    INF = float("inf")
    max_gems = need + max(denominations)
    dp = [INF] * (max_gems + 1)
    dp[0] = 0

    for i in range(1, max_gems + 1):
        for d in denominations:
            if d <= i and dp[i - d] + BRAWL_CARDS[d] < dp[i]:
                dp[i] = dp[i - d] + BRAWL_CARDS[d]

    for i in range(need, max_gems + 1):
        if dp[i] < INF:
            return dp[i]
    return None


# ─────────────────────────────────────────
# 7. VALORANT VP — фиксированные цены
# ─────────────────────────────────────────

VALORANT_PRICES = {
    240:   249,
    475:   399,
    1000:  777,
    1520:  1199,
    2050:  1699,
    2550:  1999,
    3650:  2999,
    5350:  3999,
    8700:  6199,
    11000: 7999,
}


# ─────────────────────────────────────────
# 8. ИЗВЛЕЧЕНИЕ ЧИСЛА И ВАЛЮТЫ ИЗ НАЗВАНИЯ
# ─────────────────────────────────────────

def extract_amount_currency(name: str):
    """Возвращает (amount: float, currency: str) или (None, None)."""
    name_lower = name.lower()

    # TRY
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*try', name_lower)
    if m:
        return float(m.group(1).replace(",", ".")), "TRY"

    # PLN
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*pln', name_lower)
    if m:
        return float(m.group(1).replace(",", ".")), "PLN"

    # EUR / Евро
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:евро|eur\b|euro)', name_lower)
    if m:
        return float(m.group(1).replace(",", ".")), "EUR"

    # USD / $
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*\$', name_lower)
    if not m:
        m = re.search(r'\$\s*(\d+(?:[.,]\d+)?)', name_lower)
    if not m:
        m = re.search(r'(\d+(?:[.,]\d+)?)\s*usd', name_lower)
    if m:
        return float(m.group(1).replace(",", ".")), "USD"

    return None, None


# ─────────────────────────────────────────
# 9. ОСНОВНАЯ ЛОГИКА РАСЧЁТА ЦЕНЫ
# ─────────────────────────────────────────

def calc_price(name: str, rates: dict, plati_cache: dict) -> tuple[int | None, str]:
    """
    Возвращает (новая_цена: int, комментарий: str).
    Комментарий — краткое описание источника цены.
    """
    n = name.strip()
    nl = n.lower()
    usd = rates["USD"]

    # ── Valorant VP ──────────────────────────────────────
    if "валорант" in nl or "valorant" in nl:
        m = re.search(r'(\d+)\s*vp', nl)
        if m:
            vp = int(m.group(1))
            price = VALORANT_PRICES.get(vp)
            if price:
                return price, f"Valorant {vp} VP (фикс)"
            return None, f"Valorant {vp} VP — нет в прайсе"

    # ── PUBG UC ──────────────────────────────────────────
    if "pubg" in nl or "пабг" in nl:
        m = re.search(r'(\d+)\s*юс|uc[^\d]*(\d+)|(\d+)\s*uc', nl)
        if not m:
            m = re.search(r'[-–]\s*(\d+)', nl)
        if m:
            uc = int(next(g for g in m.groups() if g))
            price = best_pubg_price(uc, usd)
            if price:
                return price, f"PUBG {uc} UC"
        return None, "PUBG — не удалось извлечь UC"

    # ── Roblox ───────────────────────────────────────────
    if "roblox" in nl or "роблокс" in nl or "робукс" in nl:
        # Пропускаем Freaky Fly и подобные карты без числа робуксов
        if any(x in nl for x in ["freaky", "void sheep", "hungry orca", "knife crown"]):
            return None, "Roblox карта-предмет (нет цены)"
        m = re.search(r'(\d+)\s*(?:робукс|robux)', nl)
        if m:
            robux = int(m.group(1))
            price = best_robux_price(robux)
            if price:
                return price, f"Roblox {robux} robux (комбо)"
        return None, "Roblox — не удалось извлечь кол-во"

    # ── Clash of Clans / Clash Royale ────────────────────
    if "clash" in nl:
        if "gold pass" in nl:
            return 557, "CoC Gold Pass (фикс)"
        if "diamond pass" in nl:
            return 957, "CR Diamond Pass (фикс)"
        m = re.search(r'(\d+)\s*gems?', nl)
        if m:
            gems = int(m.group(1))
            price = best_coc_price(gems)
            if price:
                return price, f"CoC/CR {gems} gems (комбо)"
        return None, "Clash — не удалось извлечь кол-во"

    # ── Brawl Stars ──────────────────────────────────────
    if "brawl" in nl:
        if "brawl pass pro" in nl:
            return 1996, "Brawl Pass Pro (фикс)"
        if "brawl pass plus" in nl or "pass plus" in nl:
            return 1054, "Brawl Pass Plus (фикс)"
        if "brawl pass" in nl or "бравл пасс" in nl:
            return 729, "Brawl Pass (фикс)"
        m = re.search(r'(\d+)\s*gems?', nl)
        if m:
            gems = int(m.group(1))
            price = best_brawl_price(gems)
            if price:
                return price, f"Brawl Stars {gems} gems (комбо)"
        return None, "Brawl Stars — не удалось извлечь кол-во"

    # ── PC Games ─────────────────────────────────────────
    if "minecraft" in nl or "майнкрафт" in nl:
        price = round(16.75 * usd * 1.55)
        return price, f"Minecraft $16.75 × {usd:.2f} × 1.55"

    if "forza" in nl:
        if "premium" in nl:
            return 9599, "Forza Premium (фикс)"
        if "deluxe" in nl:
            return 7799, "Forza Deluxe (фикс)"
        return 5299, "Forza Standard (фикс)"

    if "007" in nl or "first light" in nl:
        return 2645, "007 First Light (фикс)"

    if "arc raiders" in nl:
        key = "arc raiders"
        if key not in plati_cache:
            plati_cache[key] = parse_plati_price(PLATI_URLS[key])
        p = plati_cache[key]
        return (round(p), "Arc Raiders (plati.market)") if p else (None, "Arc Raiders — ошибка парсинга")

    if "gta" in nl or "grand theft" in nl:
        key = "gta 5"
        if key not in plati_cache:
            plati_cache[key] = parse_plati_price(PLATI_URLS[key])
        p = plati_cache[key]
        return (round(p), "GTA 5 (plati.market)") if p else (None, "GTA 5 — ошибка парсинга")

    if "ghost recon" in nl:
        key = "ghost recon"
        if key not in plati_cache:
            plati_cache[key] = parse_plati_price(PLATI_URLS[key])
        p = plati_cache[key]
        return (round(p), "Ghost Recon (plati.market)") if p else (None, "Ghost Recon — ошибка парсинга")

    # ── Карты оплаты: Apple, Xbox, Nintendo, Blizzard, Razer ──
    is_payment_card = any(x in nl for x in [
        "apple", "xbox", "nintendo", "blizzard", "razer", "карта пополнения"
    ])
    if is_payment_card:
        amount, currency = extract_amount_currency(n)
        if amount and currency:
            rate = rates.get(currency)
            if rate:
                price = round(amount * rate * 1.55)
                return price, f"{amount} {currency} × {rate:.4f} × 1.55"
            return None, f"Нет курса для {currency}"
        return None, "Карта оплаты — не удалось извлечь сумму/валюту"

    return None, "Не распознан тип товара"


# ─────────────────────────────────────────
# 10. ЗАГРУЗКА МАППИНГА артикул→название
# ─────────────────────────────────────────

def load_names_map(names_xlsx: str) -> dict:
    """Возвращает {артикул_продавца: название}."""
    wb = openpyxl.load_workbook(names_xlsx, read_only=True)
    ws = wb["Товары"]
    result = {}
    for i, row in enumerate(ws.iter_rows(min_row=5, values_only=True)):
        art = row[1]   # Артикул продавца
        name = row[3]  # Наименование
        if art and name:
            result[str(art).strip()] = str(name).strip()
    wb.close()
    return result


# ─────────────────────────────────────────
# 11. ГЛАВНАЯ ФУНКЦИЯ
# ─────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print("Использование:")
        print("  python update_prices.py <wb_prices.xlsx> <wb_names.xlsx> [output.xlsx]")
        sys.exit(1)

    prices_file = sys.argv[1]
    names_file  = sys.argv[2]
    out_file    = sys.argv[3] if len(sys.argv) > 3 else str(
        Path(prices_file).with_name(Path(prices_file).stem + "_updated.xlsx")
    )

    print("Загружаю курсы ЦБ РФ...")
    rates = get_cbr_rates()
    for cur, val in rates.items():
        print(f"  {cur}: {val:.4f} ₽")

    print("\nЗагружаю названия товаров...")
    names_map = load_names_map(names_file)
    print(f"  Найдено {len(names_map)} товаров с названиями")

    print("\nОбрабатываю файл цен...")
    wb = openpyxl.load_workbook(prices_file)
    ws = wb.active

    plati_cache = {}
    updated = 0
    skipped = []

    for row_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
        art_cell      = row[3]   # D — Артикул продавца
        new_price_cell = row[9]  # J — Новая цена, RUB

        art = str(art_cell.value).strip() if art_cell.value else ""
        name = names_map.get(art, "")

        if not name:
            skipped.append((art, "нет названия в файле товаров"))
            continue

        price, comment = calc_price(name, rates, plati_cache)

        if price:
            new_price_cell.value = price
            updated += 1
            print(f"  [{row_idx:3d}] {art:<25} → {price:>8} ₽  ({comment})")
        else:
            skipped.append((art, f"{name[:40]} | {comment}"))

    wb.save(out_file)

    print(f"\n✓ Обновлено: {updated}")
    print(f"✗ Пропущено: {len(skipped)}")
    if skipped:
        print("\nПропущенные товары:")
        for art, reason in skipped:
            print(f"  {art:<25} — {reason}")

    print(f"\nФайл сохранён: {out_file}")


if __name__ == "__main__":
    main()
