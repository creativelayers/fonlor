"""
Fonlor Backend API
TEFAS verilerini çekip frontend'e JSON olarak sunar.
Railway / Render / Heroku uyumlu — PORT env variable'dan okur.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import scraper
import time
import datetime
import os

app = Flask(__name__)

# Production'da Vercel URL'ini buraya yaz (deploy ettikten sonra güncelle)
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5050",
    "http://127.0.0.1:5500",
    "https://*.vercel.app",
    "*",  # geliştirme aşamasında açık, sonra kısıtla
]
CORS(app, origins="*")

# ─── In-memory cache ──────────────────────────────────────────────────────────
_cache = {}
CACHE_TTL = 300  # 5 dakika

def cache_get(key):
    if key in _cache:
        val, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return val
    return None

def cache_set(key, val):
    _cache[key] = (val, time.time())


# ─── Health check (Railway bunu kullanır) ────────────────────────────────────
@app.route("/")
def health():
    return jsonify({
        "status": "ok",
        "app": "Fonlor API",
        "version": "1.0.0",
        "endpoints": ["/api/funds", "/api/fund/<code>", "/api/fund/<code>/history"]
    })


# ─── Tüm fonlar ───────────────────────────────────────────────────────────────
@app.route("/api/funds")
def funds():
    cached = cache_get("funds_all")
    if cached:
        funds_data = cached
    else:
        raw = scraper.get_all_funds_with_returns()
        if not raw:
            return jsonify({"error": "TEFAS'tan veri çekilemedi"}), 503

        funds_data = []
        for f in raw:
            funds_data.append({
                "code":      f.get("FONKODU", ""),
                "name":      f.get("FONUNVAN", ""),
                "cat":       map_category(f.get("FONTUR", "")),
                "katilim":   "KATILIM" in f.get("FONUNVAN", "").upper(),
                "price":     safe_float(f.get("FIYAT")),
                "aum":       safe_float(f.get("PORTFOYBUYUKLUK")),
                "investors": safe_int(f.get("YATIRIMCISAYISI")),
                "r1m":       safe_float(f.get("GETIRI1AY")),
                "r3m":       safe_float(f.get("GETIRI3AY")),
                "r6m":       safe_float(f.get("GETIRI6AY")),
                "r1y":       safe_float(f.get("GETIRI1YIL")),
                "ytd":       safe_float(f.get("GETIRIYTD")),
                "risk":      safe_int(f.get("RISKDEGERI")),
            })

        cache_set("funds_all", funds_data)

    cat_filter = request.args.get("cat", "")
    q_filter   = request.args.get("q", "").lower()
    result = funds_data
    if cat_filter:
        result = [f for f in result if f["cat"] == cat_filter]
    if q_filter:
        result = [f for f in result if q_filter in f["code"].lower() or q_filter in f["name"].lower()]

    return jsonify({
        "count":      len(result),
        "updated_at": datetime.datetime.now().isoformat(),
        "funds":      result,
    })


# ─── Fon detayı ───────────────────────────────────────────────────────────────
@app.route("/api/fund/<code>")
def fund_detail(code):
    code = code.upper()
    cached = cache_get(f"fund_{code}")
    if cached:
        return jsonify(cached)

    detail = scraper.get_fund_detail(code)
    if not detail:
        return jsonify({"error": f"{code} bulunamadı"}), 404

    result = {
        "code":      code,
        "name":      detail.get("FONUNVAN", ""),
        "price":     safe_float(detail.get("FIYAT")),
        "aum":       safe_float(detail.get("PORTFOYBUYUKLUK")),
        "investors": safe_int(detail.get("YATIRIMCISAYISI")),
        "date":      detail.get("TARIH", ""),
        "cat":       map_category(detail.get("FONTUR", "")),
        "risk":      safe_int(detail.get("RISKDEGERI")),
    }
    cache_set(f"fund_{code}", result)
    return jsonify(result)


# ─── Fiyat geçmişi ────────────────────────────────────────────────────────────
@app.route("/api/fund/<code>/history")
def fund_history(code):
    code = code.upper()
    days = int(request.args.get("days", 365))
    cache_key = f"history_{code}_{days}"
    cached = cache_get(cache_key)
    if cached:
        return jsonify(cached)

    raw = scraper.get_fund_history(code, days)
    if not raw:
        return jsonify({"error": "Geçmiş veri bulunamadı"}), 404

    history = [
        {
            "date":      r.get("TARIH", "")[:10],
            "price":     safe_float(r.get("FIYAT")),
            "aum":       safe_float(r.get("PORTFOYBUYUKLUK")),
            "investors": safe_int(r.get("YATIRIMCISAYISI")),
        }
        for r in raw if r.get("FIYAT")
    ]
    returns = scraper.calculate_return(raw)
    result = {"code": code, "history": history, "returns": returns}
    cache_set(cache_key, result)
    return jsonify(result)


# ─── Portföy pozisyonları ─────────────────────────────────────────────────────
@app.route("/api/fund/<code>/portfolio")
def fund_portfolio(code):
    code = code.upper()
    cached = cache_get(f"portfolio_{code}")
    if cached:
        return jsonify(cached)

    raw = scraper.get_fund_portfolio(code)
    positions = [
        {
            "ticker": p.get("HISSESENEDIKODU", p.get("VARLIKADI", "")),
            "name":   p.get("VARLIKADI", ""),
            "weight": safe_float(p.get("PORTFOYDAKI_PAYI")),
            "sector": p.get("SEKTOR", ""),
            "type":   p.get("VARLIKTUR", ""),
        }
        for p in raw
    ]
    positions.sort(key=lambda x: x["weight"] or 0, reverse=True)
    result = {"code": code, "positions": positions, "count": len(positions)}
    cache_set(f"portfolio_{code}", result)
    return jsonify(result)


# ─── Yardımcılar ──────────────────────────────────────────────────────────────
def safe_float(val):
    if val is None: return None
    try:
        if isinstance(val, str):
            val = val.replace(",", ".").strip()
        return round(float(val), 4)
    except:
        return None

def safe_int(val):
    if val is None: return None
    try:
        return int(str(val).replace(".", "").replace(",", "").strip())
    except:
        return None

def map_category(t):
    t = (t or "").upper()
    if "HİSSE" in t or "HISSE" in t: return "Hisse"
    if "KATILIM" in t: return "Katılım"
    if "ALTIN" in t: return "Altın"
    if "BORÇLANMA" in t or "BORCLANMA" in t or "TAHVİL" in t: return "Borçlanma"
    if "PARA PİYASASI" in t or "PARA PIYASASI" in t: return "Para Piyasası"
    if "KARMA" in t or "DEĞİŞKEN" in t or "DEGISKEN" in t: return "Karma"
    return "Diğer"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    print(f"🚀 Fonlor API başlatılıyor — port {port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
