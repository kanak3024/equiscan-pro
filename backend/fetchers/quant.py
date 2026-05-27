import pandas as pd
import numpy as np
from typing import Dict, Any


def calc_rsi(prices: pd.Series, period: int = 14) -> float:
    """
    RSI using Wilder's smoothing (EWM with alpha=1/period).
    FIX: Was using simple rolling mean — now uses proper Wilder's EWM.
    """
    delta = prices.diff()
    gain  = delta.where(delta > 0, 0).ewm(alpha=1 / period, adjust=False).mean()
    loss  = (-delta.where(delta < 0, 0)).ewm(alpha=1 / period, adjust=False).mean()
    rs    = gain / loss
    rsi   = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)


def calc_macd(prices: pd.Series) -> Dict[str, float]:
    ema12  = prices.ewm(span=12, adjust=False).mean()
    ema26  = prices.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist   = macd - signal
    return {
        "macd":      round(float(macd.iloc[-1]), 4),
        "signal":    round(float(signal.iloc[-1]), 4),
        "histogram": round(float(hist.iloc[-1]), 4),
        "bullish":   float(hist.iloc[-1]) > 0 and float(hist.iloc[-1]) > float(hist.iloc[-2]),
    }


def calc_bollinger(prices: pd.Series, period: int = 20) -> Dict[str, float]:
    sma   = prices.rolling(period).mean()
    std   = prices.rolling(period).std()
    upper = sma + (2 * std)
    lower = sma - (2 * std)
    cmp   = prices.iloc[-1]

    band_w = float((upper.iloc[-1] - lower.iloc[-1]) / sma.iloc[-1] * 100)
    pct_b  = float((cmp - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1]))
    return {
        "upper":     round(float(upper.iloc[-1]), 2),
        "middle":    round(float(sma.iloc[-1]), 2),
        "lower":     round(float(lower.iloc[-1]), 2),
        "pct_b":     round(pct_b, 3),
        "bandwidth": round(band_w, 2),
        "squeeze":   band_w < 10,
    }


def calc_atr(df: pd.DataFrame, period: int = 14) -> float:
    high  = df["high"]
    low   = df["low"]
    close = df["close"]
    tr    = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    return round(float(atr), 2)


def calc_momentum_score(prices: pd.Series) -> Dict[str, float]:
    """
    Multi-period momentum — core quant factor.
    FIX: 12M return now excludes the most recent month (Jegadeesh-Titman standard)
         to avoid short-term mean-reversion contamination.
    """
    ret_1m  = (prices.iloc[-1]  / prices.iloc[-21]  - 1) * 100 if len(prices) > 21  else 0
    ret_3m  = (prices.iloc[-1]  / prices.iloc[-63]  - 1) * 100 if len(prices) > 63  else 0
    ret_6m  = (prices.iloc[-1]  / prices.iloc[-126] - 1) * 100 if len(prices) > 126 else 0
    # FIX: use prices.iloc[-21] as end point to skip the last month
    ret_12m = (prices.iloc[-21] / prices.iloc[-252] - 1) * 100 if len(prices) > 252 else 0

    # Weighted momentum (6M and 12M weighted more — institutional standard)
    weighted = (ret_1m * 0.1) + (ret_3m * 0.2) + (ret_6m * 0.3) + (ret_12m * 0.4)

    return {
        "ret_1m":   round(ret_1m, 2),
        "ret_3m":   round(ret_3m, 2),
        "ret_6m":   round(ret_6m, 2),
        "ret_12m":  round(ret_12m, 2),
        "weighted": round(weighted, 2),
    }


def calc_volatility(prices: pd.Series) -> Dict[str, float]:
    """
    Annualised volatility — risk metric.
    FIX: high_vol threshold raised to 60% for Indian market context
         (40% is normal for Indian mid/small caps; 60%+ is genuinely elevated).
    """
    daily_ret = prices.pct_change().dropna()
    vol_20d   = daily_ret.tail(20).std() * (252 ** 0.5) * 100
    vol_60d   = daily_ret.tail(60).std() * (252 ** 0.5) * 100
    return {
        "vol_20d":  round(float(vol_20d), 2),
        "vol_60d":  round(float(vol_60d), 2),
        "high_vol": float(vol_20d) > 60,   # FIX: was 40, raised to 60 for Indian market
    }


def calc_adx(df: pd.DataFrame, period: int = 14) -> Dict[str, Any]:
    """
    Proper ADX using Wilder's +DI / -DI directional movement.
    FIX: Replaces the old fake ADX (which was just normalised absolute price change).
    Requires df with 'high', 'low', 'close' columns.
    """
    high  = df["high"]
    low   = df["low"]
    close = df["close"]

    # True Range
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)

    # Directional Movement
    up_move   = high.diff()
    down_move = -low.diff()

    plus_dm  = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    # Wilder's smoothing
    atr14      = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di14  = 100 * (plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr14)
    minus_di14 = 100 * (minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr14)

    dx  = 100 * (plus_di14 - minus_di14).abs() / (plus_di14 + minus_di14)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()

    adx_val      = round(float(adx.iloc[-1]), 2)
    plus_di_val  = round(float(plus_di14.iloc[-1]), 2)
    minus_di_val = round(float(minus_di14.iloc[-1]), 2)

    trend_dir = "up" if plus_di_val > minus_di_val else "down"

    return {
        "adx":       adx_val,
        "plus_di":   plus_di_val,
        "minus_di":  minus_di_val,
        "trending":  adx_val > 25,
        "trend":     trend_dir if adx_val > 25 else "sideways",
    }


def calc_volume_trend(volumes: pd.Series) -> Dict[str, Any]:
    """Volume analysis — institutional activity signal."""
    avg_20 = float(volumes.tail(20).mean())
    avg_5  = float(volumes.tail(5).mean())
    last   = float(volumes.iloc[-1])

    vol_ratio = round(last / avg_20, 2) if avg_20 > 0 else 1
    vol_trend = round(avg_5 / avg_20, 2) if avg_20 > 0 else 1

    return {
        "vol_ratio":    vol_ratio,
        "vol_trend":    vol_trend,
        "spike":        vol_ratio >= 2.0,
        "accumulation": vol_trend > 1.1 and last > avg_20,
        "distribution": vol_trend < 0.9 and last < avg_20,
    }


def calc_support_resistance(prices: pd.Series, volumes: pd.Series) -> Dict[str, float]:
    """Volume-weighted support and resistance levels via floor-trader pivots."""
    recent = prices.tail(60)
    high   = float(recent.max())
    low    = float(recent.min())
    cmp    = float(prices.iloc[-1])

    pivot = (high + low + cmp) / 3
    r1    = 2 * pivot - low
    s1    = 2 * pivot - high
    r2    = pivot + (high - low)
    s2    = pivot - (high - low)

    return {
        "pivot": round(pivot, 2),
        "r1":    round(r1, 2),
        "r2":    round(r2, 2),
        "s1":    round(s1, 2),
        "s2":    round(s2, 2),
    }


def generate_quant_signal(
    prices:       pd.Series,
    volumes:      pd.Series,
    df:           pd.DataFrame,
    fundamentals: dict = {}
) -> Dict[str, Any]:
    """
    Full quant signal engine — combines technical + momentum + volume.
    Returns a Buy/Hold/Sell signal with confidence score.
    FIX: Removed arbitrary +30 baseline offset from scoring engine.
         Score now purely reflects signal weight sum, normalised to 0–100.
    """
    rsi       = calc_rsi(prices)
    macd      = calc_macd(prices)
    bollinger = calc_bollinger(prices)
    momentum  = calc_momentum_score(prices)
    volatility= calc_volatility(prices)
    trend     = calc_adx(df)          # FIX: uses real ADX now
    volume    = calc_volume_trend(volumes)
    sr_levels = calc_support_resistance(prices, volumes)
    atr       = calc_atr(df)

    # DMA signals
    dma20  = float(prices.tail(20).mean())
    dma50  = float(prices.tail(50).mean())
    dma200 = float(prices.tail(200).mean()) if len(prices) >= 200 else dma50
    cmp    = float(prices.iloc[-1])

    # ── SCORING ENGINE ──────────────────────────────────────────
    # Max achievable raw score = 100 (sum of all positive weights)
    # Min achievable raw score = -33 (sum of all negative weights)
    # We map this range linearly to 0–100 at the end.
    score   = 0
    signals = []

    # 1. Momentum (30 points)
    if momentum["weighted"] > 20:
        score += 30
        signals.append(("Strong momentum", "+30", "green"))
    elif momentum["weighted"] > 10:
        score += 20
        signals.append(("Good momentum", "+20", "green"))
    elif momentum["weighted"] > 0:
        score += 10
        signals.append(("Weak momentum", "+10", "amber"))
    elif momentum["weighted"] < -10:
        score -= 10
        signals.append(("Negative momentum", "-10", "red"))

    # 2. Trend / DMA (20 points)
    if dma20 > dma50 > dma200:
        score += 20
        signals.append(("Bullish DMA alignment", "+20", "green"))
    elif dma50 > dma200:
        score += 10
        signals.append(("Medium-term uptrend", "+10", "green"))
    elif dma20 < dma50 < dma200:
        score -= 10
        signals.append(("Bearish DMA alignment", "-10", "red"))

    # 3. MACD (15 points)
    if macd["bullish"] and macd["macd"] > 0:
        score += 15
        signals.append(("MACD bullish crossover", "+15", "green"))
    elif macd["bullish"]:
        score += 8
        signals.append(("MACD improving", "+8", "amber"))
    elif not macd["bullish"] and macd["macd"] < 0:
        score -= 8
        signals.append(("MACD bearish", "-8", "red"))

    # 4. RSI (15 points)
    if 50 <= rsi <= 65:
        score += 15
        signals.append(("RSI healthy bullish zone", "+15", "green"))
    elif 40 <= rsi < 50:
        score += 8
        signals.append(("RSI neutral", "+8", "amber"))
    elif rsi > 75:
        score -= 5
        signals.append(("RSI overbought", "-5", "red"))
    elif rsi < 30:
        score += 5
        signals.append(("RSI oversold — potential bounce", "+5", "amber"))

    # 5. Volume (10 points)
    if volume["accumulation"]:
        score += 10
        signals.append(("Volume accumulation", "+10", "green"))
    elif volume["distribution"]:
        score -= 5
        signals.append(("Volume distribution", "-5", "red"))

    # 6. Bollinger (10 points)
    if 0.4 <= bollinger["pct_b"] <= 0.8:
        score += 10
        signals.append(("Price in Bollinger sweet spot", "+10", "green"))
    elif bollinger["pct_b"] > 0.95:
        score -= 5
        signals.append(("Price at Bollinger upper band", "-5", "amber"))
    elif bollinger["pct_b"] < 0.1:
        score += 5
        signals.append(("Price at Bollinger lower band", "+5", "amber"))

    # FIX: Map raw score range [-33, 100] linearly to [0, 100]
    # instead of the old arbitrary score + 30 clamp.
    raw_min = -33
    raw_max = 100
    score   = int(round((score - raw_min) / (raw_max - raw_min) * 100))
    score   = max(0, min(100, score))

    # Generate signal
    if score >= 70:
        signal       = "Buy"
        signal_color = "green"
    elif score >= 55:
        signal       = "Outperform"
        signal_color = "teal"
    elif score >= 40:
        signal       = "Hold"
        signal_color = "amber"
    elif score >= 25:
        signal       = "Underperform"
        signal_color = "orange"
    else:
        signal       = "Sell"
        signal_color = "red"

    return {
        "signal":       signal,
        "score":        score,
        "signal_color": signal_color,
        "signals":      signals,
        "rsi":          rsi,
        "macd":         macd,
        "bollinger":    bollinger,
        "momentum":     momentum,
        "volatility":   volatility,
        "trend":        trend,
        "volume":       volume,
        "sr_levels":    sr_levels,
        "atr":          atr,
        "dma20":        round(dma20, 2),
        "dma50":        round(dma50, 2),
        "dma200":       round(dma200, 2),
        "cmp":          round(cmp, 2),
    }


def calc_tier2_signals(
    prices:  pd.Series,
    volumes: pd.Series,
    df:      pd.DataFrame,
    atr:     float,
) -> dict:
    """
    Calculate all Tier 2 technical filter signals.
    FIXES applied:
      - bw now correctly uses .iloc[-1] to get scalar from Series
      - golden_cross uses proper point-in-time DMA crossover detection
      - adx_bullish uses real ADX from calc_adx instead of a proxy
    """
    closes = prices
    highs  = df["high"] if "high" in df.columns else prices
    lows   = df["low"]  if "low"  in df.columns else prices
    cmp    = float(closes.iloc[-1])

    # ── MACD Crossover ────────────────────────────────────────
    ema12  = closes.ewm(span=12, adjust=False).mean()
    ema26  = closes.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    macd_crossover = (
        float(macd.iloc[-1]) > float(signal.iloc[-1]) and
        float(macd.iloc[-3]) < float(signal.iloc[-3])
    )

    # ── Price making new 3M high ──────────────────────────────
    high_3m    = float(highs.tail(63).max()) if len(highs) >= 63 else float(highs.max())
    new3m_high = cmp >= high_3m * 0.99

    # ── Golden Cross ──────────────────────────────────────────
    # FIX: Proper crossover detection — check that DMA50 was below DMA200
    # at some point in the lookback window and is now above it.
    if len(closes) >= 200:
        dma50_series  = closes.rolling(50).mean()
        dma200_series = closes.rolling(200).mean()
        # Is 50 DMA currently above 200 DMA?
        currently_above = dma50_series.iloc[-1] > dma200_series.iloc[-1]
        # Was 50 DMA below 200 DMA within the last 20 trading days?
        was_below = any(
            dma50_series.iloc[i] < dma200_series.iloc[i]
            for i in range(-20, -1)
        )
        golden_cross = currently_above and was_below
    else:
        golden_cross = False

    # ── Relative Strength vs Nifty (approximated via 1M momentum) ─
    ret_1m      = (cmp / float(closes.iloc[-21]) - 1) * 100 if len(closes) >= 21 else 0
    rs_vs_nifty = ret_1m > 3.0

    # ── Low ATR (< 3% of price) ───────────────────────────────
    atr_pct = (atr / cmp * 100) if cmp > 0 else 999
    low_atr  = atr_pct < 3.0

    # ── Bollinger Band Squeeze ────────────────────────────────
    # FIX: was float() on a full Series — now correctly takes .iloc[-1]
    sma20 = closes.rolling(20).mean()
    std20 = closes.rolling(20).std()
    bw    = float(((sma20 + 2 * std20) - (sma20 - 2 * std20)).iloc[-1] / sma20.iloc[-1] * 100)
    bb_squeeze = bw < 8.0

    # ── Supertrend Buy Signal ─────────────────────────────────
    dma50_now  = float(closes.tail(50).mean())
    dma200_now = float(closes.tail(200).mean()) if len(closes) >= 200 else dma50_now
    supertrend_level = dma200_now - (1.5 * atr)
    supertrend_buy   = cmp > supertrend_level and dma50_now > dma200_now

    # ── ADX > 25 (Strong Trend) ───────────────────────────────
    # FIX: uses real ADX via calc_adx instead of the old price-change proxy
    adx_result = calc_adx(df)
    adx_bullish = adx_result["adx"] > 25 and adx_result["trend"] == "up"

    return {
        "macd_crossover": macd_crossover,
        "new3m_high":     new3m_high,
        "golden_cross":   golden_cross,
        "rs_vs_nifty":    rs_vs_nifty,
        "low_atr":        low_atr,
        "bb_squeeze":     bb_squeeze,
        "supertrend_buy": supertrend_buy,
        "adx_bullish":    adx_bullish,
    }