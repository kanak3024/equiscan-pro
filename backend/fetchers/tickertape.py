import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.tickertape.in/",
}

async def get_analyst_rating(symbol: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=15, headers=HEADERS, follow_redirects=True) as client:

            # Search for stock
            search_r = await client.get(
                f"https://api.tickertape.in/stocks/search?text={symbol}&count=3"
            )
            search_data = search_r.json()

            # Parse new response structure
            results = search_data.get("data", {}).get("searchResults", [])
            if not results:
                return {"symbol": symbol, "error": "Not found on Tickertape"}

            # Find exact match by ticker
            sid = None
            for r in results:
                ticker = r.get("stock", {}).get("info", {}).get("ticker", "")
                if ticker == symbol:
                    sid = r.get("sid", "")
                    break
            
            # Fallback to first result
            if not sid:
                sid = results[0].get("sid", "")

            if not sid:
                return {"symbol": symbol, "error": "No SID found"}

            # Get analyst forecast
            analyst_r = await client.get(
                f"https://api.tickertape.in/stocks/forecast/{sid}"
            )
            analyst_data = analyst_r.json()
            forecast = analyst_data.get("data", {})

            # Parse ratings
            ratings = forecast.get("recommendations", {})
            buy     = ratings.get("buy", 0)
            hold    = ratings.get("hold", 0)
            sell    = ratings.get("sell", 0)
            total   = buy + hold + sell

            if total == 0:
                consensus = "Hold"
                score     = 50
            elif buy / total >= 0.6:
                consensus = "Buy"
                score     = round(70 + (buy / total) * 30)
            elif buy / total >= 0.4:
                consensus = "Outperform"
                score     = round(55 + (buy / total) * 30)
            elif sell / total >= 0.5:
                consensus = "Sell"
                score     = round(sell / total * 30)
            else:
                consensus = "Hold"
                score     = 50

            price_target = forecast.get("priceTarget", {}).get("mean", 0)

            return {
                "symbol":         symbol,
                "analyst":        consensus,
                "analyst_score":  score,
                "price_target":   round(float(price_target), 2) if price_target else 0,
                "buy_count":      buy,
                "hold_count":     hold,
                "sell_count":     sell,
                "total_analysts": total,
                "recent_upgrade": buy > hold,
                "error":          None
            }

    except Exception as e:
        return {"symbol": symbol, "error": str(e)}
