import os
import logging
from datetime import datetime, timedelta

import pandas as pd
from kiteconnect import KiteConnect

# Import the canonical RSI (Wilder's EWM) from quant.py instead of duplicating it.
# FIX: removes the local calc_rsi copy that was still using the old simple rolling mean.
from quant import calc_rsi

logger = logging.getLogger(__name__)


# ── CLIENT ────────────────────────────────────────────────────────────────────

def get_kite_client() -> KiteConnect:
    kite = KiteConnect(api_key=os.getenv("KITE_API_KEY"))
    kite.set_access_token(os.getenv("KITE_ACCESS_TOKEN"))
    return kite


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
    """True if 50 DMA crossed above 200 DMA within the last 5 candles."""
    if len(closes) < 205:
        return False
    ma50  = closes.rolling(50).mean()
    ma200 = closes.rolling(200).mean()
    for i in range(-5, -1):
        if ma50.iloc[i - 1] <= ma200.iloc[i - 1] and ma50.iloc[i] > ma200.iloc[i]:
            return True
    return False


def calc_atr_pct(df: pd.DataFrame, period: int = 14) -> float:
    """
    ATR as % of CMP using proper True Range (H-L, |H-prevC|, |L-prevC|).
    FIX: was using only H-L, which underestimates ATR after gaps/circuits.
    """
    high  = df["high"]
    low   = df["low"]
    close = df["close"]

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)

    atr = tr.tail(period).mean()
    cmp = float(close.iloc[-1])
    return round(float(atr / cmp * 100), 2) if cmp > 0 else 0.0


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
    FIX: replaced .iloc[i] = with .iat[i] = for safe scalar assignment;
         .iloc[i] = triggers SettingWithCopyWarning and breaks in pandas 3.0+.
    Returns: signal ('BUY' or 'SELL'), current supertrend value, days in signal.
    """
    high  = df["high"]
    low   = df["low"]
    close = df["close"]

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)

    atr = tr.rolling(period).mean()

    hl_avg     = (high + low) / 2
    upper_band = hl_avg + (multiplier * atr)
    lower_band = hl_avg - (multiplier * atr)

    final_upper = upper_band.copy()
    final_lower = lower_band.copy()

    # FIX: use .iat[] for scalar assignment inside loops
    for i in range(1, len(df)):
        final_upper.iat[i] = (
            upper_band.iat[i]
            if upper_band.iat[i] < final_upper.iat[i - 1] or close.iat[i - 1] > final_upper.iat[i - 1]
            else final_upper.iat[i - 1]
        )
        final_lower.iat[i] = (
            lower_band.iat[i]
            if lower_band.iat[i] > final_lower.iat[i - 1] or close.iat[i - 1] < final_lower.iat[i - 1]
            else final_lower.iat[i - 1]
        )

    supertrend = pd.Series(index=df.index, dtype=float)
    signal     = pd.Series(index=df.index, dtype=str)

    for i in range(1, len(df)):
        if close.iat[i] > final_upper.iat[i - 1]:
            supertrend.iat[i] = final_lower.iat[i]
            signal.iat[i]     = "BUY"
        elif close.iat[i] < final_lower.iat[i - 1]:
            supertrend.iat[i] = final_upper.iat[i]
            signal.iat[i]     = "SELL"
        else:
            supertrend.iat[i] = supertrend.iat[i - 1]
            signal.iat[i]     = signal.iat[i - 1]

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
    ADX using Wilder's smoothing (alpha = 1/period).
    FIX: was using ewm(span=period) which gives alpha=2/(period+1) — too fast.
         Wilder's standard is alpha=1/period (slower, more stable).
    > 25 = strong trend  |  > 40 = very strong  |  < 20 = choppy
    """
    high  = df["high"]
    low   = df["low"]
    close = df["close"]

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)

    up   = high.diff()
    down = -low.diff()

    plus_dm  = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)

    # FIX: Wilder's alpha = 1/period, not span=period
    alpha    = 1 / period
    atr_s    = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_di  = 100 * plus_dm.ewm(alpha=alpha, adjust=False).mean() / atr_s
    minus_di = 100 * minus_dm.ewm(alpha=alpha, adjust=False).mean() / atr_s

    dx  = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).fillna(0)
    adx = dx.ewm(alpha=alpha, adjust=False).mean()

    current_adx  = round(float(adx.iloc[-1]), 2)
    plus_di_val  = round(float(plus_di.iloc[-1]), 2)
    minus_di_val = round(float(minus_di.iloc[-1]), 2)

    return {
        "adx":             current_adx,
        "adx_strong":      bool(current_adx >= 25),
        "adx_very_strong": bool(current_adx >= 40),
        "plus_di":         plus_di_val,
        "minus_di":        minus_di_val,
        "adx_bullish":     bool(current_adx >= 25 and plus_di_val > minus_di_val),
    }


# ── MAIN FETCH ─────────────────────────────────────────────────────────────────

def get_technical_data(
    kite:             KiteConnect,
    instrument_token: int,
    symbol:           str,
    nifty_1m_return:  float | None = None,
) -> dict:
    """
    Fetch OHLCV history and compute all technical indicators for a symbol.
    FIX: fetch window increased from 365 to 500 calendar days to guarantee
         252+ trading rows — required for 200 DMA and 12M momentum to be valid.
         365 days often yields only 240–248 rows after holidays, causing
         silent NaN / wrong values in tail(200) and tail(252).
    """
    try:
        to_date   = datetime.now()
        from_date = to_date - timedelta(days=500)   # FIX: was 365

        hist = kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_date.strftime("%Y-%m-%d"),
            to_date=to_date.strftime("%Y-%m-%d"),
            interval="day",
        )

        df      = pd.DataFrame(hist)
        closes  = df["close"]
        volumes = df["volume"]

        # Guard: need at least 200 rows for meaningful signals
        if len(df) < 200:
            logger.warning(
                "%s: only %d rows returned — 200 DMA and momentum may be inaccurate",
                symbol, len(df),
            )

        # ── core indicators ──────────────────────────────────────────────────
        dma20  = round(float(closes.tail(20).mean()), 2)
        dma50  = round(float(closes.tail(50).mean()), 2)
        dma200 = round(float(closes.tail(200).mean()), 2) if len(closes) >= 200 else None
        cmp    = round(float(closes.iloc[-1]), 2)

        # FIX: uses imported calc_rsi from quant.py (Wilder's EWM, not rolling mean)
        rsi = calc_rsi(closes)

        avg_vol_20    = volumes.tail(20).mean()
        last_vol      = volumes.iloc[-1]
        vol_above_avg = bool(last_vol > avg_vol_20)

        # ── tier 2 indicators ────────────────────────────────────────────────
        macd_crossover = calc_macd_crossover(closes)
        new_3m_high    = calc_new_3m_high(df)
        golden_cross   = calc_golden_cross(closes)
        atr_pct        = calc_atr_pct(df)          # FIX: now uses full True Range
        bb_squeeze     = calc_bb_squeeze(closes)
        st             = calc_supertrend(df)        # FIX: uses .iat[] assignments
        adx_data       = calc_adx(df)               # FIX: uses Wilder's alpha

        stock_1m_return = round(float((closes.iloc[-1] / closes.iloc[-21] - 1) * 100), 2)

        # nifty_1m_return=None means benchmark fetch failed; treat RS as unknown
        # FIX: was returning True for all positive stocks when benchmark = 0.0
        rs_vs_nifty = (
            bool(stock_1m_return > nifty_1m_return)
            if nifty_1m_return is not None
            else None
        )

        return {
            # core
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
        logger.exception("get_technical_data failed for %s", symbol)
        return {"symbol": symbol, "error": str(e)}


# ── BENCHMARK ─────────────────────────────────────────────────────────────────

def get_nifty_1m_return(kite: KiteConnect) -> float | None:
    """
    Fetch Nifty 50 1-month return for RS comparison.
    FIX: now returns None on failure instead of 0.0.
         Returning 0.0 silently made every stock with positive 1M return
         appear to have RS vs Nifty, inflating the rs_vs_nifty filter.
    """
    try:
        to_date   = datetime.now()
        from_date = to_date - timedelta(days=40)
        hist      = kite.historical_data(
            instrument_token=256265,        # NIFTY 50 token
            from_date=from_date.strftime("%Y-%m-%d"),
            to_date=to_date.strftime("%Y-%m-%d"),
            interval="day",
        )
        closes = pd.DataFrame(hist)["close"]
        return round(float((closes.iloc[-1] / closes.iloc[-21] - 1) * 100), 2)
    except Exception:
        logger.warning("Nifty 1M return fetch failed — rs_vs_nifty will be None for all stocks")
        return None     # FIX: was returning 0.0


# ── INSTRUMENTS ───────────────────────────────────────────────────────────────

def get_all_nse_instruments(kite: KiteConnect) -> list:
    instruments = kite.instruments("NSE")
    return [i for i in instruments if i["segment"] == "NSE"]