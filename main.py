import requests
import pandas as pd
import numpy as np
import json
import time
from datetime import datetime

BENCHMARK_SEARCH_TERMS = {
    "NIFTY 50": ["nifty 50 index", "direct", "growth"],
    "NIFTY NEXT 50": ["next 50 index", "direct", "growth"],
    "NIFTY 500": ["nifty 500 index", "direct", "growth"],
    "NIFTY MIDCAP 150": ["midcap 150 index", "direct", "growth"],
    "NIFTY SMALLCAP 250": ["smallcap 250 index", "direct", "growth"],
    "NIFTY LARGE MIDCAP 250": ["large midcap 250 index", "direct", "growth"],
    "NASDAQ 100": ["nasdaq", "direct", "growth"],
    "NIFTY LIQUID INDEX": ["liquid", "direct", "growth"]
}

CATEGORY_TO_BENCHMARK = {
    "Large Cap": "NIFTY 50", "Large & Mid Cap": "NIFTY LARGE MIDCAP 250",
    "Mid Cap": "NIFTY MIDCAP 150", "Small Cap": "NIFTY SMALLCAP 250",
    "Flexi Cap": "NIFTY 500", "Multi Cap": "NIFTY 500", "ELSS": "NIFTY 500",
    "Value/Contra": "NIFTY 500", "Focused": "NIFTY 500",
    "Liquid": "NIFTY LIQUID INDEX", "Overnight": "NIFTY LIQUID INDEX",
    "Money Market": "NIFTY LIQUID INDEX", "Ultra Short Duration": "NIFTY LIQUID INDEX",
    "Low Duration": "NIFTY LIQUID INDEX", "Short Duration": "NIFTY LIQUID INDEX",
    "Medium Duration": "NIFTY LIQUID INDEX", "Long Duration": "NIFTY LIQUID INDEX",
    "Corporate Bond": "NIFTY LIQUID INDEX", "Banking & PSU": "NIFTY LIQUID INDEX",
    "Credit Risk": "NIFTY LIQUID INDEX", "Dynamic Bond": "NIFTY LIQUID INDEX",
    "Gilt": "NIFTY LIQUID INDEX", "Floater": "NIFTY LIQUID INDEX",
    "Arbitrage": "NIFTY LIQUID INDEX", "Balanced Advantage": "NIFTY 500",
    "Multi Asset": "NIFTY 500", "Equity Savings": "NIFTY 500",
    "Aggressive Hybrid": "NIFTY 500", "Conservative Hybrid": "NIFTY 50"
}

def get_secure_session():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    return session

def categorize_fund(name):
    n = " ".join(name.lower().split())
    if not (("direct" in n or "dir" in n) and ("growth" in n or "gr" in n)): return None
    if any(x in n for x in ["regular", "reg", "idcw", "dividend", "div", "income distribution", "withdrawal"]): return None
    if any(x in n for x in ["index", "idx", "etf", "exchange traded", "fof", "fund of fund", "child", "retirement", "series", "offshore", "global", "international"]): return None
    
    if "arbitrage" in n: return "Arbitrage"
    if any(x in n for x in ["balanced advantage", "baf", "dynamic asset"]): return "Balanced Advantage"
    if "multi asset" in n: return "Multi Asset"
    if "equity savings" in n: return "Equity Savings"
    if any(x in n for x in ["aggressive hybrid", "balanced hybrid", "equity hybrid"]): return "Aggressive Hybrid"
    if any(x in n for x in ["conservative hybrid", "debt hybrid"]): return "Conservative Hybrid"

    if any(x in n for x in ["elss", "tax saver", "tax saving", "tax fund"]): return "ELSS"
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
    if any(x in n for x in ["long duration", "medium to long"]) or ("long term" in n and "advantage" not in n and "equity" not in n): return "Long Duration"
    if "corporate bond" in n: return "Corporate Bond"
    if "banking & psu" in n or "banking and psu" in n: return "Banking & PSU"
    if "credit risk" in n: return "Credit Risk"
    if "dynamic bond" in n: return "Dynamic Bond"
    if "gilt" in n or "constant maturity" in n: return "Gilt"
    if "floater" in n or "floating rate" in n: return "Floater"
    
    return "Sectoral/Thematic"

def fetch_nav_history(scheme_code, session, truncate_2020=False):
    url = f"https://api.mfapi.in/mf/{scheme_code}"
    for attempt in range(1, 4):
        try:
            response = session.get(url, timeout=10)
            if response.status_code == 429:
                print("[HTTP 429 Triggered! Sleeping 3s...]", end=" ", flush=True)
                time.sleep(3)
                continue
            if response.status_code != 200: return None
            data = response.json().get("data", [])
            if not data: return None
                
            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y')
            df['nav'] = pd.to_numeric(df['nav'], errors='coerce')
            df = df.sort_values('date').reset_index(drop=True)
            
            if truncate_2020:
                df = df[df['date'] >= '2020-01-01'].reset_index(drop=True)
            return df
        except Exception:
            time.sleep(1)
    return None

def calc_3y_median(df):
    if df is None or len(df) < 500: return None
    
    max_date = df['date'].max()
    eval_start_date = max_date - pd.DateOffset(years=3)
    eval_df = df[df['date'] >= eval_start_date].copy()
    if eval_df.empty: return None
        
    eval_df['target_date'] = eval_df['date'] - pd.DateOffset(years=3)
    lookup_df = df[['date', 'nav']].rename(columns={'date': 'lookup_date', 'nav': 'past_nav'})
    
    merged = pd.merge_asof(
        eval_df.sort_values('target_date'), 
        lookup_df.sort_values('lookup_date'), 
        left_on='target_date', 
        right_on='lookup_date', 
        direction='backward'
    )
    
    merged = merged.dropna(subset=['past_nav'])
    merged['gap_to_target'] = (merged['target_date'] - merged['lookup_date']).dt.days
    valid_rolls = merged[merged['gap_to_target'] <= 15].copy() 
    
    if len(valid_rolls) < 50: return None 
    
    valid_rolls['exact_days'] = (valid_rolls['date'] - valid_rolls['lookup_date']).dt.days
    valid_rolls = valid_rolls[valid_rolls['exact_days'] > 0]
    valid_rolls['cagr'] = ((valid_rolls['nav'] / valid_rolls['past_nav']) ** (365.25 / valid_rolls['exact_days'])) - 1
    
    return round(valid_rolls['cagr'].median() * 100, 2)

def main():
    session = get_secure_session()
    print("1. Downloading AMFI Master List & Discovering Benchmarks...")
    amfi_res = session.get("https://www.amfiindia.com/spages/NAVAll.txt", timeout=15)
    
    nav_dict = {}
    categorized_funds = {}
    all_raw_funds = []
    discovered_benchmarks = {}

    if amfi_res.status_code == 200:
        lines = amfi_res.text.split('\n')
        for line in lines:
            cols = line.split(';')
            if len(cols) >= 6:
                nav_str, date_str, scheme_code = cols[-2].strip(), cols[-1].strip(), cols[0].strip()
                if nav_str and nav_str != 'N.A.':
                    try:
                        nav_val = float(nav_str)
                        fund_name_parts = [c.strip() for c in cols[3:-2] if c.strip()]
                        full_fund_name = " ".join(" - ".join(fund_name_parts).split())
                        all_raw_funds.append({"code": scheme_code, "name": full_fund_name})
                        
                        nav_obj = {"nav": nav_val, "date": date_str, "schemeCode": scheme_code}
                        isin1, isin2 = cols[1].strip().upper(), cols[2].strip().upper()
                        if isin1 and isin1 != '-': nav_dict[isin1] = nav_obj
                        if isin2 and isin2 != '-': nav_dict[isin2] = nav_obj
                        
                        category = categorize_fund(full_fund_name)
                        if category:
                            if category not in categorized_funds: categorized_funds[category] = []
                            clean_name = " ".join(full_fund_name.replace('- Direct Plan', '').replace('- Direct', '').replace('- Growth Option', '').replace('- Growth', '').replace('Growth', '').replace('-  ', '').strip().split())
                            if not any(f['code'] == scheme_code for f in categorized_funds[category]):
                                categorized_funds[category].append({"code": scheme_code, "name": clean_name})
                    except ValueError: pass

    # Dynamic Benchmark Discovery
    for b_key, terms in BENCHMARK_SEARCH_TERMS.items():
        for fund in all_raw_funds:
            n_lower = fund["name"].lower()
            if all(term in n_lower for term in terms):
                discovered_benchmarks[b_key] = fund
                break

    with open('latest_navs.json', 'w') as f:
        json.dump(nav_dict, f)

    final_output = {
        "last_updated": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
        "indices": {},
        "peer_groups": {},
        "fund_medians": {},
        "index_history": {}
    }

    print("\n2. Fetching Discovered Benchmark Histories (Post-2020)...")
    for b_key, fund in discovered_benchmarks.items():
        df = fetch_nav_history(fund["code"], session, truncate_2020=True)
        if df is not None:
            final_output["indices"][b_key] = {"rolling_3Y": calc_3y_median(df) or "-"}
            history_array = [{"time": int(r['date'].timestamp() * 1000), "nav": float(r['nav'])} for _, r in df.iterrows()]
            final_output["index_history"][b_key] = history_array
            print(f" -> Success: {b_key} [{fund['name']}]")
        else:
            print(f" -> Failed: {b_key}")
        time.sleep(1)

    print("\n3. STARTING FULL MARKET PEER GROUP ANALYSIS (1s Delay)")
    for category, funds_to_process in sorted(categorized_funds.items()):
        if category == "Sectoral/Thematic" or len(funds_to_process) < 3:
            continue
            
        proxy_key = CATEGORY_TO_BENCHMARK.get(category, "NIFTY 500")
        proxy_name = discovered_benchmarks.get(proxy_key, {}).get("name", "Unknown Proxy")
        
        print(f"\n--- PROCESSING CATEGORY: {category} ({len(funds_to_process)} Funds) [Proxy: {proxy_name}] ---")
        
        successful_returns = []
        for idx, f in enumerate(funds_to_process, 1):
            print(f"[{idx}/{len(funds_to_process)}] {f['name']}...", end=" ", flush=True)
            df = fetch_nav_history(f["code"], session)
            
            if df is not None:
                med_3y = calc_3y_median(df)
                if med_3y is not None:
                    successful_returns.append({"name": f["name"], "return_3y": med_3y})
                    final_output["fund_medians"][f["code"]] = med_3y
                    print(f"Data OK ({med_3y}%)")
                else:
                    print(f"Skipped (Insufficient History)")
            else:
                print(f"Failed Fetch")
            
            time.sleep(1)

        if successful_returns:
            successful_returns.sort(key=lambda x: x["return_3y"], reverse=True)
            just_returns = [x["return_3y"] for x in successful_returns]
            final_output["peer_groups"][category] = {
                "q1": round(float(np.percentile(just_returns, 75)), 2),
                "q2": round(float(np.percentile(just_returns, 50)), 2),
                "q3": round(float(np.percentile(just_returns, 25)), 2),
                "top_3": [f"{f['name']} ({f['return_3y']}%)" for f in successful_returns[:3]]
            }

    with open('ranks.json', 'w') as f:
        json.dump(final_output, f)
    print("\n==================================================")
    print("Done! Institutional ranks.json generated successfully.")

if __name__ == "__main__":
    main()
