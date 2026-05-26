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
    gain  = delta.where(delta > 0, 0).rolling(period).mean()
    loss  = -delta.where(delta < 0, 0).rolling(period).mean()
    rs    = gain / loss
    rsi   = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)

# ── TIER 2 INDICATORS ─────────────────────────────────────────────────────────

def calc_macd_crossover(closes: pd.Series) -> bool:
    """True if MACD line crossed above signal line in the last candle."""
    exp12  = closes.ewm(span=12, adjust=False).mean()
    exp26  = closes.ewm(span=26, adjust=False).mean()
    macd   = exp12 - exp26
    signal = macd.ewm(span=9, adjust=False).mean()
    return bool(macd.iloc[-2] <= signal.iloc[-2] and macd.iloc[-1] > signal.iloc[-1])

def calc_new_3m_high(df: pd.DataFrame) -> bool:
    """True if CMP is at or above the 3-month (63-day) high."""
    high_3m = df["high"].tail(63).max()
    return bool(df["close"].iloc[-1] >= high_3m)

def calc_golden_cross(closes: pd.Series) -> bool:
    """True if 50 DMA just crossed above 200 DMA (within last 5 candles)."""
    ma50  = closes.rolling(50).mean()
    ma200 = closes.rolling(200).mean()
    for i in range(-5, -1):
        if ma50.iloc[i-1] <= ma200.iloc[i-1] and ma50.iloc[i] > ma200.iloc[i]:
            return True
    return False

def calc_atr_pct(df: pd.DataFrame, period: int = 14) -> float:
    """ATR as a % of CMP over last N candles."""
    high_low = df["high"] - df["low"]
    atr      = high_low.tail(period).mean()
    cmp      = df["close"].iloc[-1]
    return round(float(atr / cmp * 100), 2)

def calc_bb_squeeze(closes: pd.Series, period: int = 20, threshold: float = 0.10) -> bool:
    """True if Bollinger Band width is below threshold (bands tightening)."""
    ma    = closes.rolling(period).mean()
    std   = closes.rolling(period).std()
    upper = ma + 2 * std
    lower = ma - 2 * std
    bw    = (upper - lower) / ma
    return bool(bw.iloc[-1] < threshold)

def calc_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> dict:
    """
    Supertrend indicator.
    Returns: signal ('BUY' or 'SELL'), current supertrend value, and how many days in current signal.
    """
    high  = df["high"]
    low   = df["low"]
    close = df["close"]

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()

    hl_avg     = (high + low) / 2
    upper_band = hl_avg + (multiplier * atr)
    lower_band = hl_avg - (multiplier * atr)

    final_upper = upper_band.copy()
    final_lower = lower_band.copy()

    for i in range(1, len(df)):
        final_upper.iloc[i] = (
            upper_band.iloc[i]
            if upper_band.iloc[i] < final_upper.iloc[i - 1] or close.iloc[i - 1] > final_upper.iloc[i - 1]
            else final_upper.iloc[i - 1]
        )
        final_lower.iloc[i] = (
            lower_band.iloc[i]
            if lower_band.iloc[i] > final_lower.iloc[i - 1] or close.iloc[i - 1] < final_lower.iloc[i - 1]
            else final_lower.iloc[i - 1]
        )

    supertrend = pd.Series(index=df.index, dtype=float)
    signal     = pd.Series(index=df.index, dtype=str)

    for i in range(1, len(df)):
        if close.iloc[i] > final_upper.iloc[i - 1]:
            supertrend.iloc[i] = final_lower.iloc[i]
            signal.iloc[i]     = "BUY"
        elif close.iloc[i] < final_lower.iloc[i - 1]:
            supertrend.iloc[i] = final_upper.iloc[i]
            signal.iloc[i]     = "SELL"
        else:
            supertrend.iloc[i] = supertrend.iloc[i - 1]
            signal.iloc[i]     = signal.iloc[i - 1]

    current_signal = signal.iloc[-1]
    days_in_signal = 0
    for s in reversed(signal.tolist()):
        if s == current_signal:
            days_in_signal += 1
        else:
            break

    return {
        "supertrend_signal": current_signal,
        "supertrend_value":  round(float(supertrend.iloc[-1]), 2),
        "supertrend_buy":    current_signal == "BUY",
        "supertrend_days":   days_in_signal,
    }

def calc_adx(df: pd.DataFrame, period: int = 14) -> dict:
    """
    ADX (Average Directional Index)
    > 25 = strong trend (tradeable)
    > 40 = very strong trend
    < 20 = weak/choppy, avoid
    """
    high  = df["high"]
    low   = df["low"]
    close = df["close"]

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)

    up   = high - high.shift()
    down = low.shift() - low

    plus_dm  = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)

    atr_s    = tr.ewm(span=period).mean()
    plus_di  = 100 * plus_dm.ewm(span=period).mean() / atr_s
    minus_di = 100 * minus_dm.ewm(span=period).mean() / atr_s

    dx  = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).fillna(0)
    adx = dx.ewm(span=period).mean()

    current_adx = round(float(adx.iloc[-1]), 2)

    return {
        "adx":             current_adx,
        "adx_strong":      bool(current_adx >= 25),
        "adx_very_strong": bool(current_adx >= 40),
        "plus_di":         round(float(plus_di.iloc[-1]), 2),
        "minus_di":        round(float(minus_di.iloc[-1]), 2),
        "adx_bullish":     bool(current_adx >= 25 and float(plus_di.iloc[-1]) > float(minus_di.iloc[-1])),
    }

# ── MAIN FETCH ─────────────────────────────────────────────────────────────────

def get_technical_data(kite: KiteConnect, instrument_token: int, symbol: str,
                       nifty_1m_return: float = None) -> dict:
    try:
        to_date   = datetime.now()
        from_date = to_date - timedelta(days=365)

        hist = kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_date.strftime("%Y-%m-%d"),
            to_date=to_date.strftime("%Y-%m-%d"),
            interval="day"
        )

        df      = pd.DataFrame(hist)
        closes  = df["close"]
        volumes = df["volume"]

        # ── existing indicators ──────────────────────────────────────────────
        dma20  = round(float(closes.tail(20).mean()), 2)
        dma50  = round(float(closes.tail(50).mean()), 2)
        dma200 = round(float(closes.tail(200).mean()), 2)
        cmp    = round(float(closes.iloc[-1]), 2)
        rsi    = calc_rsi(closes)

        avg_vol_20    = volumes.tail(20).mean()
        last_vol      = volumes.iloc[-1]
        vol_above_avg = bool(last_vol > avg_vol_20)

        # ── tier 2 indicators ───────────────────────────────────────────────
        macd_crossover  = calc_macd_crossover(closes)
        new_3m_high     = calc_new_3m_high(df)
        golden_cross    = calc_golden_cross(closes)
        atr_pct         = calc_atr_pct(df)
        bb_squeeze      = calc_bb_squeeze(closes)
        st              = calc_supertrend(df)
        adx_data        = calc_adx(df)

        stock_1m_return = round(float((closes.iloc[-1] / closes.iloc[-21] - 1) * 100), 2)
        rs_vs_nifty     = bool(nifty_1m_return is not None and stock_1m_return > nifty_1m_return)

        return {
            # existing
            "symbol":            symbol,
            "cmp":               cmp,
            "dma20":             dma20,
            "dma50":             dma50,
            "dma200":            dma200,
            "rsi":               rsi,
            "vol_above_avg":     vol_above_avg,
            "high52w":           round(float(df["high"].tail(252).max()), 2),
            "low52w":            round(float(df["low"].tail(252).min()), 2),
            # tier 2
            "macd_crossover":    macd_crossover,
            "new_3m_high":       new_3m_high,
            "golden_cross":      golden_cross,
            "atr_pct":           atr_pct,
            "low_atr":           bool(atr_pct < 3.0),
            "bb_squeeze":        bb_squeeze,
            "rs_vs_nifty":       rs_vs_nifty,
            "stock_1m_return":   stock_1m_return,
            "supertrend_signal": st["supertrend_signal"],
            "supertrend_value":  st["supertrend_value"],
            "supertrend_buy":    st["supertrend_buy"],
            "supertrend_days":   st["supertrend_days"],
            "adx":               adx_data["adx"],
            "adx_strong":        adx_data["adx_strong"],
            "adx_very_strong":   adx_data["adx_very_strong"],
            "plus_di":           adx_data["plus_di"],
            "minus_di":          adx_data["minus_di"],
            "adx_bullish":       adx_data["adx_bullish"],
            "error":             None,
        }

    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


def get_nifty_1m_return(kite: KiteConnect) -> float:
    """Fetch Nifty 50 1-month return to use for RS comparison."""
    try:
        to_date   = datetime.now()
        from_date = to_date - timedelta(days=40)
        hist      = kite.historical_data(
            instrument_token=256265,
            from_date=from_date.strftime("%Y-%m-%d"),
            to_date=to_date.strftime("%Y-%m-%d"),
            interval="day"
        )
        closes = pd.DataFrame(hist)["close"]
        return round(float((closes.iloc[-1] / closes.iloc[-21] - 1) * 100), 2)
    except:
        return 0.0


def get_all_nse_instruments(kite: KiteConnect) -> list:
    instruments = kite.instruments("NSE")
    return [i for i in instruments if i["segment"] == "NSE"]