import os
from datetime import datetime, timedelta
import pandas as pd
from kiteconnect import KiteConnect

def get_kite_client():
    kite = KiteConnect(api_key=os.getenv("KITE_API_KEY"))
    kite.set_access_token(os.getenv("KITE_ACCESS_TOKEN"))
    return kite

def calc_rsi(prices: pd.Series, period: int = 14) -> float:
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)

def get_technical_data(kite: KiteConnect, instrument_token: int, symbol: str) -> dict:
    try:
        to_date = datetime.now()
        from_date = to_date - timedelta(days=300)

        hist = kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_date.strftime("%Y-%m-%d"),
            to_date=to_date.strftime("%Y-%m-%d"),
            interval="day"
        )

        df = pd.DataFrame(hist)
        closes = df["close"]
        volumes = df["volume"]

        dma20  = round(float(closes.tail(20).mean()), 2)
        dma50  = round(float(closes.tail(50).mean()), 2)
        dma200 = round(float(closes.tail(200).mean()), 2)
        cmp    = round(float(closes.iloc[-1]), 2)
        rsi    = calc_rsi(closes)

        avg_vol_20 = volumes.tail(20).mean()
        last_vol   = volumes.iloc[-1]
        vol_above_avg = bool(last_vol > avg_vol_20)

        return {
            "symbol":        symbol,
            "cmp":           cmp,
            "dma20":         dma20,
            "dma50":         dma50,
            "dma200":        dma200,
            "rsi":           rsi,
            "vol_above_avg": vol_above_avg,
            "high52w":       round(float(df["high"].tail(252).max()), 2),
            "low52w":        round(float(df["low"].tail(252).min()), 2),
            "error":         None
        }

    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

def get_all_nse_instruments(kite: KiteConnect) -> list:
    instruments = kite.instruments("NSE")
    return [i for i in instruments if i["segment"] == "NSE"]