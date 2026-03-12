"""
Fonlor TEFAS Scraper
TEFAS'ın gizli JSON API endpoint'lerini kullanarak gerçek veri çeker.
Tarayıcı header'ları ile istek atar, rate limiting uygular.
"""

import requests
import json
import time
import datetime
from typing import Optional

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.tefas.gov.tr/FonAnaliz.aspx",
    "Origin": "https://www.tefas.gov.tr",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
})

BASE = "https://www.tefas.gov.tr/api/DB"


def _post(endpoint: str, params: dict, retries=3) -> Optional[dict]:
    """TEFAS API'ye POST isteği atar. Hata durumunda retry yapar."""
    url = f"{BASE}/{endpoint}"
    for attempt in range(retries):
        try:
            resp = SESSION.post(url, data=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            print(f"  ⏱ Timeout ({attempt+1}/{retries}): {endpoint}")
            time.sleep(2 ** attempt)
        except requests.exceptions.HTTPError as e:
            print(f"  ❌ HTTP {e.response.status_code}: {endpoint}")
            if e.response.status_code == 429:
                time.sleep(10)  # rate limit
            else:
                break
        except Exception as e:
            print(f"  ❌ Hata: {e}")
            time.sleep(1)
    return None


def get_fund_list(fund_type: str = "YAT") -> list[dict]:
    """
    Tüm fonların listesini çeker.
    fund_type: "YAT" = yatırım fonları, "EME" = emeklilik fonları
    """
    today = datetime.date.today().strftime("%d.%m.%Y")
    params = {
        "fontip": fund_type,
        "sfontur": "",
        "fonkod": "",
        "fongrup": "",
        "bastarih": today,
        "bittarih": today,
        "fonturkod": "",
        "fonunvantip": "",
    }
    data = _post("BindFundComparisonList", params)
    if not data or "data" not in data:
        return []
    return data["data"]


def get_fund_detail(fund_code: str) -> Optional[dict]:
    """
    Tek bir fonun detay bilgilerini çeker:
    fiyat, büyüklük, yatırımcı sayısı, günlük/haftalık/aylık getiri
    """
    today = datetime.date.today().strftime("%d.%m.%Y")
    params = {
        "fontip": "YAT",
        "fonkod": fund_code,
        "bastarih": today,
        "bittarih": today,
    }
    data = _post("BindHistoryInfo", params)
    if not data or "data" not in data or not data["data"]:
        return None
    return data["data"][0]


def get_fund_history(fund_code: str, days: int = 365) -> list[dict]:
    """
    Bir fonun geçmiş fiyat verilerini çeker.
    days: kaç günlük geçmiş (30, 90, 180, 365, 1095, 1825)
    """
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days)
    params = {
        "fontip": "YAT",
        "fonkod": fund_code,
        "bastarih": start.strftime("%d.%m.%Y"),
        "bittarih": end.strftime("%d.%m.%Y"),
    }
    data = _post("BindHistoryInfo", params)
    if not data or "data" not in data:
        return []
    # Tarihe göre sırala (eskiden yeniye)
    rows = data["data"]
    rows.sort(key=lambda x: x.get("TARIH", ""))
    return rows


def get_fund_portfolio(fund_code: str) -> list[dict]:
    """
    Bir fonun portföy pozisyonlarını çeker (KAP'tan aylık yayınlanan).
    """
    params = {
        "fonkod": fund_code,
    }
    data = _post("BindFundPortfolio", params)
    if not data or "data" not in data:
        return []
    return data["data"]


def get_all_funds_with_returns() -> list[dict]:
    """
    Tüm fonları + dönemsel getirilerini tek seferde çeker.
    Bu endpoint TEFAS'ın karşılaştırma sayfasında kullanılıyor.
    """
    today = datetime.date.today().strftime("%d.%m.%Y")
    month_ago = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%d.%m.%Y")
    params = {
        "fontip": "YAT",
        "sfontur": "",
        "fonkod": "",
        "fongrup": "",
        "bastarih": month_ago,
        "bittarih": today,
        "fonturkod": "",
        "fonunvantip": "",
    }
    data = _post("BindFundComparisonList", params)
    if not data or "data" not in data:
        return []
    return data["data"]


def calculate_return(history: list[dict]) -> dict:
    """Fiyat geçmişinden dönemsel getirileri hesaplar."""
    if len(history) < 2:
        return {}

    def pct(old, new):
        if not old or old == 0:
            return None
        return round((new - old) / old * 100, 2)

    prices = [(r.get("TARIH"), float(r.get("FIYAT", 0) or 0)) for r in history if r.get("FIYAT")]
    if not prices:
        return {}

    latest_date, latest_price = prices[-1]
    now = datetime.date.today()

    def price_n_days_ago(n):
        target = now - datetime.timedelta(days=n)
        # En yakın tarihi bul
        for date_str, price in reversed(prices[:-1]):
            try:
                d = datetime.datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S").date()
                if d <= target:
                    return price
            except:
                pass
        return prices[0][1]  # fallback: ilk fiyat

    return {
        "r1m": pct(price_n_days_ago(30), latest_price),
        "r3m": pct(price_n_days_ago(90), latest_price),
        "r6m": pct(price_n_days_ago(180), latest_price),
        "r1y": pct(price_n_days_ago(365), latest_price),
        "ytd": pct(price_n_days_ago((now - datetime.date(now.year, 1, 1)).days), latest_price),
    }


# ─── Hızlı test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🔍 TEFAS bağlantısı test ediliyor...")
    funds = get_fund_list()
    if funds:
        print(f"✅ {len(funds)} fon bulundu")
        print(f"   Örnek: {funds[0]}")
    else:
        print("❌ Veri çekilemedi")

    print("\n🔍 AFT detayı test ediliyor...")
    detail = get_fund_detail("AFT")
    if detail:
        print(f"✅ AFT: {detail}")
    else:
        print("❌ AFT detayı çekilemedi")
