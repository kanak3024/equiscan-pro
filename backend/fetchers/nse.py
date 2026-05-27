import asyncio
import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

# FIX: complete, current Chrome UA — truncated UA triggers NSE bot detection
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer":         "https://www.nseindia.com/",
    "Connection":      "keep-alive",
}

# ── HELPERS ───────────────────────────────────────────────────────────────────

async def _prime_nse_session(client: httpx.AsyncClient, page: str = "") -> None:
    """
    Prime NSE session cookies before hitting any API endpoint.
    FIX: proper 3-step sequence — homepage → relevant page → small delay.
         NSE bot detection checks both cookie presence and request timing.
    """
    try:
        await client.get("https://www.nseindia.com/", timeout=10)
        await asyncio.sleep(0.5)
        if page:
            await client.get(f"https://www.nseindia.com/{page}", timeout=10)
            await asyncio.sleep(0.3)
    except Exception:
        pass  # priming failures are non-fatal; the API call will surface the real error


async def _get_with_retry(
    client:   httpx.AsyncClient,
    url:      str,
    retries:  int = 3,
    delay:    float = 1.5,
) -> httpx.Response | None:
    """
    GET with retry logic for NSE's intermittent 401/403/429 responses.
    FIX: NSE API fails unpredictably during market hours without retries;
         silent failures were masking real data gaps.
    """
    for attempt in range(1, retries + 1):
        try:
            r = await client.get(url, timeout=15)
            if r.status_code == 200:
                return r
            logger.warning("NSE %s returned %d (attempt %d/%d)", url, r.status_code, attempt, retries)
        except httpx.RequestError as e:
            logger.warning("NSE request error %s (attempt %d/%d): %s", url, attempt, retries, e)
        if attempt < retries:
            await asyncio.sleep(delay * attempt)  # back-off: 1.5s, 3s
    return None


# ── FII / DII ─────────────────────────────────────────────────────────────────

async def get_fii_dii_data() -> dict:
    """
    Get latest FII/DII buying/selling data from NSE.
    FIX: was summing across all days in the response (5-10 days worth),
         now filters to latest date only for accurate single-day figures.
    """
    try:
        async with httpx.AsyncClient(
            timeout=15,
            headers=NSE_HEADERS,
            follow_redirects=True,
        ) as client:
            await _prime_nse_session(client, "market-data/fii-dii-activity")

            r = await _get_with_retry(
                client,
                "https://www.nseindia.com/api/fiidiiTradeReact",
            )
            if r is None:
                return {"error": "NSE FII/DII endpoint unavailable after retries"}

            try:
                data = r.json()
            except Exception:
                return {"error": f"NSE FII/DII returned non-JSON response (status {r.status_code})"}

            if not data:
                return {"error": "NSE FII/DII returned empty data"}

            # FIX: filter to latest date only — endpoint returns multiple days
            latest_date = max(
                (item.get("date", "") for item in data),
                default="",
            )
            fii_net = 0.0
            dii_net = 0.0

            for item in data:
                if item.get("date", "") != latest_date:
                    continue
                category = item.get("category", "").upper()
                try:
                    net = float(str(item.get("netValue", "0")).replace(",", ""))
                except (ValueError, TypeError):
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
                "date":        latest_date or datetime.now().strftime("%Y-%m-%d"),
                "raw":         data[:3],
                "error":       None,
            }

    except Exception as e:
        logger.exception("get_fii_dii_data failed")
        return {"error": str(e)}


# ── BULK DEALS ────────────────────────────────────────────────────────────────

async def get_bulk_deals() -> list:
    """
    Get bulk deals from NSE.
    FIX: added status code check and JSON error handling — previously a 403
         or HTML error page would be silently swallowed, returning [] as if
         there were genuinely no bulk deals that day.
    """
    try:
        async with httpx.AsyncClient(
            timeout=15,
            headers=NSE_HEADERS,
            follow_redirects=True,
        ) as client:
            # FIX: prime with the relevant page, not just the homepage
            await _prime_nse_session(client, "market-data/bulk-block-deals")

            r = await _get_with_retry(
                client,
                "https://www.nseindia.com/api/bulk-deals",
            )
            if r is None:
                logger.warning("get_bulk_deals: NSE endpoint unavailable after retries")
                return []

            try:
                data = r.json()
            except Exception:
                logger.warning("get_bulk_deals: non-JSON response (status %d)", r.status_code)
                return []

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
        logger.exception("get_bulk_deals failed")
        return []


# ── SHAREHOLDING ──────────────────────────────────────────────────────────────

async def get_stock_shareholding(symbol: str) -> dict:
    """
    Get shareholding pattern for a stock from NSE.
    FIX: now returns the quarter date alongside percentages so callers know
         how stale the data is (NSE publishes shareholding quarterly, not daily).
    """
    try:
        async with httpx.AsyncClient(
            timeout=15,
            headers=NSE_HEADERS,
            follow_redirects=True,
        ) as client:
            await _prime_nse_session(client, f"get-quotes/equity?symbol={symbol}")

            r = await _get_with_retry(
                client,
                f"https://www.nseindia.com/api/shareholding-patterns?symbol={symbol}",
            )
            if r is None:
                return {"symbol": symbol, "error": "NSE shareholding endpoint unavailable after retries"}

            try:
                data = r.json()
            except Exception:
                return {"symbol": symbol, "error": f"Non-JSON response (status {r.status_code})"}

            shareholding = data.get("data", [])
            if not shareholding:
                return {"symbol": symbol, "error": "No shareholding data returned"}

            latest      = shareholding[0]
            # FIX: surface the quarter date so callers know data freshness
            quarter_end = latest.get("endDate", "unknown")

            fii      = 0.0
            dii      = 0.0
            promoter = 0.0

            for item in latest.get("shareholdingPatterns", {}).get("data", []):
                category = item.get("category", "").upper()
                try:
                    pct = float(str(item.get("percentage", "0")).replace(",", "") or "0")
                except (ValueError, TypeError):
                    pct = 0.0

                if "PROMOTER" in category:
                    promoter += pct
                elif "FII" in category or "FPI" in category:
                    fii += pct
                elif "DII" in category or "MUTUAL" in category or "INSURANCE" in category:
                    dii += pct

            return {
                "symbol":       symbol,
                "promoter":     round(promoter, 2),
                "fii":          round(fii, 2),
                "dii":          round(dii, 2),
                "quarter_end":  quarter_end,   # FIX: added — data is quarterly, not live
                "error":        None,
            }

    except Exception as e:
        logger.exception("get_stock_shareholding failed for %s", symbol)
        return {"symbol": symbol, "error": str(e)}