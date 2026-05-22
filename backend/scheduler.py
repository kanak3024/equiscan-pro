import asyncio
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

with open("universe.json", "r") as f:
    UNIVERSE = json.load(f)

SYMBOLS     = [s["symbol"] for s in UNIVERSE]
SYMBOL_META = {s["symbol"]: s for s in UNIVERSE}

stock_db: dict = {}

NSE_IPO_YEARS = {
    "MANKIND": 2023, "KAYNES": 2022, "EMARTIND": 2022, "APTUS": 2021,
    "LATENTVIEW": 2021, "ROLEX": 2021, "HARSHA": 2022, "VENUS": 2022,
    "AMI": 2021, "DEVYANI": 2021, "NAZARA": 2021, "FUSION": 2022,
    "WAAREE": 2024, "SYRMA": 2022, "GLOBALH": 2022, "VERITAS": 2019,
    "CLEAN": 2021, "360ONE": 2022, "ACMESOLAR": 2024, "AADHARHFC": 2024,
    "ANTHEM": 2024, "AFCONS": 2024, "OLAELEC": 2024, "HYUNDAI": 2024,
    "SWIGGY": 2024, "MEESHO": 2024, "LENSKART": 2024, "GROWW": 2024,
}

def get_ipo_year(symbol: str) -> int:
    return NSE_IPO_YEARS.get(symbol, 2015)

def get_quant_signal_sync(symbol: str, instruments: list) -> dict:
    from fetchers.kite import get_kite_client
    from fetchers.quant import generate_quant_signal
    import pandas as pd

    try:
        kite  = get_kite_client()
        match = next(
            (i for i in instruments
             if i["tradingsymbol"] == symbol
             and i["instrument_type"] == "EQ"),
            None
        )
        if not match:
            return {}

        to_date   = datetime.now()
        from_date = to_date - timedelta(days=400)

        hist = kite.historical_data(
            instrument_token=match["instrument_token"],
            from_date=from_date.strftime("%Y-%m-%d"),
            to_date=to_date.strftime("%Y-%m-%d"),
            interval="day"
        )
        df      = pd.DataFrame(hist)
        prices  = df["close"]
        volumes = df["volume"]
        return generate_quant_signal(prices, volumes, df)
    except Exception as e:
        return {"error": str(e)}

async def fetch_stock_data(symbol: str) -> dict:
    from fetchers.screener import get_fundamentals
    from fetchers.trendlyne import get_analyst_data
    meta = SYMBOL_META.get(symbol, {})
    try:
        fund = await get_fundamentals(symbol)
        anal = await get_analyst_data(symbol)

        ipo_year = fund.get("ipo_year", 2020)
        if ipo_year == 2020:
            ipo_year = get_ipo_year(symbol)

        return {
            "symbol":       symbol,
            "name":         meta.get("name", symbol),
            "sector":       meta.get("sector", "Unknown"),
            "index":        meta.get("index", ""),
            **fund,
            **anal,
            "ipo_year":     ipo_year,
            "last_updated": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

async def fetch_technical_data(symbol: str, instruments: list) -> dict:
    from fetchers.kite import get_kite_client, get_technical_data
    try:
        kite  = get_kite_client()
        match = next(
            (i for i in instruments
             if i["tradingsymbol"] == symbol
             and i["instrument_type"] == "EQ"),
            None
        )
        if not match:
            print(f"    [tech] {symbol} not found in instruments")
            return {}
        print(f"    [tech] {symbol} token={match['instrument_token']}")
        result = get_technical_data(kite, match["instrument_token"], symbol)
        print(f"    [tech] {symbol} dma20={result.get('dma20')} error={result.get('error')}")
        return result
    except Exception as e:
        print(f"    [tech] {symbol} exception: {e}")
        return {}

async def refresh_batch(symbols: list, batch_size: int = 5):
    total   = len(symbols)
    success = 0
    errors  = 0

    print(f"\n{'='*60}")
    print(f"Starting refresh for {total} stocks")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    print("Fetching Kite instruments list...")
    try:
        from fetchers.kite import get_kite_client
        kite        = get_kite_client()
        instruments = kite.instruments("NSE")
        print(f"Got {len(instruments)} instruments from Kite")
    except Exception as e:
        instruments = []
        print(f"Kite instruments failed: {e}")

    for i in range(0, total, batch_size):
        batch = symbols[i:i + batch_size]
        print(f"Batch {i//batch_size + 1}/{(total//batch_size)+1} — {batch}")

        fund_tasks   = [fetch_stock_data(sym) for sym in batch]
        fund_results = await asyncio.gather(*fund_tasks, return_exceptions=True)

        for sym, result in zip(batch, fund_results):
            if isinstance(result, Exception):
                errors += 1
                print(f"  ✗ {sym}: {result}")
                continue

            err = result.get("error", "")
            if err and "Trendlyne" not in str(err):
                errors += 1
                print(f"  ✗ {sym}: {err}")
                continue

            # Fetch technical data
            tech = await fetch_technical_data(sym, instruments)
            if tech and not tech.get("error"):
                result["dma20"]         = tech.get("dma20", 0)
                result["dma50"]         = tech.get("dma50", 0)
                result["dma200"]        = tech.get("dma200", 0)
                result["cmp"]           = tech.get("cmp", 0)
                result["rsi"]           = tech.get("rsi", 0)
                result["vol_above_avg"] = tech.get("vol_above_avg", False)
                result["high52w"]       = tech.get("high52w", 0)
                result["low52w"]        = tech.get("low52w", 0)

            # Run quant signal engine
            try:
                loop  = asyncio.get_event_loop()
                quant = await loop.run_in_executor(
                    None, lambda s=sym: get_quant_signal_sync(s, instruments)
                )
                if quant and not quant.get("error"):
                    result["analyst"]       = quant.get("signal", "Hold")
                    result["analyst_score"] = quant.get("score", 50)
                    result["quant_signals"] = quant.get("signals", [])
                    result["momentum"]      = quant.get("momentum", {})
                    result["macd"]          = quant.get("macd", {})
                    print(f"    [quant] {sym} signal={quant.get('signal')} score={quant.get('score')}")
            except Exception as qe:
                print(f"    [quant] {sym} error: {qe}")

            stock_db[sym] = result
            success += 1
            print(f"  ✓ {sym}: MCap={result.get('mcap',0)} DMA20={result.get('dma20',0)} Analyst={result.get('analyst','?')}")

        if i + batch_size < total:
            print(f"  Waiting 3s...")
            await asyncio.sleep(3)

    print(f"\n{'='*60}")
    print(f"Done! Success: {success} | Errors: {errors}")
    print(f"{'='*60}\n")

    # Merge with existing data
    try:
        with open("stock_data.json", "r") as f:
            existing = json.load(f)
        existing.update(stock_db)
        stock_db.update(existing)
    except:
        pass

    with open("stock_data.json", "w") as f:
        json.dump(stock_db, f)
    print(f"Saved {len(stock_db)} stocks to stock_data.json")

async def run_full_refresh():
    await refresh_batch(SYMBOLS, batch_size=5)

async def run_test_refresh():
    test_symbols = ["MANKIND", "ABB", "APTUS", "TATAPOWER", "INFY"]
    await refresh_batch(test_symbols, batch_size=5)

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "test"
    if mode == "full":
        print("Running FULL refresh for all 504 stocks...")
        asyncio.run(run_full_refresh())
    else:
        print("Running TEST refresh for 5 stocks...")
        asyncio.run(run_test_refresh())