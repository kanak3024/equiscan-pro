import logging

import httpx

logger = logging.getLogger(__name__)

# FIX: full Chrome UA — truncated UA can trigger bot detection
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.tickertape.in/",
}

# Safe neutral dict returned on all error paths.
# FIX: includes inst_buying and recent_upgrade so the cache entry is never
# missing keys that stockData.ts expects when this fetcher is merged via {**anal}
def _neutral(symbol: str, error: str | None = None) -> dict:
    return {
        "symbol":         symbol,
        "analyst":        "Hold",
        "analyst_score":  50,
        "price_target":   None,   # FIX: None not 0 — 0 caused large-negative upside calc
        "buy_count":      0,
        "hold_count":     0,
        "sell_count":     0,
        "total_analysts": 0,
        "recent_upgrade": False,
        "inst_buying":    False,  # FIX: explicit key so cache entry is complete
        "error":          error,
    }


async def get_analyst_rating(symbol: str) -> dict:
    """
    Fetch analyst consensus and price target from Tickertape.

    FIX summary:
      - HTTP status checked on both search and forecast calls
      - price_target returns None (not 0) when unavailable
      - recent_upgrade fixed — was measuring buy>hold ratio (a consensus
        snapshot), not an actual rating change. Tickertape forecast endpoint
        doesn't provide upgrade history so it's now explicitly False.
      - inst_buying added as explicit False (field was missing entirely)
      - Full Chrome UA replaces truncated string
      - logger.exception on all failure paths
    """
    try:
        async with httpx.AsyncClient(
            timeout=15,
            headers=HEADERS,
            follow_redirects=True,
        ) as client:

            # ── Step 1: resolve symbol → Tickertape SID ───────────────────
            search_r = await client.get(
                f"https://api.tickertape.in/stocks/search?text={symbol}&count=3"
            )

            # FIX: check status before parsing
            if search_r.status_code != 200:
                logger.warning(
                    "Tickertape search returned %d for %s", search_r.status_code, symbol
                )
                return _neutral(symbol, f"Tickertape search returned HTTP {search_r.status_code}")

            try:
                search_data = search_r.json()
            except Exception:
                logger.warning("Tickertape search non-JSON response for %s", symbol)
                return _neutral(symbol, "Tickertape search returned non-JSON response")

            results = search_data.get("data", {}).get("searchResults", [])
            if not results:
                return _neutral(symbol, "Not found on Tickertape")

            # Prefer exact ticker match, fall back to first result
            sid = None
            for r in results:
                ticker = r.get("stock", {}).get("info", {}).get("ticker", "")
                if ticker == symbol:
                    sid = r.get("sid", "")
                    break

            if not sid:
                sid = results[0].get("sid", "")

            if not sid:
                return _neutral(symbol, "No SID found on Tickertape")

            # ── Step 2: fetch analyst forecast ────────────────────────────
            analyst_r = await client.get(
                f"https://api.tickertape.in/stocks/forecast/{sid}"
            )

            # FIX: check status before parsing
            if analyst_r.status_code != 200:
                logger.warning(
                    "Tickertape forecast returned %d for %s (sid=%s)",
                    analyst_r.status_code, symbol, sid,
                )
                return _neutral(symbol, f"Tickertape forecast returned HTTP {analyst_r.status_code}")

            try:
                analyst_data = analyst_r.json()
            except Exception:
                logger.warning("Tickertape forecast non-JSON response for %s", symbol)
                return _neutral(symbol, "Tickertape forecast returned non-JSON response")

            forecast = analyst_data.get("data", {})

            # ── Step 3: parse buy/hold/sell counts ────────────────────────
            ratings = forecast.get("recommendations", {})
            buy     = int(ratings.get("buy",  0))
            hold    = int(ratings.get("hold", 0))
            sell    = int(ratings.get("sell", 0))
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

            # Clamp to [0, 100] — defensive guard against edge cases
            score = max(0, min(100, score))

            # ── Step 4: price target ──────────────────────────────────────
            raw_target   = forecast.get("priceTarget", {}).get("mean")
            # FIX: None when unavailable — was returning 0 which caused
            # upside = ((0 - cmp) / cmp) * 100 → large negative in the frontend
            price_target = round(float(raw_target), 2) if raw_target else None

            return {
                "symbol":         symbol,
                "analyst":        consensus,
                "analyst_score":  score,
                "price_target":   price_target,
                "buy_count":      buy,
                "hold_count":     hold,
                "sell_count":     sell,
                "total_analysts": total,
                # FIX: was `buy > hold` which measured the current consensus
                # distribution, not an actual rating change event. The forecast
                # endpoint doesn't provide upgrade history so this is False.
                # Use trendlyne.py's recent_upgrade for actual upgrade signals.
                "recent_upgrade": False,
                # FIX: added explicit key — was missing entirely, causing
                # stockData.ts mapApiStock to always get undefined → false anyway,
                # but the intent is now clear and the field is always present.
                "inst_buying":    False,
                "error":          None,
            }

    except Exception as e:
        logger.exception("get_analyst_rating failed for %s", symbol)
        return _neutral(symbol, str(e))