import requests
import pandas as pd
import numpy as np
import json
from datetime import datetime

# Exact AMFI Scheme Codes for the Official Passive Index Funds
INDEX_PROXIES = {
    "NIFTY 50": "147794",              # Motilal Oswal Nifty 50 Index Fund Direct G
    "NIFTY NEXT 50": "147796",         # Motilal Oswal Nifty Next 50 Index Fund Direct G
    "NIFTY 500": "147625",             # Motilal Oswal Nifty 500 Index Fund Direct G
    "NIFTY MIDCAP 150": "147622",      # Motilal Oswal Nifty Midcap 150 Index Fund Direct G
    "NIFTY SMALLCAP 250": "147623",    # Motilal Oswal Nifty Smallcap 250 Index Fund Direct G
    "NIFTY BANK": "147620",            # Motilal Oswal Nifty Bank Index Fund Direct G
    "NASDAQ 100": "145552"             # Motilal Oswal Nasdaq 100 FoF Direct G
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
    # Assume 252 trading days in a year
    periods = {'1Y': 252, '3Y': 252 * 3, '5Y': 252 * 5}
    results = {}
    
    for label, days in periods.items():
        if len(df) > days:
            # Shift the series by 'days' to simulate the buy price X years ago
            df[f'nav_ago_{label}'] = df['nav'].shift(days)
            # Calculate the point-to-point CAGR for that specific rolling window
            years = days / 252
            rolling_cagr = ((df['nav'] / df[f'nav_ago_{label}']) ** (1 / years)) - 1
            # Extract the median of all those overlapping rolling periods
            median_return = rolling_cagr.median() * 100
            results[label] = round(median_return, 2)
        else:
            results[label] = "-"
            
    return results

def main():
    final_output = {
        "last_updated": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
        "indices": {}
    }
    
    for index_name, code in INDEX_PROXIES.items():
        print(f"Processing {index_name}...")
        df = fetch_nav_history(code)
        if df is not None:
            # Get latest NAV for Shadow XIRR mapping
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

if __name__ == "__main__":
    main()
