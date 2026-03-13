"""
Fonlor Scraper - TEFAS veri cekici v3
"""
import requests, datetime, re

BASE = "https://www.tefas.gov.tr"
API  = BASE + "/api/DB/"

HEADERS_API = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": BASE + "/TarihselVeriler.aspx",
    "Origin": BASE,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
}
HEADERS_HTML = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

def _post(endpoint, params):
    try:
        r = requests.post(API + endpoint, data=params, headers=HEADERS_API, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[scraper] {endpoint} HATA: {e}")
        return None

def _get_html(fund_code):
    """FonAnaliz sayfasini cek, session ile."""
    s = requests.Session()
    s.headers.update(HEADERS_HTML)
    # Once ana sayfayi ziyaret et (session/cookie icin)
    try:
        s.get(BASE, timeout=10)
    except: pass
    r = s.get(f"{BASE}/FonAnaliz.aspx?FonKod={fund_code}", timeout=20)
    r.raise_for_status()
    return r.text

def get_all_funds_with_returns():
    today = datetime.date.today().strftime("%d.%m.%Y")
    year_start = datetime.date(datetime.date.today().year, 1, 1).strftime("%d.%m.%Y")

    data = _post("BindFundComparisonList", {
        "fontip": "YAT", "sfontur": "", "fonkod": "", "fongrup": "",
        "bastarih": year_start, "bittarih": today,
        "fonturkod": "", "fonunvantip": "",
    })
    if data and "data" in data and data["data"]:
        print(f"[scraper] BindFundComparisonList OK: {len(data['data'])} fon")
        return data["data"]

    data = _post("BindHistoryInfo", {
        "fontip": "YAT", "fonkod": "",
        "bastarih": today, "bittarih": today,
    })
    if data and "data" in data:
        return data["data"]
    return []

def get_fund_detail(fund_code):
    """TEFAS FonAnaliz HTML'inden tam detay cek."""
    try:
        html = _get_html(fund_code)

        def strip_tags(s):
            return re.sub(r'<[^>]+>', '', s).strip()

        def clean_num(s):
            if not s: return None
            return s.replace('%','').replace('.','').replace(',','.').strip()

        # Fon adi - h2 tag'inden
        name_m = re.search(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL)
        name = strip_tags(name_m.group(1)) if name_m else ""

        # Son fiyat
        price_m = re.search(r'Son Fiyat[^<]*(?:<[^>]+>){1,5}\s*([\d,\.]+)', html, re.DOTALL)
        price = clean_num(price_m.group(1)) if price_m else None

        # Getiriler - metin formatinda geliyor
        def get_ret(label):
            # "Son 1 Ay Getirisi\n%-1,263417" gibi
            m = re.search(re.escape(label) + r'\s*\n\s*%?\s*([-\d,\.]+)', html)
            if m: return clean_num(m.group(1))
            # HTML entity ile: "Son 1 Ay Getirisi<...>%-1.26"
            m = re.search(re.escape(label) + r'[^%]*%\s*([-\d,\.]+)', html, re.DOTALL)
            if m: return clean_num(m.group(1))
            return None

        r1m  = get_ret("Son 1 Ay Getirisi")
        r3m  = get_ret("Son 3 Ay Getirisi")
        r6m  = get_ret("Son 6 Ay Getirisi")
        r1y  = get_ret("Son 1 Yıl Getirisi")

        # YTD - Yilbasından itibaren
        ytd_m = re.search(r'Yılbaşından İtibaren[^%\d-]*%?\s*([-\d,\.]+)', html)
        ytd = clean_num(ytd_m.group(1)) if ytd_m else None

        # AUM
        aum_m = re.search(r'Fon Toplam Değer[^<]*(?:<[^>]+>){1,5}\s*([\d\.,]+)', html, re.DOTALL)
        aum = clean_num(aum_m.group(1)) if aum_m else None

        # Yatirimci
        inv_m = re.search(r'Yatırımcı Sayısı[^<]*(?:<[^>]+>){1,5}\s*([\d\.]+)', html, re.DOTALL)
        investors = inv_m.group(1).replace('.','') if inv_m else None

        # Risk
        risk_m = re.search(r'Fonun Risk Değeri[^<]*(?:<[^>]+>){1,5}[^<]*?(\d)\s*<', html, re.DOTALL)
        risk = risk_m.group(1) if risk_m else None

        # Kategori
        cat_m = re.search(r'Kategorisi[^<]*(?:<[^>]+>){1,5}\s*([^<\n]+)', html, re.DOTALL)
        cat = cat_m.group(1).strip() if cat_m else None

        # Gunluk degisim
        chg_m = re.search(r'Günlük Getiri[^%]*%\s*([-\d,\.]+)', html)
        daily_chg = clean_num(chg_m.group(1)) if chg_m else None

        print(f"[scraper] get_fund_detail {fund_code}: fiyat={price}, r1y={r1y}, r1m={r1m}")

        return {
            "FONKODU":    fund_code,
            "FONUNVAN":   name,
            "FIYAT":      price,
            "PORTFOYBUYUKLUK": aum,
            "KISISAYISI": investors,
            "GETIRI1AY":  r1m,
            "GETIRI3AY":  r3m,
            "GETIRI6AY":  r6m,
            "GETIRI1YIL": r1y,
            "GETIRIYTD":  ytd,
            "RISKDEGERI": risk,
            "KATEGORI":   cat,
            "GUNLUKGETIRI": daily_chg,
        }
    except Exception as e:
        print(f"[scraper] get_fund_detail HATA ({fund_code}): {e}")
        return None

def get_fund_history(fund_code, days=1825):
    end   = datetime.date.today()
    start = end - datetime.timedelta(days=days)
    data = _post("BindHistoryInfo", {
        "fontip": "YAT", "fonkod": fund_code,
        "bastarih": start.strftime("%d.%m.%Y"),
        "bittarih": end.strftime("%d.%m.%Y"),
    })
    if not data or "data" not in data:
        return []
    rows = data["data"]
    rows = [r for r in rows if str(r.get("FONKODU","")).upper() == fund_code.upper()]

    def parse_date(val):
        s = str(val)
        if s.isdigit() and len(s) > 8:
            try:
                return datetime.datetime.fromtimestamp(int(s)/1000).strftime("%Y-%m-%d")
            except: pass
        try:
            return datetime.datetime.strptime(s[:10], "%d.%m.%Y").strftime("%Y-%m-%d")
        except: pass
        return s[:10]

    for r in rows:
        r["_DATE"] = parse_date(r.get("TARIH"))

    rows.sort(key=lambda x: x["_DATE"])
    return rows

def get_fund_portfolio(fund_code):
    """Portfoy verisi - once API, sonra HTML."""
    # Session ile API dene
    s = requests.Session()
    s.headers.update(HEADERS_HTML)
    try:
        s.get(BASE, timeout=10)
        s.get(f"{BASE}/FonAnaliz.aspx?FonKod={fund_code}", timeout=10)
    except: pass

    try:
        r = s.post(API + "BindFundPortfolio", 
                   data={"fonkod": fund_code},
                   headers={**HEADERS_API, "Referer": f"{BASE}/FonAnaliz.aspx"},
                   timeout=20)
        data = r.json()
        if data and "data" in data and data["data"]:
            print(f"[scraper] portfolio API OK: {len(data['data'])} pozisyon")
            return data["data"]
    except Exception as e:
        print(f"[scraper] portfolio API HATA: {e}")

    # HTML'den parse et
    try:
        html = s.get(f"{BASE}/FonAnaliz.aspx?FonKod={fund_code}", timeout=20).text
        return _parse_portfolio_from_html(html)
    except Exception as e:
        print(f"[scraper] portfolio HTML HATA: {e}")
    return []

def _parse_portfolio_from_html(html):
    """HTML'den portfoy pie chart datasini cek."""
    portfolio = []
    # Highcharts veya chart data
    # "name:'Yabancı Hisse Senedi',y:98.49" gibi
    chart_m = re.findall(r"name\s*:\s*'([^']+)'\s*,\s*y\s*:\s*([\d\.]+)", html)
    if chart_m:
        for name, pct in chart_m:
            portfolio.append({
                "VARLIKADI": name,
                "PORTAYPAYORAN": float(pct),
            })
        return portfolio

    # Alternatif: data:[{name:...,y:...}]
    chart_m2 = re.findall(r'"name"\s*:\s*"([^"]+)"\s*,\s*"y"\s*:\s*([\d\.]+)', html)
    for name, pct in chart_m2:
        portfolio.append({"VARLIKADI": name, "PORTAYPAYORAN": float(pct)})

    return portfolio

def calculate_return(history):
    if len(history) < 2: return {}
    def pct(old, new):
        if not old or old == 0: return None
        return round((new - old) / old * 100, 2)
    prices = []
    for r in history:
        try:
            f = r.get("FIYAT")
            d = r.get("_DATE") or r.get("TARIH")
            if f and d:
                prices.append((str(d)[:10], float(str(f).replace(",", "."))))
        except: pass
    if not prices: return {}
    _, lp = prices[-1]
    now = datetime.date.today()
    def p(n):
        t = now - datetime.timedelta(days=n)
        for ds, pr in reversed(prices[:-1]):
            try:
                if datetime.datetime.strptime(ds[:10], "%Y-%m-%d").date() <= t:
                    return pr
            except: pass
        return prices[0][1]
    return {
        "r1m": pct(p(30), lp), "r3m": pct(p(90), lp),
        "r6m": pct(p(180), lp), "r1y": pct(p(365), lp),
    }
