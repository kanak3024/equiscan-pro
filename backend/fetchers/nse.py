import httpx
import json
from datetime import datetime

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

async def get_fii_dii_data() -> dict:
    """Get latest FII/DII buying/selling data from NSE"""
    try:
        async with httpx.AsyncClient(
            timeout=15,
            headers=NSE_HEADERS,
            follow_redirects=True
        ) as client:
            # Get cookies first
            await client.get("https://www.nseindia.com/market-data/fii-dii-activity")
            await client.get("https://www.nseindia.com/")
            
            # Now get the data
            r = await client.get(
                "https://www.nseindia.com/api/fiidiiTradeReact",
                headers={
                    **NSE_HEADERS,
                    "X-Requested-With": "XMLHttpRequest",
                }
            )
            
            if r.status_code != 200:
                return {"error": f"NSE returned {r.status_code}"}
            
            data = r.json()
            fii_net = 0.0
            dii_net = 0.0
            
            for item in data:
                category = item.get("category", "").upper()
                try:
                    net = float(str(item.get("netValue", "0")).replace(",", ""))
                except:
                    net = 0.0
                if "FII" in category or "FPI" in category:
                    fii_net += net
                elif "DII" in category:
                    dii_net += net
            
            return {
                "fii_net":     round(fii_net, 2),
                "dii_net":     round(dii_net, 2),
                "fii_buying":  fii_net > 0,
                "dii_buying":  dii_net > 0,
                "both_buying": fii_net > 0 and dii_net > 0,
                "date":        datetime.now().strftime("%Y-%m-%d"),
                "raw":         data[:3],
                "error":       None
            }
    except Exception as e:
        return {"error": str(e)}

async def get_bulk_deals() -> list:
    """Get bulk deals from NSE"""
    try:
        async with httpx.AsyncClient(timeout=15, headers=NSE_HEADERS) as client:
            await client.get("https://www.nseindia.com/")
            r = await client.get(
                "https://www.nseindia.com/api/bulk-deals"
            )
            data = r.json()
            deals = data.get("data", [])
            return [
                {
                    "symbol":   d.get("symbol", ""),
                    "client":   d.get("clientName", ""),
                    "type":     d.get("buySell", ""),
                    "quantity": d.get("quantityTraded", 0),
                    "price":    d.get("tradePrice", 0),
                }
                for d in deals[:20]
            ]
    except Exception as e:
        return []

async def get_stock_shareholding(symbol: str) -> dict:
    """Get shareholding pattern for a stock from NSE"""
    try:
        async with httpx.AsyncClient(timeout=15, headers=NSE_HEADERS) as client:
            await client.get("https://www.nseindia.com/")
            r = await client.get(
                f"https://www.nseindia.com/api/shareholding-patterns?symbol={symbol}"
            )
            data = r.json()
            
            shareholding = data.get("data", [])
            if not shareholding:
                return {"error": "No data"}
            
            latest = shareholding[0]
            
            fii = 0.0
            dii = 0.0
            promoter = 0.0
            
            for item in latest.get("shareholdingPatterns", {}).get("data", []):
                category = item.get("category", "").upper()
                pct = float(str(item.get("percentage", "0")).replace(",", "") or "0")
                
                if "PROMOTER" in category:
                    promoter += pct
                elif "FII" in category or "FPI" in category:
                    fii += pct
                elif "DII" in category or "MUTUAL" in category or "INSURANCE" in category:
                    dii += pct
            
            return {
                "symbol":   symbol,
                "promoter": round(promoter, 2),
                "fii":      round(fii, 2),
                "dii":      round(dii, 2),
                "error":    None
            }
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}