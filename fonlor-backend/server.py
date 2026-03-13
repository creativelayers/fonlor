"""
Fonlor Backend API - cPanel Passenger/WSGI uyumlu
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
import scraper
import time, datetime, os

app = Flask(__name__)
CORS(app, origins="*")

_cache = {}
CACHE_TTL = 300

def cache_get(key):
    if key in _cache:
        val, ts = _cache[key]
        if time.time() - ts < CACHE_TTL: return val
    return None

def cache_set(key, val):
    _cache[key] = (val, time.time())

@app.route("/")
@app.route("/fonlor-api")
@app.route("/fonlor-api/")
def health():
    return jsonify({"status": "ok", "app": "Fonlor API", "version": "2.4.0"})

@app.route("/api/funds")
@app.route("/fonlor-api/api/funds")
def funds():
    cached = cache_get("funds_all")
    if cached:
        funds_data = cached
    else:
        raw = scraper.get_all_funds_with_returns()
        if not raw:
            return jsonify({"error": "TEFAS'tan veri cekilemedi"}), 503
        cache_set("funds_raw", raw)
        funds_data = []
        for f in raw:
            funds_data.append(fund_row(f))
        cache_set("funds_all", funds_data)

    limit = int(request.args.get("limit", 0))
    q_filter = request.args.get("q", "").lower()
    result = funds_data
    if q_filter:
        result = [f for f in result if q_filter in f["FONKODU"].lower() or q_filter in f.get("FONUNVAN","").lower()]
    if limit:
        result = result[:limit]
    return jsonify({"count": len(result), "updated_at": datetime.datetime.now().isoformat(), "funds": result})

@app.route("/api/debug/fields")
@app.route("/fonlor-api/api/debug/fields")
def debug_fields():
    raw = scraper.get_all_funds_with_returns()
    if not raw:
        return jsonify({"error": "veri yok"}), 503
    return jsonify({"fields": list(raw[0].keys()), "sample": raw[0]})

@app.route("/api/fund/<code>")
@app.route("/fonlor-api/api/fund/<code>")
def fund_detail(code):
    code = code.upper()
    cached = cache_get(f"fund_{code}")
    if cached: return jsonify(cached)

    # 1) Tum fonlar cache'inde ara (getiri dahil)
    all_funds_raw = cache_get("funds_raw")
    raw_f = None
    if all_funds_raw:
        for f in all_funds_raw:
            if str(f.get("FONKODU", "")).upper() == code:
                raw_f = f
                break

    # 2) Tum listeyi cek ve cache'le
    if not raw_f:
        all_raw = scraper.get_all_funds_with_returns()
        if all_raw:
            cache_set("funds_raw", all_raw)
            for f in all_raw:
                if str(f.get("FONKODU", "")).upper() == code:
                    raw_f = f
                    break

    # 3) HTML scrape fallback (getiri icin en iyi kaynak)
    html_detail = scraper.get_fund_detail(code)

    if not raw_f and not html_detail:
        return jsonify({"error": f"{code} bulunamadi"}), 404

    # raw_f'dan temel bilgiler, html_detail'dan getiri
    base = raw_f or {}
    html = html_detail or {}

    result = {
        "fund": {
            "FONKODU":         code,
            "FONUNVAN":        html.get("FONUNVAN") or base.get("FONUNVAN", ""),
            "FIYAT":           safe_float(html.get("FIYAT") or base.get("FIYAT") or base.get("SONFIYAT")),
            "PORTFOYBUYUKLUK": safe_float(html.get("PORTFOYBUYUKLUK") or base.get("PORTFOYBUYUKLUK")),
            "KISISAYISI":      safe_int(html.get("KISISAYISI") or base.get("YATIRIMCISAYISI") or base.get("KISISAYISI")),
            "TEDPAYSAYISI":    safe_int(base.get("TEDPAYSAYISI")),
            "BORSABULTENFIYAT":base.get("BORSABULTENFIYAT"),
            "TARIH":           base.get("TARIH", ""),
            "RISKDEGERI":      html.get("RISKDEGERI"),
            # Getiriler - once html'den, yoksa liste verisinden
            "GETIRI1AY":  safe_float(html.get("GETIRI1AY") or base.get("GETIRI1AY") or base.get("GETIRIAYLIK")),
            "GETIRI3AY":  safe_float(html.get("GETIRI3AY") or base.get("GETIRI3AY") or base.get("GETIRI3AYLIK")),
            "GETIRI6AY":  safe_float(html.get("GETIRI6AY") or base.get("GETIRI6AY") or base.get("GETIRI6AYLIK")),
            "GETIRI1YIL": safe_float(html.get("GETIRI1YIL") or base.get("GETIRI1YIL") or base.get("GETIRIYILLIK")),
            "GETIRIYTD":  safe_float(html.get("GETIRIYTD") or base.get("GETIRIYTD") or base.get("YILBASI")),
        }
    }
    cache_set(f"fund_{code}", result)
    return jsonify(result)

@app.route("/api/fund/<code>/history")
@app.route("/fonlor-api/api/fund/<code>/history")
def fund_history(code):
    code = code.upper()
    days = int(request.args.get("days", 1825))
    cache_key = f"history_{code}_{days}"
    cached = cache_get(cache_key)
    if cached: return jsonify(cached)
    raw = scraper.get_fund_history(code, days)
    if not raw:
        return jsonify({"code": code, "history": []}), 200
    history = [{"TARIH": r.get("TARIH"), "FIYAT": safe_float(r.get("FIYAT")),
                "PORTFOYBUYUKLUK": safe_float(r.get("PORTFOYBUYUKLUK")),
                "KISISAYISI": safe_int(r.get("YATIRIMCISAYISI") or r.get("KISISAYISI"))}
               for r in raw if r.get("FIYAT")]
    result = {"code": code, "history": history}
    cache_set(cache_key, result)
    return jsonify(result)

@app.route("/api/fund/<code>/portfolio")
@app.route("/fonlor-api/api/fund/<code>/portfolio")
def fund_portfolio(code):
    code = code.upper()
    cached = cache_get(f"portfolio_{code}")
    if cached: return jsonify(cached)
    raw = scraper.get_fund_portfolio(code)
    result = {"code": code, "portfolio": raw, "count": len(raw)}
    cache_set(f"portfolio_{code}", result)
    return jsonify(result)

def fund_row(f):
    """Ham TEFAS verisini API satırına donustur."""
    return {
        "FONKODU":          str(f.get("FONKODU", "")),
        "FONUNVAN":         f.get("FONUNVAN", ""),
        "FIYAT":            safe_float(f.get("FIYAT") or f.get("SONFIYAT")),
        "PORTFOYBUYUKLUK":  safe_float(f.get("PORTFOYBUYUKLUK") or f.get("BUYUKLUK")),
        "KISISAYISI":       safe_int(f.get("YATIRIMCISAYISI") or f.get("KISISAYISI")),
        "TEDPAYSAYISI":     safe_int(f.get("TEDPAYSAYISI")),
        "BORSABULTENFIYAT": f.get("BORSABULTENFIYAT"),
        "TARIH":            f.get("TARIH", ""),
        "r1m":  safe_pct(f.get("GETIRI1AY") or f.get("GETIRIAYLIK")),
        "r3m":  safe_pct(f.get("GETIRI3AY") or f.get("GETIRI3AYLIK")),
        "r6m":  safe_pct(f.get("GETIRI6AY") or f.get("GETIRI6AYLIK")),
        "r1y":  safe_pct(f.get("GETIRI1YIL") or f.get("GETIRIYILLIK")),
        "ytd":  safe_pct(f.get("GETIRIYTD") or f.get("YILBASI")),
    }

def safe_float(val):
    if val is None: return None
    try:
        if isinstance(val, str): val = val.replace(",", ".").strip()
        v = float(val)
        return None if v != v else round(v, 4)
    except: return None

def safe_pct(val):
    v = safe_float(val)
    if v is None: return None
    if -1 < v < 1 and v != 0:
        return round(v * 100, 2)
    return v

def safe_int(val):
    if val is None: return None
    try: return int(str(val).split(".")[0].replace(",", ""))
    except: return None

application = app  # cPanel Passenger icin sart!

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False)
