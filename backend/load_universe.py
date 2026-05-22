import pandas as pd
import json

# Read both CSV files
nifty500 = pd.read_csv("ind_nifty500list.csv")
smallcap250 = pd.read_csv("ind_niftysmallcap250list.csv")

# Extract symbols and company info
def extract_stocks(df, index_name):
    stocks = []
    for _, row in df.iterrows():
        stocks.append({
            "symbol":   row["Symbol"].strip(),
            "name":     row["Company Name"].strip(),
            "sector":   row["Industry"].strip(),
            "index":    index_name
        })
    return stocks

n500 = extract_stocks(nifty500, "Nifty500")
sc250 = extract_stocks(smallcap250, "SmallCap250")

# Combine and deduplicate by symbol
all_stocks = {s["symbol"]: s for s in n500}
for s in sc250:
    if s["symbol"] not in all_stocks:
        all_stocks[s["symbol"]] = s

final = list(all_stocks.values())

# Save to JSON
with open("universe.json", "w") as f:
    json.dump(final, f, indent=2)

print(f"Nifty500:     {len(n500)} stocks")
print(f"SmallCap250:  {len(sc250)} stocks")
print(f"Combined:     {len(final)} unique stocks")
print(f"Saved to:     universe.json")
print()
print("Sample:")
for s in final[:5]:
    print(f"  {s['symbol']:20} {s['name']:40} {s['sector']}")