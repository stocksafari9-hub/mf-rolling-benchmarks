import requests
import pandas as pd
import numpy as np
import json
import time
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

BENCHMARK_SEARCH_TERMS = {
    "NIFTY 50": ["nifty 50", "index", "direct", "growth"],
    "NIFTY 500": ["nifty 500", "index", "direct", "growth"],
    "NIFTY MIDCAP 150": ["midcap 150", "index", "direct", "growth"],
    "NIFTY SMALLCAP 250": ["smallcap 250", "index", "direct", "growth"],
    "NIFTY LARGE MIDCAP 250": ["large midcap 250", "index", "direct", "growth"],
    "NASDAQ 100": ["nasdaq", "direct", "growth"],
    "NIFTY LIQUID INDEX": ["liquid", "direct", "growth"],
    "NIFTY GILT 10Y": ["constant maturity", "direct", "growth"]
}

SYNTHETIC_BLENDS = {
    "SYNTHETIC_AGGRESSIVE": 0.65,
    "SYNTHETIC_BAF": 0.50,
    "SYNTHETIC_MULTI_ASSET": 0.50,
    "SYNTHETIC_EQ_SAVINGS": 0.35,
    "SYNTHETIC_CONSERVATIVE": 0.15
}

CATEGORY_TO_BENCHMARK = {
    "Large Cap": "NIFTY 50", "Large & Mid Cap": "NIFTY LARGE MIDCAP 250",
    "Mid Cap": "NIFTY MIDCAP 150", "Small Cap": "NIFTY SMALLCAP 250",
    "Flexi Cap": "NIFTY 500", "Multi Cap": "NIFTY 500", "ELSS": "NIFTY 500",
    "Value/Contra": "NIFTY 500", "Focused": "NIFTY 500", "Gilt": "NIFTY GILT 10Y",
    "Liquid": "NIFTY LIQUID INDEX", "Overnight": "NIFTY LIQUID INDEX",
    "Money Market": "NIFTY LIQUID INDEX", "Ultra Short Duration": "NIFTY LIQUID INDEX",
    "Low Duration": "NIFTY LIQUID INDEX", "Short Duration": "NIFTY LIQUID INDEX",
    "Medium Duration": "NIFTY LIQUID INDEX", "Long Duration": "NIFTY LIQUID INDEX",
    "Corporate Bond": "NIFTY LIQUID INDEX", "Banking & PSU": "NIFTY LIQUID INDEX",
    "Credit Risk": "NIFTY LIQUID INDEX", "Dynamic Bond": "NIFTY LIQUID INDEX",
    "Floater": "NIFTY LIQUID INDEX", "Arbitrage": "NIFTY LIQUID INDEX",
    "Aggressive Hybrid": "SYNTHETIC_AGGRESSIVE", "Balanced Advantage": "SYNTHETIC_BAF",
    "Multi Asset": "SYNTHETIC_MULTI_ASSET", "Equity Savings": "SYNTHETIC_EQ_SAVINGS",
    "Conservative Hybrid": "SYNTHETIC_CONSERVATIVE"
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

def fetch_nav_robust(scheme_code, session):
    url = f"https://api.mfapi.in/mf/{scheme_code}"
    for attempt in range(1, 5):
        try:
            response = session.get(url, timeout=10)
            if response.status_code == 429:
                print("[HTTP 429! Sleeping 5s...]", end=" ", flush=True)
                time.sleep(5)
                continue
            if response.status_code != 200: return None
            data = response.json().get("data", [])
            if not data: return None
            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y')
            df['nav'] = pd.to_numeric(df['nav'], errors='coerce')
            return df.sort_values('date').reset_index(drop=True)
        except Exception:
            time.sleep(2)
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

def build_synthetic_index(eq_df, debt_df, eq_weight):
    eq_df = eq_df[eq_df['date'] >= '2019-12-01'].copy()
    debt_df = debt_df[debt_df['date'] >= '2019-12-01'].copy()
    
    merged = pd.merge(eq_df[['date', 'nav']], debt_df[['date', 'nav']], on='date', how='outer', suffixes=('_eq', '_debt')).sort_values('date')
    merged = merged.ffill().dropna()
    
    merged['eq_ret'] = merged['nav_eq'].pct_change().fillna(0)
    merged['debt_ret'] = merged['nav_debt'].pct_change().fillna(0)
    merged['blend_ret'] = (merged['eq_ret'] * eq_weight) + (merged['debt_ret'] * (1 - eq_weight))
    
    synthetic_navs = [100.0]
    for ret in merged['blend_ret'].iloc[1:]:
        synthetic_navs.append(synthetic_navs[-1] * (1 + ret))
        
    merged['nav'] = synthetic_navs
    final_df = merged[['date', 'nav']].copy()
    return final_df[final_df['date'] >= '2020-01-01'].reset_index(drop=True)

def main():
    session = get_secure_session()
    print("1. Downloading AMFI Master List & Hunting for Established Proxies...")
    amfi_res = session.get("https://www.amfiindia.com/spages/NAVAll.txt", timeout=15)
    
    nav_dict = {}
    categorized_funds = {}
    all_raw_funds = []
    
    if amfi_res.status_code == 200:
        for line in amfi_res.text.split('\n'):
            cols = line.split(';')
            if len(cols) >= 6:
                nav_str, date_str, scheme_code = cols[-2].strip(), cols[-1].strip(), cols[0].strip()
                if nav_str and nav_str != 'N.A.':
                    try:
                        nav_val = float(nav_str)
                        full_name = " ".join(" - ".join([c.strip() for c in cols[3:-2] if c.strip()]).split())
                        all_raw_funds.append({"code": scheme_code, "name": full_name})
                        
                        isin1, isin2 = cols[1].strip().upper(), cols[2].strip().upper()
                        if isin1 and isin1 != '-': nav_dict[isin1] = {"nav": nav_val, "date": date_str, "schemeCode": scheme_code}
                        if isin2 and isin2 != '-': nav_dict[isin2] = {"nav": nav_val, "date": date_str, "schemeCode": scheme_code}
                        
                        cat = categorize_fund(full_name)
                        if cat:
                            clean_name = " ".join(full_name.replace('- Direct Plan', '').replace('- Direct', '').replace('- Growth Option', '').replace('- Growth', '').replace('Growth', '').strip().split())
                            if cat not in categorized_funds: categorized_funds[cat] = []
                            if not any(f['code'] == scheme_code for f in categorized_funds[cat]):
                                categorized_funds[cat].append({"code": scheme_code, "name": clean_name})
                    except ValueError: pass

    with open('latest_navs.json', 'w') as f:
        json.dump(nav_dict, f)

    final_output = {
        "last_updated": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
        "indices": {},
        "peer_groups": {},
        "fund_medians": {},
        "index_history": {}
    }
    
    index_dataframes = {}

    print("\n2. Discovering Age-Aware Benchmarks (Must predate 2020-01-15)...")
    for b_key, terms in BENCHMARK_SEARCH_TERMS.items():
        found = False
        for fund in all_raw_funds:
            if all(term in fund["name"].lower() for term in terms):
                print(f" -> Testing {fund['name']}...", end=" ", flush=True)
                df = fetch_nav_robust(fund["code"], session)
                if df is not None and df['date'].min() <= pd.to_datetime('2020-01-15'):
                    print("PASS (Vintage Verified)")
                    df_2020 = df[df['date'] >= '2020-01-01'].reset_index(drop=True)
                    index_dataframes[b_key] = df
                    final_output["indices"][b_key] = {"rolling_3Y": calc_3y_median(df) or "-"}
                    final_output["index_history"][b_key] = [{"time": int(r['date'].timestamp() * 1000), "nav": float(r['nav'])} for _, r in df_2020.iterrows()]
                    found = True
                    break
                else:
                    print("REJECTED (Too young or API failed)")
                time.sleep(1)
        if not found: print(f" -> FATAL: Could not find established proxy for {b_key}")

    print("\n3. Synthesizing Tier-3 Blends for Hybrids...")
    for s_key, eq_weight in SYNTHETIC_BLENDS.items():
        if "NIFTY 50" in index_dataframes and "NIFTY LIQUID INDEX" in index_dataframes:
            syn_df = build_synthetic_index(index_dataframes["NIFTY 50"], index_dataframes["NIFTY LIQUID INDEX"], eq_weight)
            final_output["indices"][s_key] = {"rolling_3Y": calc_3y_median(syn_df) or "-"}
            final_output["index_history"][s_key] = [{"time": int(r['date'].timestamp() * 1000), "nav": round(float(r['nav']), 4)} for _, r in syn_df.iterrows()]
            print(f" -> Created {s_key} ({eq_weight*100}% Equity / {(1-eq_weight)*100}% Debt)")

    print("\n4. STARTING MARKET PEER GROUP ANALYSIS (1s Delay + Dead Letter Queue)")
    dead_letter_queue = []
    
    for category, funds_to_process in sorted(categorized_funds.items()):
        if category == "Sectoral/Thematic" or len(funds_to_process) < 3: continue
        
        proxy_key = CATEGORY_TO_BENCHMARK.get(category, "NIFTY 500")
        print(f"\n--- PROCESSING CATEGORY: {category} ({len(funds_to_process)} Funds) [Proxy: {proxy_key}] ---")
        
        successful_returns = []
        for idx, f in enumerate(funds_to_process, 1):
            print(f"[{idx}/{len(funds_to_process)}] {f['name']}...", end=" ", flush=True)
            df = fetch_nav_robust(f["code"], session)
            
            if df is not None:
                med_3y = calc_3y_median(df)
                if med_3y is not None:
                    successful_returns.append({"name": f["name"], "return_3y": med_3y})
                    final_output["fund_medians"][f["code"]] = med_3y
                    print(f"Data OK ({med_3y}%)")
                else:
                    print("Skipped (Insufficient History)")
            else:
                print("FAILED -> Added to Dead Letter Queue")
                dead_letter_queue.append((category, f))
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

    if dead_letter_queue:
        print(f"\n5. PROCESSING DEAD LETTER QUEUE ({len(dead_letter_queue)} Funds)")
        time.sleep(10)
        for cat, f in dead_letter_queue:
            print(f" -> Retrying {f['name']}...", end=" ", flush=True)
            df = fetch_nav_robust(f["code"], session)
            if df is not None:
                med_3y = calc_3y_median(df)
                if med_3y is not None:
                    final_output["fund_medians"][f["code"]] = med_3y
                    print(f"SUCCESS ({med_3y}%)")
                    # Note: We omit re-calculating category quartiles for 1-2 delayed funds to avoid mathematical edge-cases
                else: print("Insufficient History")
            else: print("PERMANENT FAILURE")
            time.sleep(2)

    with open('ranks.json', 'w') as f:
        json.dump(final_output, f, indent=4)
        
    print("\n==================================================")
    print("Done! Formatted Institutional ranks.json generated.")

if __name__ == "__main__":
    main()
