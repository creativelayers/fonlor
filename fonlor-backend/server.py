"""
Fonlor Backend API - tefas-crawler versiyonu
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
import scraper
import time
import datetime
import os

app = Flask(__name__)
CORS(app, origins="*")

_cache = {}
CACHE_TTL = 300

def cache_get(key):
    if key in _cache:
        val, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return val
    return None

def cache_set(key, val):
    _cache[key] = (val, time.time())

@app.route("/")
def health():
    return jsonify({"status":"ok","app":"Fonlor API","version":"2.0.0"})

@app.route("/api/funds")
def funds():
    cached = cache_get("funds_all")
    if cached:
        funds_data = cached
    else:
        raw = scraper.get_all_funds_with_returns()
        if not raw:
            return jsonify({"error":"TEFAS'tan veri çekilemedi"}), 503

        funds_data = []
        for f in raw:
            # tefas-crawler sütun isimleri (İngilizce)
            name = f.get("title") or f.get("FONUNVAN","")
            funds_data.append({
                "code":      str(f.get("code") or f.get("FONKODU","")),
                "name":      name,
                "cat":       map_category_from_type(f.get("fund_type",""), name),
                "katilim":   "KATILIM" in name.upper(),
                "price":     safe_float(f.get("price") or f.get("FIYAT")),
                "aum":       safe_float(f.get("market_cap") or f.get("PORTFOYBUYUKLUK")),
                "investors": safe_int(f.get("number_of_investors") or f.get("YATIRIMCISAYISI")),
                "r1m":       safe_float(f.get("monthly_return") or f.get("GETIRI1AY")),
                "r3m":       safe_float(f.get("quarterly_return") or f.get("GETIRI3AY")),
                "r6m":       safe_float(f.get("semiannual_return") or f.get("GETIRI6AY")),
                "r1y":       safe_float(f.get("annual_return") or f.get("GETIRI1YIL")),
                "ytd":       safe_float(f.get("ytd_return") or f.get("GETIRIYTD")),
                "risk":      safe_int(f.get("risk_value") or f.get("RISKDEGERI")),
            })

        cache_set("funds_all", funds_data)

    cat_filter = request.args.get("cat","")
    q_filter = request.args.get("q","").lower()
    result = funds_data
    if cat_filter:
        result = [f for f in result if f["cat"] == cat_filter]
    if q_filter:
        result = [f for f in result if q_filter in f["code"].lower() or q_filter in f["name"].lower()]

    return jsonify({"count":len(result),"updated_at":datetime.datetime.now().isoformat(),"funds":result})

@app.route("/api/fund/<code>")
def fund_detail(code):
    code = code.upper()
    cached = cache_get(f"fund_{code}")
    if cached: return jsonify(cached)

    detail = scraper.get_fund_detail(code)
    if not detail:
        return jsonify({"error":f"{code} bulunamadı"}), 404

    name = detail.get("title") or detail.get("FONUNVAN","")
    result = {
        "code":      code,
        "name":      name,
        "price":     safe_float(detail.get("price") or detail.get("FIYAT")),
        "aum":       safe_float(detail.get("market_cap") or detail.get("PORTFOYBUYUKLUK")),
        "investors": safe_int(detail.get("number_of_investors") or detail.get("YATIRIMCISAYISI")),
        "date":      str(detail.get("date") or detail.get("TARIH","")),
        "cat":       map_category_from_type(detail.get("fund_type",""), name),
        "risk":      safe_int(detail.get("risk_value") or detail.get("RISKDEGERI")),
    }
    cache_set(f"fund_{code}", result)
    return jsonify(result)

@app.route("/api/fund/<code>/history")
def fund_history(code):
    code = code.upper()
    days = int(request.args.get("days", 365))
    cache_key = f"history_{code}_{days}"
    cached = cache_get(cache_key)
    if cached: return jsonify(cached)

    raw = scraper.get_fund_history(code, days)
    if not raw:
        return jsonify({"error":"Geçmiş veri bulunamadı"}), 404

    history = [{"date": str(r.get("date",""))[:10], "price": safe_float(r.get("price")),
                "aum": safe_float(r.get("market_cap")), "investors": safe_int(r.get("number_of_investors"))}
               for r in raw if r.get("price")]
    returns = scraper.calculate_return(raw)
    result = {"code":code,"history":history,"returns":returns}
    cache_set(cache_key, result)
    return jsonify(result)

@app.route("/api/fund/<code>/portfolio")
def fund_portfolio(code):
    code = code.upper()
    cached = cache_get(f"portfolio_{code}")
    if cached: return jsonify(cached)

    raw = scraper.get_fund_portfolio(code)
    positions = [{"ticker": p.get("HISSESENEDIKODU", p.get("VARLIKADI","")),
                  "name": p.get("VARLIKADI",""), "weight": safe_float(p.get("PORTFOYDAKI_PAYI")),
                  "sector": p.get("SEKTOR",""), "type": p.get("VARLIKTUR","")}
                 for p in raw]
    positions.sort(key=lambda x: x["weight"] or 0, reverse=True)
    result = {"code":code,"positions":positions,"count":len(positions)}
    cache_set(f"portfolio_{code}", result)
    return jsonify(result)

@app.route("/api/reverse/<ticker>")
def reverse_lookup(ticker):
    ticker = ticker.upper()
    cached = cache_get("funds_all")
    if not cached:
        return jsonify({"error":"Önce /api/funds çağrılmalı"}), 503
    # Bu özellik için portföy verisi lazım, basit versiyon
    return jsonify({"ticker":ticker,"message":"Portföy verisi ayrı sorgulanmalı"})

def safe_float(val):
    if val is None: return None
    try:
        if isinstance(val, str): val = val.replace(",",".").strip()
        v = float(val)
        return None if (v != v) else round(v, 4)  # NaN kontrolü
    except: return None

def safe_int(val):
    if val is None: return None
    try: return int(str(val).replace(".","").replace(",","").strip().split(".")[0])
    except: return None

def map_category_from_type(fund_type, name=""):
    t = str(fund_type).upper()
    n = str(name).upper()
    if "HİSSE" in t or "HISSE" in t or "HİSSE" in n or "HISSE" in n: return "Hisse"
    if "KATILIM" in t or "KATILIM" in n: return "Katılım"
    if "ALTIN" in t or "ALTIN" in n: return "Altın"
    if "BORÇ" in t or "TAHVİL" in t or "BORÇ" in n: return "Borçlanma"
    if "PARA" in t or "PARA" in n: return "Para Piyasası"
    if "KARMA" in t or "DEĞİŞKEN" in t: return "Karma"
    return "Diğer"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"🚀 Fonlor API başlatılıyor — port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
