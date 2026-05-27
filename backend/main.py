import os
import json
import asyncio
import logging
from datetime import datetime, timedelta

import pandas as pd
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from fetchers.screener import get_fundamentals
from fetchers.trendlyne import get_analyst_data
from fetchers.kite import (
    get_kite_client,
    get_technical_data,
    get_nifty_1m_return,
    get_all_nse_instruments,
)

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(title="EquiScan Pro API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Load universe ──────────────────────────────────────────────────────────────

with open("universe.json", "r") as f:
    UNIVERSE = json.load(f)

SYMBOLS     = [s["symbol"] for s in UNIVERSE]
SYMBOL_META = {s["symbol"]: s for s in UNIVERSE}

# ── In-memory stock cache ──────────────────────────────────────────────────────

stock_cache: dict = {}

# FIX: guard flag to prevent concurrent daily_refresh runs
_refresh_running: bool = False


def load_cache_from_disk() -> None:
    """
    Load stock_data.json into memory on startup.
    FIX: distinguishes file-not-found from JSON parse errors so a corrupted
         cache file doesn't silently wipe good data on the next refresh.
    """
    try:
        with open("stock_data.json", "r") as f:
            data = json.load(f)
        stock_cache.update(data)
        logger.info("Loaded %d stocks from disk cache", len(stock_cache))
    except FileNotFoundError:
        logger.info("No disk cache found — will fetch on first run")
    except json.JSONDecodeError as e:
        # FIX: don't silently swallow a corrupted file — log and abort so the
        # existing file is NOT overwritten by an empty cache on next refresh.
        logger.error(
            "stock_data.json is corrupted and could not be parsed: %s — "
            "fix or delete the file manually before restarting", e
        )
        raise


# ── Scheduler ─────────────────────────────────────────────────────────────────

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


async def fetch_one(
    symbol:          str,
    kite=None,
    instrument_map:  dict        = None,
    nifty_1m_return: float | None = None,
) -> dict:
    meta = SYMBOL_META.get(symbol, {})
    try:
        fund = await get_fundamentals(symbol)
        anal = await get_analyst_data(symbol)

        tech = {}
        if kite and instrument_map and symbol in instrument_map:
            token = instrument_map[symbol]
            tech  = await asyncio.to_thread(
                get_technical_data, kite, token, symbol, nifty_1m_return
            )
            tech.pop("error", None)

        trendlyne_err = anal.pop("error", None) if isinstance(anal, dict) else None

        return {
            "symbol":               symbol,
            "name":                 meta.get("name", symbol),
            "sector":               meta.get("sector", "Unknown"),
            "index":                meta.get("index", ""),
            **fund,
            **anal,
            **tech,
            # FIX: explicitly flag whether Trendlyne data is present so
            # consumers know when analyst fields may be missing
            "trendlyne_available": trendlyne_err is None,
            "last_updated":        datetime.now().isoformat(),
        }
    except Exception as e:
        logger.exception("fetch_one failed for %s", symbol)
        return {"symbol": symbol, "error": str(e)}


async def daily_refresh() -> None:
    global _refresh_running

    # FIX: prevent two concurrent refresh tasks writing to cache/disk
    if _refresh_running:
        logger.warning("daily_refresh already running — skipping duplicate trigger")
        return

    _refresh_running = True
    logger.info("Starting daily refresh for %d stocks", len(SYMBOLS))
    success    = 0
    batch_size = 5

    # Initialise Kite once for the whole run
    kite           = None
    instrument_map = {}
    nifty_ret      = None
    try:
        kite           = get_kite_client()
        all_inst       = get_all_nse_instruments(kite)
        instrument_map = {
            i["tradingsymbol"]: i["instrument_token"]
            for i in all_inst
            if i["instrument_type"] == "EQ"
        }
        nifty_ret = await asyncio.to_thread(get_nifty_1m_return, kite)
        logger.info("Nifty 1M return: %s%%", nifty_ret)
    except Exception as e:
        logger.error("Kite init failed — technical data will be skipped: %s", e)

    try:
        for i in range(0, len(SYMBOLS), batch_size):
            batch   = SYMBOLS[i:i + batch_size]
            tasks   = [
                fetch_one(
                    sym,
                    kite=kite,
                    instrument_map=instrument_map,
                    nifty_1m_return=nifty_ret,
                )
                for sym in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for sym, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.error("fetch_one raised exception for %s: %s", sym, result)
                    continue
                err = result.get("error", "")
                if not err or "Trendlyne" in str(err):
                    stock_cache[sym] = result
                    success += 1

            await asyncio.sleep(2)

        with open("stock_data.json", "w") as f:
            json.dump(stock_cache, f)

        logger.info("Daily refresh complete — %d/%d stocks updated", success, len(SYMBOLS))

    finally:
        _refresh_running = False


# Schedule: every weekday at 6:30 AM IST
scheduler.add_job(
    daily_refresh,
    "cron",
    day_of_week="mon-fri",
    hour=6,
    minute=30,
    id="daily_refresh",
)


# ── Startup / Shutdown ────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup() -> None:
    load_cache_from_disk()
    scheduler.start()
    logger.info("Scheduler started — daily refresh at 6:30 AM IST (Mon-Fri)")


@app.on_event("shutdown")
async def shutdown() -> None:
    scheduler.shutdown()


# ── Core routes ───────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "EquiScan Pro API running"}


@app.get("/api/health")
def health():
    next_run = None
    job = scheduler.get_job("daily_refresh")
    if job and job.next_run_time:
        next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S %Z")
    return {
        "status":               "ok",
        "refresh_running":      _refresh_running,
        "kite_configured":      os.getenv("KITE_API_KEY", "") not in ("", "your_kite_api_key_here"),
        "screener_configured":  os.getenv("SCREENER_SESSION", "") not in ("", "your_screener_session_cookie_here"),
        "trendlyne_configured": os.getenv("TRENDLYNE_TOKEN", "") not in ("", "your_trendlyne_token_here"),
        "cached_stocks":        len(stock_cache),
        "next_refresh":         next_run,
    }


@app.get("/api/refresh")
async def manual_refresh():
    # FIX: return 409 instead of spawning a second concurrent refresh task
    if _refresh_running:
        raise HTTPException(status_code=409, detail="Refresh already in progress")
    asyncio.create_task(daily_refresh())
    return {"status": "Refresh started in background"}


@app.get("/api/stocks")
def get_stocks(
    limit:  int = Query(default=50),
    offset: int = Query(default=0),
):
    stocks = list(stock_cache.values())
    return {
        "stocks": stocks[offset:offset + limit],
        "total":  len(stocks),
        "cached": len(stock_cache),
    }


@app.get("/api/screen")
async def screen(
    symbols:   str  = Query(default=""),
    use_cache: bool = Query(default=True),
):
    if symbols:
        sym_list = [s.strip().upper() for s in symbols.split(",")]
    else:
        sym_list = SYMBOLS

    # FIX: on-demand fetches now get Nifty benchmark so rs_vs_nifty is
    # consistent with cached data instead of always being None
    kite      = None
    nifty_ret = None
    instrument_map: dict = {}
    needs_live = any(sym not in stock_cache for sym in sym_list) if use_cache else True
    if needs_live:
        try:
            kite      = get_kite_client()
            all_inst  = get_all_nse_instruments(kite)
            instrument_map = {
                i["tradingsymbol"]: i["instrument_token"]
                for i in all_inst
                if i["instrument_type"] == "EQ"
            }
            nifty_ret = await asyncio.to_thread(get_nifty_1m_return, kite)
        except Exception as e:
            logger.warning("Kite init failed in /api/screen: %s", e)

    results = []
    for sym in sym_list:
        if use_cache and sym in stock_cache:
            results.append(stock_cache[sym])
        else:
            data = await fetch_one(
                sym,
                kite=kite,
                instrument_map=instrument_map,
                nifty_1m_return=nifty_ret,
            )
            if not data.get("error") or "Trendlyne" in str(data.get("error", "")):
                stock_cache[sym] = data
                results.append(data)

    return {"results": results, "count": len(results)}


# ── Tier 2 filter ─────────────────────────────────────────────────────────────

@app.get("/api/screen/filter")
def screen_filter(
    min_roe:        float = Query(default=0),
    max_pe:         float = Query(default=9999),
    macd_crossover: bool  = Query(default=False),
    new_3m_high:    bool  = Query(default=False),
    golden_cross:   bool  = Query(default=False),
    rs_vs_nifty:    bool  = Query(default=False),
    low_atr:        bool  = Query(default=False),
    bb_squeeze:     bool  = Query(default=False),
    supertrend_buy: bool  = Query(default=False),
    adx_bullish:    bool  = Query(default=False),
):
    results = []
    for stock in stock_cache.values():
        if stock.get("error"):
            continue
        if stock.get("roe", 0) < min_roe:
            continue
        if max_pe < 9999 and (stock.get("pe") or 9999) > max_pe:
            continue
        if macd_crossover and not stock.get("macd_crossover"):
            continue
        if new_3m_high    and not stock.get("new_3m_high"):
            continue
        if golden_cross   and not stock.get("golden_cross"):
            continue
        # FIX: rs_vs_nifty can be None (benchmark unavailable) — only pass
        # stocks where it is explicitly True, not just truthy/non-None
        if rs_vs_nifty    and stock.get("rs_vs_nifty") is not True:
            continue
        if low_atr        and not stock.get("low_atr"):
            continue
        if bb_squeeze     and not stock.get("bb_squeeze"):
            continue
        if supertrend_buy and not stock.get("supertrend_buy"):
            continue
        # FIX: was "adxBullish" (camelCase) — key in cache is "adx_bullish"
        if adx_bullish    and not stock.get("adx_bullish"):
            continue
        results.append(stock)

    return {"results": results, "count": len(results)}


# ── Per-stock routes ──────────────────────────────────────────────────────────

@app.get("/api/stock/{symbol}/fundamentals")
async def stock_fundamentals(symbol: str):
    sym = symbol.upper()
    if sym in stock_cache:
        return stock_cache[sym]
    return await get_fundamentals(sym)


@app.get("/api/stock/{symbol}/technical")
async def stock_technical(symbol: str):
    try:
        kite        = get_kite_client()
        instruments = kite.instruments("NSE")
        match = next(
            (i for i in instruments
             if i["tradingsymbol"] == symbol.upper()
             and i["instrument_type"] == "EQ"),
            None,
        )
        if not match:
            return {"error": f"{symbol} not found"}
        nifty_ret = await asyncio.to_thread(get_nifty_1m_return, kite)
        return await asyncio.to_thread(
            get_technical_data, kite, match["instrument_token"], symbol.upper(), nifty_ret
        )
    except Exception as e:
        logger.exception("stock_technical failed for %s", symbol)
        return {"error": str(e)}


@app.get("/api/stock/{symbol}/quant")
async def stock_quant(symbol: str):
    """
    Run the full quant signal engine on fresh data for a single stock.
    FIX: fetch window increased from 400 to 500 days to match kite.py
         and guarantee sufficient rows for 200 DMA and 12M momentum.
    """
    try:
        from fetchers.quant import generate_quant_signal

        kite        = get_kite_client()
        instruments = kite.instruments("NSE")
        match = next(
            (i for i in instruments
             if i["tradingsymbol"] == symbol.upper()
             and i["instrument_type"] == "EQ"),
            None,
        )
        if not match:
            return {"error": f"{symbol} not found"}

        to_date   = datetime.now()
        from_date = to_date - timedelta(days=500)   # FIX: was 400
        hist = await asyncio.to_thread(
            kite.historical_data,
            match["instrument_token"],
            from_date.strftime("%Y-%m-%d"),
            to_date.strftime("%Y-%m-%d"),
            "day",
        )
        df     = pd.DataFrame(hist)
        result = generate_quant_signal(df["close"], df["volume"], df)
        return {"symbol": symbol.upper(), **result}

    except Exception as e:
        logger.exception("stock_quant failed for %s", symbol)
        return {"error": str(e)}


@app.get("/api/stock/{symbol}/history")
async def stock_history(symbol: str, days: int = Query(default=365)):
    try:
        kite        = get_kite_client()
        instruments = kite.instruments("NSE")
        match = next(
            (i for i in instruments
             if i["tradingsymbol"] == symbol.upper()
             and i["instrument_type"] == "EQ"),
            None,
        )
        if not match:
            return {"error": f"{symbol} not found"}

        to_date   = datetime.now()
        from_date = to_date - timedelta(days=days)
        hist = await asyncio.to_thread(
            kite.historical_data,
            match["instrument_token"],
            from_date.strftime("%Y-%m-%d"),
            to_date.strftime("%Y-%m-%d"),
            "day",
        )
        return {
            "symbol": symbol.upper(),
            "data": [
                {
                    "date":   h["date"].strftime("%Y-%m-%d"),
                    "open":   h["open"],
                    "high":   h["high"],
                    "low":    h["low"],
                    "close":  h["close"],
                    "volume": h["volume"],
                }
                for h in hist
            ],
        }
    except Exception as e:
        logger.exception("stock_history failed for %s", symbol)
        return {"error": str(e)}


@app.get("/api/stock/{symbol}/volume")
async def stock_volume(symbol: str):
    try:
        kite        = get_kite_client()
        instruments = kite.instruments("NSE")
        match = next(
            (i for i in instruments
             if i["tradingsymbol"] == symbol.upper()
             and i["instrument_type"] == "EQ"),
            None,
        )
        if not match:
            return {"error": f"{symbol} not found"}

        to_date   = datetime.now()
        from_date = to_date - timedelta(days=60)
        hist = await asyncio.to_thread(
            kite.historical_data,
            match["instrument_token"],
            from_date.strftime("%Y-%m-%d"),
            to_date.strftime("%Y-%m-%d"),
            "day",
        )
        volumes    = [h["volume"] for h in hist]
        avg_vol_20 = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else 0
        last_vol   = volumes[-1] if volumes else 0
        vol_ratio  = round(last_vol / avg_vol_20, 2) if avg_vol_20 > 0 else 0

        return {
            "symbol":        symbol.upper(),
            "last_volume":   last_vol,
            "avg_volume_20": round(avg_vol_20),
            "vol_ratio":     vol_ratio,
            "spike":         vol_ratio >= 2.0,
            "spike_level":   (
                "extreme" if vol_ratio >= 3
                else "high" if vol_ratio >= 2
                else "normal"
            ),
            "data": [
                {"date": h["date"].strftime("%Y-%m-%d"), "volume": h["volume"]}
                for h in hist[-30:]
            ],
        }
    except Exception as e:
        logger.exception("stock_volume failed for %s", symbol)
        return {"error": str(e)}


@app.get("/api/nifty/history")
async def nifty_history(days: int = Query(default=365)):
    try:
        kite      = get_kite_client()
        to_date   = datetime.now()
        from_date = to_date - timedelta(days=days)
        hist = await asyncio.to_thread(
            kite.historical_data,
            256265,
            from_date.strftime("%Y-%m-%d"),
            to_date.strftime("%Y-%m-%d"),
            "day",
        )
        return {
            "data": [
                {"date": h["date"].strftime("%Y-%m-%d"), "close": h["close"]}
                for h in hist
            ]
        }
    except Exception as e:
        logger.exception("nifty_history failed")
        return {"error": str(e)}


# ── Market data routes ────────────────────────────────────────────────────────

@app.get("/api/market/fii-dii")
async def fii_dii():
    from fetchers.nse import get_fii_dii_data
    return await get_fii_dii_data()


@app.get("/api/market/bulk-deals")
async def bulk_deals():
    from fetchers.nse import get_bulk_deals
    return await get_bulk_deals()


@app.get("/api/stock/{symbol}/shareholding")
async def stock_shareholding(symbol: str):
    from fetchers.nse import get_stock_shareholding
    return await get_stock_shareholding(symbol.upper())


@app.get("/api/stock/{symbol}/analyst-tt")
async def stock_analyst_tickertape(symbol: str):
    from fetchers.tickertape import get_analyst_rating
    return await get_analyst_rating(symbol.upper())


# ── Universe routes ───────────────────────────────────────────────────────────

@app.get("/api/universe")
def get_universe():
    return {"stocks": UNIVERSE, "count": len(UNIVERSE)}


@app.get("/api/universe/symbols")
def get_symbols():
    return {"symbols": SYMBOLS, "count": len(SYMBOLS)}


@app.get("/api/instruments/search")
def search_instruments(q: str = Query(default="MANKIND")):
    try:
        kite        = get_kite_client()
        instruments = kite.instruments("NSE")
        results     = [i for i in instruments if q.upper() in i["tradingsymbol"]][:10]
        return {"results": results}
    except Exception as e:
        logger.exception("search_instruments failed")
        return {"error": str(e)}


# ── Debug routes — only available when DEBUG_MODE=true in .env ────────────────
# FIX: all debug endpoints gated behind DEBUG_MODE env flag so they are
#      never exposed in production. They were previously always-on, leaking
#      the Screener session cookie path to anyone who knew the URL.

_DEBUG = os.getenv("DEBUG_MODE", "false").lower() == "true"


def _require_debug():
    if not _DEBUG:
        raise HTTPException(status_code=404, detail="Not found")


@app.get("/api/stock/{symbol}/debug")
async def stock_debug(symbol: str):
    _require_debug()
    import httpx
    from bs4 import BeautifulSoup
    session = os.getenv("SCREENER_SESSION", "")
    headers = {"Cookie": f"sessionid={session}", "User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=20) as client:
        r    = await client.get(
            f"https://www.screener.in/company/{symbol.upper()}/consolidated/",
            headers=headers,
        )
        soup   = BeautifulSoup(r.text, "html.parser")
        ratios = {}
        for li in soup.select("#top-ratios li"):
            name  = li.select_one(".name")
            value = li.select_one(".number")
            if name and value:
                ratios[name.text.strip()] = value.text.strip()
    return {"ratios": ratios}


@app.get("/api/stock/{symbol}/debug2")
async def stock_debug2(symbol: str):
    _require_debug()
    import httpx
    from bs4 import BeautifulSoup
    session = os.getenv("SCREENER_SESSION", "")
    headers = {"Cookie": f"sessionid={session}", "User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=20) as client:
        r    = await client.get(
            f"https://www.screener.in/company/{symbol.upper()}/",
            headers=headers,
        )
        soup   = BeautifulSoup(r.text, "html.parser")
        ratios = {}
        for li in soup.select("#top-ratios li"):
            name  = li.select_one(".name")
            value = li.select_one(".number")
            if name and value:
                ratios[name.text.strip()] = value.text.strip()
    return {"ratios": ratios}


@app.get("/api/stock/{symbol}/debug3")
async def stock_debug3(symbol: str):
    _require_debug()
    import httpx
    from bs4 import BeautifulSoup
    session = os.getenv("SCREENER_SESSION", "")
    headers = {"Cookie": f"sessionid={session}", "User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=20) as client:
        r      = await client.get(
            f"https://www.screener.in/company/{symbol.upper()}/consolidated/",
            headers=headers,
        )
        soup   = BeautifulSoup(r.text, "html.parser")
        bs_sec = soup.find("section", {"id": "balance-sheet"})
        rows   = []
        if bs_sec:
            for row in bs_sec.select("tr")[:15]:
                cols = row.select("td")
                if cols:
                    rows.append([c.text.strip() for c in cols[:3]])
    return {"rows": rows}


@app.get("/api/debug/tickertape/{symbol}")
async def debug_tickertape(symbol: str):
    _require_debug()
    import httpx
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.tickertape.in/",
    }
    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
        r = await client.get(
            f"https://api.tickertape.in/stocks/search?text={symbol}&count=3"
        )
        return {"status": r.status_code, "data": r.text[:500]}


@app.get("/api/debug/tickertape2/{sid}")
async def debug_tickertape2(sid: str):
    _require_debug()
    import httpx
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.tickertape.in/",
    }
    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
        r = await client.get(f"https://api.tickertape.in/stocks/forecast/{sid}")
        return {"status": r.status_code, "data": r.text[:500]}


@app.get("/api/debug/tickertape3/{sid}")
async def debug_tickertape3(sid: str):
    _require_debug()
    import httpx
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.tickertape.in/",
    }
    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
        urls = [
            f"https://api.tickertape.in/stocks/{sid}/forecast",
            f"https://api.tickertape.in/stocks/{sid}/analysts",
            f"https://api.tickertape.in/stocks/{sid}/recommendations",
            f"https://api.tickertape.in/analyst-ratings?sid={sid}",
        ]
        results = {}
        for url in urls:
            r = await client.get(url)
            results[url] = {"status": r.status_code, "data": r.text[:200]}
        return results


@app.get("/api/debug/screener-analyst/{symbol}")
async def debug_screener_analyst(symbol: str):
    _require_debug()
    import httpx
    from bs4 import BeautifulSoup
    session = os.getenv("SCREENER_SESSION", "")
    headers = {"Cookie": f"sessionid={session}", "User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=20) as client:
        r    = await client.get(
            f"https://www.screener.in/company/{symbol}/",
            headers=headers,
        )
        soup    = BeautifulSoup(r.text, "html.parser")
        results = {}
        for section in soup.find_all("section"):
            sid = section.get("id", "")
            h2  = section.find("h2")
            if h2:
                results[sid or h2.text.strip()] = h2.text.strip()
        return {"sections": results}


@app.get("/api/debug/screener-insights/{symbol}")
async def debug_screener_insights(symbol: str):
    _require_debug()
    import httpx
    from bs4 import BeautifulSoup
    session = os.getenv("SCREENER_SESSION", "")
    headers = {"Cookie": f"sessionid={session}", "User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=20) as client:
        r        = await client.get(
            f"https://www.screener.in/company/{symbol}/",
            headers=headers,
        )
        soup     = BeautifulSoup(r.text, "html.parser")
        insights = soup.find("section", {"id": "insights"})
        if insights:
            return {"text": insights.get_text(separator="\n", strip=True)[:1000]}
        return {"error": "No insights section found"}


@app.get("/api/debug/groww/{symbol}")
async def debug_groww(symbol: str):
    _require_debug()
    import httpx
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
        r = await client.get(
            f"https://groww.in/v1/api/stocks_data/v1/accord_fintech/company/search/nse/{symbol}"
        )
        return {"status": r.status_code, "data": r.text[:500]}


@app.get("/api/debug/groww2/{symbol}")
async def debug_groww2(symbol: str):
    _require_debug()
    import httpx
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept":     "application/json",
        "origin":     "https://groww.in",
        "referer":    "https://groww.in/",
    }
    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
        urls = [
            f"https://groww.in/v1/api/stocks_data/v1/tr_live_data/exchange/NSE/segment/CASH/{symbol}/overview",
            f"https://groww.in/v1/api/stocks_data/v2/tr_live_data/exchange/NSE/segment/CASH/{symbol}/overview",
            f"https://groww.in/v1/api/stocks_data/v1/company/search?q={symbol}",
        ]
        results = {}
        for url in urls:
            try:
                r = await client.get(url)
                results[url.split("/")[-1]] = {
                    "status": r.status_code,
                    "data":   r.text[:300],
                }
            except Exception as e:
                results[url.split("/")[-1]] = {"error": str(e)}
        return results