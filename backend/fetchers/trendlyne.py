import os
import httpx

async def get_analyst_data(symbol: str) -> dict:
    """
    Trendlyne API for analyst ratings and price targets.
    Falls back to neutral if token not configured.
    """
    token = os.getenv("TRENDLYNE_TOKEN", "")

    if not token or token == "your_trendlyne_token_here":
        # Fallback — return neutral until token is configured
        return {
            "symbol":        symbol,
            "analyst":       "Hold",
            "analyst_score": 50,
            "price_target":  0,
            "recent_upgrade": False,
            "inst_buying":   False,
            "error":         "Trendlyne token not configured"
        }

    try:
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"https://trendlyne.com/api/v1/analyst/{symbol}/",
                headers=headers
            )
            d = r.json()

            consensus = d.get("consensus", "Hold")
            score_map = {
                "Strong Buy": 90,
                "Buy": 75,
                "Outperform": 70,
                "Hold": 50,
                "Underperform": 30,
                "Sell": 15
            }

            return {
                "symbol":         symbol,
                "analyst":        consensus,
                "analyst_score":  score_map.get(consensus, 50),
                "price_target":   d.get("median_target", 0),
                "recent_upgrade": d.get("upgrades_30d", 0) > 0,
                "inst_buying":    d.get("fii_dii_change", 0) > 0,
                "error":          None
            }

    except Exception as e:
        return {"symbol": symbol, "error": str(e)}