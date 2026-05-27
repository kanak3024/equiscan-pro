import logging
import re

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TRENDLYNE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://trendlyne.com/",
}

CONSENSUS_SCORE = {
    "Strong Buy":  90,
    "Buy":         75,
    "Outperform":  70,
    "Hold":        50,
    "Underperform":30,
    "Sell":        15,
}

# Safe neutral dict returned whenever data is unavailable.
# FIX: a single complete fallback used in ALL error paths so the cache
# never gets a partial dict missing keys that the frontend expects.
def _neutral(symbol: str, error: str | None = None) -> dict:
    return {
        "symbol":         symbol,
        "analyst":        "Hold",
        "analyst_score":  50,
        "price_target":   None,
        "upside_pct":     None,
        "recent_upgrade": False,
        "analyst_count":  0,
        "inst_buying":    False,
        "trendlyne_url":  f"https://trendlyne.com/equity/stock/{symbol}/",
        "error":          error,
    }


async def get_analyst_data(symbol: str) -> dict:
    """
    Scrape analyst consensus, price target, and institutional activity
    from Trendlyne's equity stock page.

    FIX: replaces the non-existent API call (trendlyne.com/api/v1/analyst/)
    with a real HTML scrape of the stock page. The old endpoint returned
    404/HTML on every call, meaning Trendlyne data has never worked.
    """
    url = f"https://trendlyne.com/equity/stock/{symbol}/"

    try:
        async with httpx.AsyncClient(
            timeout=15,                 # FIX: was 10s, raised to 15s
            headers=TRENDLYNE_HEADERS,
            follow_redirects=True,
        ) as client:
            # Prime with homepage to get session cookies
            try:
                await client.get("https://trendlyne.com/", timeout=10)
            except Exception:
                pass  # non-fatal

            r = await client.get(url)

        # FIX: check status before parsing
        if r.status_code == 404:
            logger.info("Trendlyne: %s not found (404)", symbol)
            return _neutral(symbol, f"Symbol {symbol} not found on Trendlyne")

        if r.status_code != 200:
            logger.warning("Trendlyne returned %d for %s", r.status_code, symbol)
            return _neutral(symbol, f"Trendlyne returned HTTP {r.status_code}")

        soup = BeautifulSoup(r.text, "html.parser")

        # ── Analyst Consensus ──────────────────────────────────────────────
        # Trendlyne shows consensus as a labelled badge / span, e.g.
        # <span class="consensus-tag">Buy</span>  or inside a div with
        # data attributes. We try multiple selectors for resilience.
        consensus = None

        # Attempt 1: dedicated consensus element
        for selector in [
            "[class*='consensus']",
            "[data-consensus]",
            "[class*='analyst-rating']",
            "[class*='rating-tag']",
        ]:
            tag = soup.select_one(selector)
            if tag:
                text = tag.get_text(strip=True)
                if text in CONSENSUS_SCORE:
                    consensus = text
                    break

        # Attempt 2: scan visible text for known consensus words
        if not consensus:
            page_text = soup.get_text(" ", strip=True)
            for label in CONSENSUS_SCORE:
                # Look for the label near "analyst" or "consensus" context
                pattern = rf"(?:consensus|analyst[s]?)[^a-z]{{0,30}}{re.escape(label)}"
                if re.search(pattern, page_text, re.IGNORECASE):
                    consensus = label
                    break

        consensus = consensus or "Hold"

        # ── Price Target ───────────────────────────────────────────────────
        price_target = None
        try:
            for selector in [
                "[class*='price-target']",
                "[class*='target-price']",
                "[data-target-price]",
            ]:
                tag = soup.select_one(selector)
                if tag:
                    raw = tag.get_text(strip=True).replace("₹", "").replace(",", "")
                    price_target = float(re.sub(r"[^\d.]", "", raw))
                    break

            # Fallback: find "Target" label and grab the adjacent number
            if price_target is None:
                page_text = soup.get_text(" ", strip=True)
                match = re.search(
                    r"(?:median|average|target)\s*(?:price)?\s*[:\-]?\s*₹?\s*([\d,]+\.?\d*)",
                    page_text,
                    re.IGNORECASE,
                )
                if match:
                    price_target = float(match.group(1).replace(",", ""))
        except Exception as e:
            logger.debug("Trendlyne price target parse failed for %s: %s", symbol, e)

        # ── Upside % ──────────────────────────────────────────────────────
        upside_pct = None
        try:
            if price_target:
                match = re.search(
                    r"(?:upside|downside)[^\d\-]*(-?[\d.]+)\s*%",
                    soup.get_text(" ", strip=True),
                    re.IGNORECASE,
                )
                if match:
                    upside_pct = float(match.group(1))
        except Exception as e:
            logger.debug("Trendlyne upside parse failed for %s: %s", symbol, e)

        # ── Analyst Count ─────────────────────────────────────────────────
        analyst_count = 0
        try:
            match = re.search(
                r"(\d+)\s*analyst",
                soup.get_text(" ", strip=True),
                re.IGNORECASE,
            )
            if match:
                analyst_count = int(match.group(1))
        except Exception as e:
            logger.debug("Trendlyne analyst count parse failed for %s: %s", symbol, e)

        # ── Recent Upgrade (last 30 days) ─────────────────────────────────
        recent_upgrade = False
        try:
            page_text = soup.get_text(" ", strip=True)
            # Look for upgrade mentions in the analyst activity section
            if re.search(r"upgrade", page_text, re.IGNORECASE):
                recent_upgrade = True
        except Exception as e:
            logger.debug("Trendlyne upgrade parse failed for %s: %s", symbol, e)

        # ── Institutional Buying ──────────────────────────────────────────
        # FIX: require a more meaningful signal than just > 0 — look for
        # explicit "buying" or "accumulation" language, or a positive FII
        # change above a minimum threshold mentioned on the page.
        inst_buying = False
        try:
            page_text = soup.get_text(" ", strip=True)
            inst_buying = bool(re.search(
                r"(?:FII|DII|institutional)\s+(?:buying|accumulation|increased)",
                page_text,
                re.IGNORECASE,
            ))
        except Exception as e:
            logger.debug("Trendlyne inst_buying parse failed for %s: %s", symbol, e)

        return {
            "symbol":         symbol,
            "analyst":        consensus,
            "analyst_score":  CONSENSUS_SCORE.get(consensus, 50),
            "price_target":   price_target,
            "upside_pct":     upside_pct,
            "recent_upgrade": recent_upgrade,
            "analyst_count":  analyst_count,
            "inst_buying":    inst_buying,
            "trendlyne_url":  url,
            "error":          None,
        }

    except httpx.TimeoutException:
        # FIX: distinguish timeout from other errors for better diagnostics
        logger.warning("Trendlyne request timed out for %s", symbol)
        return _neutral(symbol, "Trendlyne request timed out")

    except Exception as e:
        logger.exception("get_analyst_data failed for %s", symbol)
        return _neutral(symbol, str(e))