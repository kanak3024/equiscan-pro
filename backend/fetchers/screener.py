import os
import re
import logging

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SCREENER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.screener.in/",
}


def get_screener_session() -> str:
    return os.getenv("SCREENER_SESSION", "")


def parse_number(text: str) -> float:
    """Parse Indian-formatted number strings, including parenthetical negatives."""
    if not text:
        return 0.0
    text = (
        text.replace(",", "")
            .replace("%", "")
            .replace("₹", "")
            .replace("Cr", "")
            .strip()
    )
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        return float(text)
    except ValueError:
        return 0.0


async def _fetch_soup(
    client: httpx.AsyncClient,
    url:    str,
    headers: dict,
) -> BeautifulSoup | None:
    """
    Fetch a URL and return a BeautifulSoup object.
    FIX: checks HTTP status before parsing — a 403/429/redirect was previously
         parsed as real HTML, causing all fields to silently return 0/False.
    Returns None if the response is not a valid 200 page.
    """
    try:
        r = await client.get(url, headers=headers, timeout=20)
    except httpx.RequestError as e:
        logger.warning("HTTP request failed for %s: %s", url, e)
        return None

    if r.status_code != 200:
        logger.warning("Screener returned %d for %s", r.status_code, url)
        return None

    # Screener redirects to /login/ when session is expired — detect silently
    if "/login/" in str(r.url):
        logger.warning("Screener session expired or invalid — redirected to login for %s", url)
        return None

    return BeautifulSoup(r.text, "html.parser")


async def get_fundamentals(symbol: str) -> dict:
    """
    Scrape fundamental data for a stock from Screener.in.

    FIX summary:
      - Validates session cookie before making any request
      - Checks HTTP status code; treats non-200 as an error
      - Falls back to standalone URL when consolidated page is unavailable
      - cashflow_5q renamed cashflow_5y (Screener shows annual CF, not quarterly)
      - revenue_growth now targets the annual P&L section explicitly
      - promoter_stable uses QoQ change (< 2pp) instead of latest-vs-oldest
      - ipo_year defaults to None instead of 2020
      - All bare except blocks replaced with logger.debug for diagnosability
    """

    # FIX: validate session before sending requests
    session = get_screener_session()
    if not session:
        logger.error("SCREENER_SESSION env var is not set")
        return {"symbol": symbol, "error": "SCREENER_SESSION not configured"}

    headers = {
        **SCREENER_HEADERS,
        "Cookie": f"sessionid={session}",
    }

    try:
        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
        ) as client:

            # FIX: try consolidated first, fall back to standalone
            # Many PSUs, banks, NBFCs and smaller mid-caps have no consolidated view
            soup = await _fetch_soup(
                client,
                f"https://www.screener.in/company/{symbol}/consolidated/",
                headers,
            )
            used_consolidated = soup is not None

            if soup is None:
                logger.info(
                    "%s: consolidated page unavailable — trying standalone", symbol
                )
                soup = await _fetch_soup(
                    client,
                    f"https://www.screener.in/company/{symbol}/",
                    headers,
                )

            if soup is None:
                return {"symbol": symbol, "error": "Screener page unavailable (check session or symbol)"}

            # ── Top Ratios ─────────────────────────────────────────────────
            ratios: dict[str, str] = {}
            for li in soup.select("#top-ratios li"):
                name  = li.select_one(".name")
                value = li.select_one(".number")
                if name and value:
                    ratios[name.text.strip()] = value.text.strip()

            mcap = parse_number(ratios.get("Market Cap", "0"))
            pe   = parse_number(ratios.get("Stock P/E", "0")) or None
            roe  = parse_number(ratios.get("ROE", "0"))

            # ── Debt / Equity ──────────────────────────────────────────────
            # Primary: labelled row in any table (annual ratios section)
            debt_eq = 0.0
            try:
                for table in soup.select("table"):
                    for row in table.select("tr"):
                        cols  = row.select("td")
                        if len(cols) < 2:
                            continue
                        label = cols[0].text.strip()
                        if any(x in label for x in ["Debt to Equity", "Debt / Equity", "D/E"]):
                            debt_eq = parse_number(cols[-1].text)
                            break
                    if debt_eq:
                        break
            except Exception as e:
                logger.debug("%s: D/E table parse failed: %s", symbol, e)

            # Fallback: compute from balance sheet borrowings / equity
            if debt_eq == 0.0:
                try:
                    bs_section = soup.find("section", {"id": "balance-sheet"})
                    if bs_section:
                        borrowings     = 0.0
                        equity_capital = 0.0
                        reserves       = 0.0
                        for row in bs_section.select("tr"):
                            cols  = row.select("td")
                            if len(cols) < 2:
                                continue
                            label = cols[0].text.strip()
                            val   = parse_number(cols[-1].text)
                            if "Borrowings" in label:
                                borrowings = val
                            if "Equity Capital" in label:
                                equity_capital = val
                            if "Reserves" in label:
                                reserves = val
                        total_equity = equity_capital + reserves
                        if total_equity > 0 and borrowings > 0:
                            debt_eq = round(borrowings / total_equity, 2)
                except Exception as e:
                    logger.debug("%s: balance-sheet D/E fallback failed: %s", symbol, e)

            # ── Revenue Growth ─────────────────────────────────────────────
            # FIX: explicitly target the annual P&L section to avoid picking up
            # quarterly absolute revenue values which are not growth rates.
            revenue_growth = 0.0
            try:
                pl_section = soup.find("section", {"id": "profit-loss"})
                if pl_section:
                    for row in pl_section.select("tr"):
                        cols  = row.select("td")
                        if len(cols) < 2:
                            continue
                        label = cols[0].text.strip()
                        if any(x in label for x in ["Sales Growth", "Revenue Growth", "Compounded Sales Growth"]):
                            vals = [
                                parse_number(c.text)
                                for c in cols[1:]
                                if c.text.strip() and c.text.strip() not in ("-", "")
                            ]
                            if vals:
                                revenue_growth = vals[-1]
                                break
            except Exception as e:
                logger.debug("%s: revenue_growth P&L parse failed: %s", symbol, e)

            # Fallback: regex scan over company-ratios section
            if revenue_growth == 0.0:
                try:
                    for section in soup.select(".company-ratios"):
                        text    = section.get_text()
                        matches = re.findall(r"Sales Growth[^\d\-]*(-?\d+\.?\d*)", text)
                        if matches:
                            revenue_growth = float(matches[0])
                            break
                except Exception as e:
                    logger.debug("%s: revenue_growth regex fallback failed: %s", symbol, e)

            # ── Promoter Shareholding ──────────────────────────────────────
            promoter        = 0.0
            promoter_stable = True
            try:
                sh_section = soup.find("section", {"id": "shareholding"})
                if sh_section:
                    for row in sh_section.select("table tbody tr"):
                        cols = row.select("td")
                        if not cols or "Promoters" not in cols[0].text:
                            continue
                        values = []
                        for c in cols[1:]:
                            try:
                                values.append(
                                    float(c.text.strip().replace("%", "").replace(",", ""))
                                )
                            except ValueError:
                                pass
                        if values:
                            promoter = values[-1]
                            # FIX: use QoQ change instead of latest-vs-oldest
                            # Latest-vs-oldest missed mid-period dips (e.g. pledging events)
                            # A >2pp drop in the most recent quarter is a warning sign
                            if len(values) >= 2:
                                promoter_stable = abs(values[-1] - values[-2]) < 2.0
                        break
            except Exception as e:
                logger.debug("%s: promoter shareholding parse failed: %s", symbol, e)

            # ── Quarterly Profit + EPS ─────────────────────────────────────
            profit_3q      = False
            eps_increasing = False
            try:
                for row in soup.select("#quarters table tbody tr"):
                    cols  = row.select("td")
                    if not cols:
                        continue
                    label = cols[0].text.strip()

                    if "Net Profit" in label:
                        vals = []
                        for c in cols[1:]:
                            try:
                                vals.append(parse_number(c.text))
                            except ValueError:
                                pass
                        if len(vals) >= 3:
                            profit_3q = all(v > 0 for v in vals[-3:])

                    if "EPS" in label:
                        vals = []
                        for c in cols[1:]:
                            try:
                                vals.append(parse_number(c.text))
                            except ValueError:
                                pass
                        if len(vals) >= 3:
                            last3          = vals[-3:]
                            eps_increasing = last3[2] > last3[1] > last3[0]
            except Exception as e:
                logger.debug("%s: quarterly profit/EPS parse failed: %s", symbol, e)

            # ── IPO Year ───────────────────────────────────────────────────
            # FIX: default None instead of 2020 — 2020 was silently skewing
            # any age-based filter that used this field
            ipo_year: int | None = None
            try:
                about = soup.find("div", {"id": "about"})
                if about:
                    text  = about.get_text()
                    match = re.search(r'listed.*?(\d{4})', text, re.IGNORECASE)
                    if match:
                        ipo_year = int(match.group(1))
            except Exception as e:
                logger.debug("%s: ipo_year parse failed: %s", symbol, e)

            # ── Operating Cash Flow ────────────────────────────────────────
            # FIX: renamed cashflow_5q → cashflow_5y because Screener's
            # #cash-flow section shows ANNUAL data, not quarterly.
            # Checking vals[-5:] gives the last 5 years, not 5 quarters.
            cashflow_5y = False
            try:
                for row in soup.select("#cash-flow table tbody tr"):
                    if "Operating" not in row.text:
                        continue
                    cols = row.select("td")
                    vals = []
                    for c in cols[1:]:
                        try:
                            vals.append(parse_number(c.text))
                        except ValueError:
                            pass
                    if len(vals) >= 5:
                        cashflow_5y = all(v > 0 for v in vals[-5:])
                    break
            except Exception as e:
                logger.debug("%s: cashflow parse failed: %s", symbol, e)

            return {
                "symbol":            symbol,
                "mcap":              mcap,
                "pe":                pe,
                "roe":               roe,
                "debt_eq":           debt_eq,
                "revenue_growth":    revenue_growth,
                "promoter":          promoter,
                "promoter_stable":   promoter_stable,
                "profit_3q":         profit_3q,
                "eps_increasing":    eps_increasing,
                "cashflow_5y":       cashflow_5y,   # FIX: was cashflow_5q
                "ipo_year":          ipo_year,       # FIX: None if unparseable
                "used_consolidated": used_consolidated,
                "error":             None,
            }

    except Exception as e:
        logger.exception("get_fundamentals failed for %s", symbol)
        return {"symbol": symbol, "error": str(e)}