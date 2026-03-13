"""
Fonlor TEFAS Scraper - tefas-crawler kullanır
"""
import datetime
from tefas import Crawler

_crawler = Crawler()

def get_all_funds_with_returns():
    today = datetime.date.today().strftime("%Y-%m-%d")
    try:
        print(f"TEFAS connecting via tefas-crawler... {today}")
        data = _crawler.fetch(start=today, columns=[
            "code","title","date","price","daily_return",
            "monthly_return","quarterly_return","semiannual_return",
            "annual_return","ytd_return","market_cap",
            "number_of_investors","risk_value","fund_type",
        ])
        records = data.to_dict(orient="records")
        print(f"OK: {len(records)} funds")
        return records
    except Exception as e:
        print(f"FAILED: {e}")
        return []

def get_fund_detail(fund_code):
    today = datetime.date.today().strftime("%Y-%m-%d")
    try:
        data = _crawler.fetch(start=today, name=fund_code)
        if data.empty: return None
        return data.iloc[0].to_dict()
    except Exception as e:
        print(f"Fund detail error ({fund_code}): {e}")
        return None

def get_fund_history(fund_code, days=365):
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days)
    try:
        data = _crawler.fetch(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            name=fund_code,
            columns=["code","date","price","market_cap","number_of_investors"]
        )
        records = data.to_dict(orient="records")
        records.sort(key=lambda x: str(x.get("date","")))
        return records
    except Exception as e:
        print(f"History error ({fund_code}): {e}")
        return []

def get_fund_portfolio(fund_code):
    import requests
    try:
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.tefas.gov.tr/FonAnaliz.aspx",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        })
        r = s.post("https://www.tefas.gov.tr/api/DB/BindFundPortfolio",
                   data={"fonkod": fund_code}, timeout=20)
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        print(f"Portfolio error ({fund_code}): {e}")
        return []

def calculate_return(history):
    if len(history) < 2: return {}
    def pct(old,new):
        if not old or old==0: return None
        return round((new-old)/old*100,2)
    prices = []
    for r in history:
        try:
            p=r.get("price"); d=r.get("date")
            if p and d: prices.append((str(d)[:10],float(p)))
        except: pass
    if not prices: return {}
    _,lp = prices[-1]
    now = datetime.date.today()
    def p(n):
        t=now-datetime.timedelta(days=n)
        for ds,pr in reversed(prices[:-1]):
            try:
                if datetime.datetime.strptime(ds[:10],"%Y-%m-%d").date()<=t: return pr
            except: pass
        return prices[0][1]
    return {"r1m":pct(p(30),lp),"r3m":pct(p(90),lp),"r6m":pct(p(180),lp),"r1y":pct(p(365),lp)}
