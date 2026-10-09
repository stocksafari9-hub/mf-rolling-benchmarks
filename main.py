import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import numpy as np
import json
import time
from datetime import datetime

# Exact AMFI Scheme Codes for the Official Passive Index Proxies
INDEX_PROXIES = {
    "NIFTY 50": "147794",              
    "NIFTY NEXT 50": "147796",         
    "NIFTY 500": "147625",             
    "NIFTY MIDCAP 150": "147622",      
    "NIFTY SMALLCAP 250": "147623",    
    "NIFTY LARGE MIDCAP 250": "149343", 
    "NASDAQ 100": "145552",
    "NIFTY LIQUID INDEX": "119800"      
}

# --- ROBUST NETWORK ENGINE ---
def get_secure_session():
    session = requests.Session()
    # If the server throws a 429 (Too Many Requests) or 503 (Server Busy), it will auto-retry up to 10 times, pausing exponentially.
    retry = Retry(
        total=10,
        read=10,
        connect=10,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        respect_retry_after_header=True
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    return session

def categorize_fund(name):
    n = name.lower()
    if not (("direct" in n or "dir" in n) and ("growth" in n or "gr" in n)): return None
    if any(x in n for x in ["regular", "reg", "idcw", "dividend", "div"]): return None
    if any(x in n for x in ["index", "idx", "etf", "exchange traded", "fof", "fund of fund", "child", "retirement"]): return None
    
    if "arbitrage" in n: return "Arbitrage"
    if any(x in n for x in ["balanced advantage", "baf", "dynamic asset"]): return "Balanced Advantage"
    if "multi asset" in n: return "Multi Asset"
    if "equity savings" in n: return "Equity Savings"
    if any(x in n for x in ["aggressive hybrid", "balanced hybrid", "equity hybrid"]): return "Aggressive Hybrid"
    if any(x in n for x in ["conservative hybrid", "debt hybrid"]): return "Conservative Hybrid"

    if any(x in n for x in ["elss", "tax saver", "tax saving"]): return "ELSS"
    if any(x in n for x in ["large & mid", "large and mid", "large & midcap", "large and midcap", "largemidcap"]): return "Large & Mid Cap"
    if "small cap" in n or "smallcap" in n: return "Small Cap"
    if "mid cap" in n or "midcap" in n: return "Mid Cap"
    if any(x in n for x in ["large cap", "largecap", "bluechip", "blue chip"]): return "Large Cap"
    if "flexi cap" in n or "flexicap" in n: return "Flexi Cap"
    if "multi cap" in n or "multicap" in n: return "Multi Cap"
    if "value" in n or "contra" in n: return "Value/Contra"
    if "focused" in n or "focus" in n: return "Focused"

    if "liquid" in n: return "Liquid"
    if "overnight" in n: return "Overnight"
    if "money market" in n: return "Money Market"
    if "ultra short" in n: return "Ultra Short Duration"
    if "low duration" in n: return "Low Duration"
    if "short duration" in n or "short term" in n: return "Short Duration"
    if "medium duration" in n: return "Medium Duration"
    if any(x in n for x in ["long duration", "long term", "medium to long"]): return "Long Duration"
    if "corporate bond" in n: return "Corporate Bond"
    if "banking & psu" in n or "banking and psu" in n: return "Banking & PSU"
    if "credit risk" in n: return "Credit Risk"
    if "dynamic bond" in n: return "Dynamic Bond"
    if "gilt" in n or "constant maturity" in n: return "Gilt"
    if "floater" in n or "floating rate" in n: return "Floater"
    return "Sectoral/Thematic"

def fetch_nav_history(scheme_code, session):
    try:
        url = f"https://api.mfapi.in/mf/{scheme_code}"
        response = session.get(url, timeout=15)
        if response.status_code != 200: return None
        data = response.json().get("data", [])
        if not data: return None
            
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y')
        df['nav'] = pd.to_numeric(df['nav'], errors='coerce')
        df = df.sort_values('date').reset_index(drop=True)
        return df
    except Exception as e:
        print(f"Error fetching {scheme_code}: {e}")
        return None

def calc_3y_median(df):
    if df is None or len(df) <= 252 * 3: return None
    df['nav_ago_3Y'] = df['nav'].shift(252 * 3)
    rolling_cagr = ((df['nav'] / df['nav_ago_3Y']) ** (1 / 3)) - 1
    return round(rolling_cagr.median() * 100, 2)

def main():
    session = get_secure_session()
    
    print("Downloading AMFI List for classification...")
    amfi_res = session.get("https://www.amfiindia.com/spages/NAVAll.txt", timeout=15)
    nav_dict = {}
    categorized_funds = {}

    if amfi_res.status_code == 200:
        lines = amfi_res.text.split('\n')
        for line in lines:
            cols = line.split(';')
            if len(cols) >= 6:
                nav_str = cols[-2].strip()
                date_str = cols[-1].strip()
                if nav_str and nav_str != 'N.A.':
                    try:
                        nav_val = float(nav_str)
                        scheme_code = cols[0].strip()
                        fund_name = cols[3].strip()
                        
                        nav_obj = {"nav": nav_val, "date": date_str, "schemeCode": scheme_code}
                        isin1, isin2 = cols[1].strip().upper(), cols[2].strip().upper()
                        if isin1 and isin1 != '-': nav_dict[isin1] = nav_obj
                        if isin2 and isin2 != '-': nav_dict[isin2] = nav_obj
                        
                        category = categorize_fund(fund_name)
                        if category:
                            if category not in categorized_funds: categorized_funds[category] = []
                            clean_name = fund_name.replace('- Direct Plan', '').replace('- Direct', '').replace('Growth', '').replace('-  ', '').strip()
                            categorized_funds[category].append({"code": scheme_code, "name": clean_name})
                    except ValueError: pass

    with open('latest_navs.json', 'w') as f:
        json.dump(nav_dict, f)
    print(f"Saved latest_navs.json with {len(nav_dict)} ISINs")

    final_output = {
        "last_updated": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
        "indices": {},
        "peer_groups": {}
    }

    print("Fetching Global Indices...")
    for index_name, code in INDEX_PROXIES.items():
        df = fetch_nav_history(code, session)
        if df is not None:
            final_output["indices"][index_name] = {
                "rolling_3Y": calc_3y_median(df) or "-"
            }
        time.sleep(1) # Polite throttle

    print("Calculating True Peer Group Percentiles...")
    for category, funds in categorized_funds.items():
        print(f"Processing Category: {category} ({len(funds)} funds)")
        returns_list = []
        for f in funds:
            df = fetch_nav_history(f["code"], session)
            med_3y = calc_3y_median(df)
            if med_3y is not None:
                returns_list.append({"name": f["name"], "return_3y": med_3y})
            time.sleep(1) # Core Throttle - prevents IP ban
            
        if not returns_list: continue

        returns_list.sort(key=lambda x: x["return_3y"], reverse=True)
        
        just_returns = [x["return_3y"] for x in returns_list]
        q1_bound = round(np.percentile(just_returns, 75), 2)
        q2_bound = round(np.percentile(just_returns, 50), 2)
        q3_bound = round(np.percentile(just_returns, 25), 2)

        top_3 = []
        for top_f in returns_list[:3]:
            top_3.append(f"{top_f['name']} ({top_f['return_3y']}%)")

        final_output["peer_groups"][category] = {
            "q1": q1_bound,
            "q2": q2_bound,
            "q3": q3_bound,
            "top_3": top_3
        }

    with open('ranks.json', 'w') as f:
        json.dump(final_output, f, indent=4)
    print("Successfully generated ranks.json with Institutional Peer Groups!")

if __name__ == "__main__":
    main()
