import requests
import pandas as pd
import numpy as np
import json
from datetime import datetime

# Exact AMFI Scheme Codes for the Official Passive Index Proxies
INDEX_PROXIES = {
    "NIFTY 50": "147794",              
    "NIFTY NEXT 50": "147796",         
    "NIFTY 500": "147625",             
    "NIFTY MIDCAP 150": "147622",      
    "NIFTY SMALLCAP 250": "147623",    
    "NIFTY LARGE MIDCAP 250": "149343", # Edelweiss Large Midcap 250
    "NASDAQ 100": "145552"             
}

def fetch_nav_history(scheme_code):
    url = f"https://api.mfapi.in/mf/{scheme_code}"
    response = requests.get(url)
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

def calculate_rolling_returns(df):
    periods = {'1Y': 252, '3Y': 252 * 3, '5Y': 252 * 5}
    results = {}
    for label, days in periods.items():
        if len(df) > days:
            df[f'nav_ago_{label}'] = df['nav'].shift(days)
            years = days / 252
            rolling_cagr = ((df['nav'] / df[f'nav_ago_{label}']) ** (1 / years)) - 1
            median_return = rolling_cagr.median() * 100
            results[label] = round(median_return, 2)
        else:
            results[label] = "-"
    return results

def fetch_amfi_navs():
    print("Downloading latest AMFI NAVs...")
    url = "https://www.amfiindia.com/spages/NAVAll.txt"
    response = requests.get(url, timeout=10)
    nav_dict = {}
    if response.status_code == 200:
        lines = response.text.split('\n')
        for line in lines:
            cols = line.split(';')
            if len(cols) >= 6:
                nav_str = cols[-2].strip()
                date_str = cols[-1].strip()
                if nav_str and nav_str != 'N.A.':
                    try:
                        nav_val = float(nav_str)
                        scheme_code = cols[0].strip()
                        nav_obj = {"nav": nav_val, "date": date_str, "schemeCode": scheme_code}
                        
                        isin1 = cols[1].strip().upper()
                        if isin1 and isin1 != '-':
                            nav_dict[isin1] = nav_obj
                        
                        isin2 = cols[2].strip().upper()
                        if isin2 and isin2 != '-':
                            nav_dict[isin2] = nav_obj
                    except ValueError:
                        pass
    
    with open('latest_navs.json', 'w') as f:
        json.dump(nav_dict, f)
    print(f"Successfully saved {len(nav_dict)} ISINs to latest_navs.json")

def main():
    final_output = {
        "last_updated": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
        "indices": {}
    }
    
    for index_name, code in INDEX_PROXIES.items():
        print(f"Processing {index_name}...")
        df = fetch_nav_history(code)
        if df is not None:
            latest_nav = df.iloc[-1]['nav']
            latest_date = df.iloc[-1]['date'].strftime('%Y-%m-%d')
            rolling = calculate_rolling_returns(df)
            
            final_output["indices"][index_name] = {
                "latest_nav": latest_nav,
                "nav_date": latest_date,
                "rolling_1Y": rolling.get('1Y', '-'),
                "rolling_3Y": rolling.get('3Y', '-'),
                "rolling_5Y": rolling.get('5Y', '-')
            }
            
    with open('ranks.json', 'w') as f:
        json.dump(final_output, f, indent=4)
    print("Successfully generated ranks.json")
    
    fetch_amfi_navs()

if __name__ == "__main__":
    main()
