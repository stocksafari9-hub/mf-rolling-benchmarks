import requests
import pandas as pd
import numpy as np
import json
import time
from datetime import datetime

# Official Passive Index Proxies
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

def get_secure_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    return session

def categorize_fund(name):
    n = name.lower()
    
    # 1. Exclusion: Must be Direct Growth, Exclude Dividends, IDCW, & Regular
    if not (("direct" in n or "dir" in n) and ("growth" in n or "gr" in n)): return None
    if any(x in n for x in ["regular", "reg", "idcw", "dividend", "div", "income distribution", "withdrawal"]): return None
    
    # 2. Skip Passives, Closed-Ended Series, & International Funds
    if any(x in n for x in ["index", "idx", "etf", "exchange traded", "fof", "fund of fund", "child", "retirement", "series", "offshore", "global", "international"]): return None
    
    # 3. Hybrids
    if "arbitrage" in n: return "Arbitrage"
    if any(x in n for x in ["balanced advantage", "baf", "dynamic asset"]): return "Balanced Advantage"
    if "multi asset" in n: return "Multi Asset"
    if "equity savings" in n: return "Equity Savings"
    if any(x in n for x in ["aggressive hybrid", "balanced hybrid", "equity hybrid"]): return "Aggressive Hybrid"
    if any(x in n for x in ["conservative hybrid", "debt hybrid"]): return "Conservative Hybrid"

    # 4. Pure Equity
    if any(x in n for x in ["elss", "tax saver", "tax saving", "tax fund"]): return "ELSS"
    if any(x in n for x in ["large & mid", "large and mid", "large & midcap", "large and midcap", "largemidcap"]): return "Large & Mid Cap"
    if "small cap" in n or "smallcap" in n: return "Small Cap"
    if "mid cap" in n or "midcap" in n: return "Mid Cap"
    if any(x in n for x in ["large cap", "largecap", "bluechip", "blue chip"]): return "Large Cap"
    if "flexi cap" in n or "flexicap" in n: return "Flexi Cap"
    if "multi cap" in n or "multicap" in n: return "Multi Cap"
    if "value" in n or "contra" in n: return "Value/Contra"
    if "focused" in n or "focus" in n: return "Focused"

    # 5. Debt
    if "liquid" in n: return "Liquid"
    if "overnight" in n: return "Overnight"
    if "money market" in n: return "Money Market"
    if "ultra short" in n: return "Ultra Short Duration"
    if "low duration" in n: return "Low Duration"
    if "short duration" in n or "short term" in n: return "Short Duration"
    if "medium duration" in n: return "Medium Duration"
    # Safely route Long Duration Debt while blocking Equity 'Advantage' funds
    if any(x in n for x in ["long duration", "medium to long"]) or ("long term" in n and "advantage" not in n and "equity" not in n): return "Long Duration"
    if "corporate bond" in n: return "Corporate Bond"
    if "banking & psu" in n or "banking and psu" in n: return "Banking & PSU"
    if "credit risk" in n: return "Credit Risk"
    if "dynamic bond" in n: return "Dynamic Bond"
    if "gilt" in n or "constant maturity" in n: return "Gilt"
    if "floater" in n or "floating rate" in n: return "Floater"
    
    # Fallback
    return "Sectoral/Thematic"

def fetch_nav_history(scheme_code, session):
    try:
        url = f"https://api.mfapi.in/mf/{scheme_code}"
        response = session.get(url, timeout=10)
        if response.status_code != 200: 
            return None
        data = response.json().get("data", [])
        if not data: 
            return None
            
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y')
        df['nav'] = pd.to_numeric(df['nav'], errors='coerce')
        df = df.sort_values('date').reset_index(drop=True)
        return df
    except Exception as e:
        return None

def calc_3y_median(df):
    if df is None or len(df) <= 252 * 3: return None
    df['nav_ago_3Y'] = df['nav'].shift(252 * 3)
    rolling_cagr = ((df['nav'] / df['nav_ago_3Y']) ** (1 / 3)) - 1
    return round(rolling_cagr.median() * 100, 2)

def main():
    session = get_secure_session()
    
    print("1. Downloading AMFI Master List...")
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
                        
                        # Dynamically combine Scheme Name, Plan, and Option
                        fund_name_parts = [c.strip() for c in cols[3:-2] if c.strip()]
                        full_fund_name = " - ".join(fund_name_parts)
                        
                        nav_obj = {"nav": nav_val, "date": date_str, "schemeCode": scheme_code}
                        isin1, isin2 = cols[1].strip().upper(), cols[2].strip().upper()
                        if isin1 and isin1 != '-': nav_dict[isin1] = nav_obj
                        if isin2 and isin2 != '-': nav_dict[isin2] = nav_obj
                        
                        category = categorize_fund(full_fund_name)
                        if category:
                            if category not in categorized_funds: categorized_funds[category] = []
                            clean_name = full_fund_name.replace('- Direct Plan', '').replace('- Direct', '').replace('- Growth Option', '').replace('- Growth', '').replace('Growth', '').replace('-  ', '').strip()
                            if not any(f['code'] == scheme_code for f in categorized_funds[category]):
                                categorized_funds[category].append({"code": scheme_code, "name": clean_name})
                    except ValueError: pass

    with open('latest_navs.json', 'w') as f:
        json.dump(nav_dict, f)
    print(f"Saved latest_navs.json with {len(nav_dict)} ISINs")

    print("\n==================================================")
    print("      AMFI HIERARCHY CLASSIFICATION REPORT")
    print("==================================================")
    total_active = sum(len(funds) for funds in categorized_funds.values())
    print(f"Total Direct Growth Active Funds Detected: {total_active}")
    for cat, funds in sorted(categorized_funds.items()):
        print(f"{cat}: {len(funds)} funds")
    print("==================================================\n")

    final_output = {
        "last_updated": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
        "indices": {},
        "peer_groups": {}
    }

    print("2. Fetching Global Indices (3 sec gap)...")
    for index_name, code in INDEX_PROXIES.items():
        df = fetch_nav_history(code, session)
        if df is not None:
            final_output["indices"][index_name] = {"rolling_3Y": calc_3y_median(df) or "-"}
            print(f" -> Success: {index_name}")
        else:
            print(f" -> Failed: {index_name}")
        time.sleep(3) 

    print("\n3. STARTING FULL MARKET PEER GROUP ANALYSIS")
    
    # Process all categories except Sectoral/Thematic
    for category, funds_to_process in sorted(categorized_funds.items()):
        if category == "Sectoral/Thematic":
            print(f"\n--- SKIPPING: {category} (Meaningless Quartiles) ---")
            continue
            
        if len(funds_to_process) < 3:
            print(f"\n--- SKIPPING: {category} (Insufficient Peers: {len(funds_to_process)}) ---")
            continue

        print(f"\n--- PROCESSING CATEGORY: {category} ({len(funds_to_process)} Funds) ---")
        
        successful_returns = []
        failed_queue = []

        # Round 1: Initial Fetch
        for idx, f in enumerate(funds_to_process, 1):
            print(f"[{idx}/{len(funds_to_process)}] {f['name']}...", end=" ", flush=True)
            df = fetch_nav_history(f["code"], session)
            
            if df is not None:
                med_3y = calc_3y_median(df)
                if med_3y is not None:
                    successful_returns.append({"name": f["name"], "return_3y": med_3y})
                    print(f"Data OK ({med_3y}%)")
                else:
                    print(f"Skipped (Insufficient History)")
            else:
                print(f"DROPPED -> Queue")
                failed_queue.append(f)
            
            time.sleep(3)

        # Round 2: Retry Queue
        if failed_queue:
            print(f"\n   -> PROCESSING RETRIES: {len(failed_queue)} funds pending...")
            dead_letter_log = []
            for idx, f in enumerate(failed_queue, 1):
                print(f"   [Retry {idx}/{len(failed_queue)}] {f['name']}...", end=" ", flush=True)
                df = fetch_nav_history(f["code"], session)
                
                if df is not None:
                    med_3y = calc_3y_median(df)
                    if med_3y is not None:
                        successful_returns.append({"name": f["name"], "return_3y": med_3y})
                        print(f"SUCCESS ({med_3y}%)")
                    else:
                        print(f"Skipped (Insufficient History)")
                else:
                    print(f"DEAD LETTER")
                    dead_letter_log.append(f)
                
                time.sleep(3)

            if dead_letter_log:
                print(f"   !!! {len(dead_letter_log)} funds permanently failed to fetch.")

        # Calculate Quartiles
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
        json.dump(final_output, f, indent=4)
    print("\n==================================================")
    print("Done! Institutional ranks.json generated successfully.")

if __name__ == "__main__":
    main()
