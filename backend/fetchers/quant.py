import pandas as pd
import numpy as np
from typing import Dict, Any

def calc_rsi(prices: pd.Series, period: int = 14) -> float:
    delta = prices.diff()
    gain  = delta.where(delta > 0, 0).rolling(period).mean()
    loss  = -delta.where(delta < 0, 0).rolling(period).mean()
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
        "macd":       round(float(macd.iloc[-1]), 4),
        "signal":     round(float(signal.iloc[-1]), 4),
        "histogram":  round(float(hist.iloc[-1]), 4),
        "bullish":    float(hist.iloc[-1]) > 0 and float(hist.iloc[-1]) > float(hist.iloc[-2]),
    }

def calc_bollinger(prices: pd.Series, period: int = 20) -> Dict[str, float]:
    sma    = prices.rolling(period).mean()
    std    = prices.rolling(period).std()
    upper  = sma + (2 * std)
    lower  = sma - (2 * std)
    cmp    = prices.iloc[-1]
    band_w = float((upper.iloc[-1] - lower.iloc[-1]) / sma.iloc[-1] * 100)
    pct_b  = float((cmp - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1]))
    return {
        "upper":      round(float(upper.iloc[-1]), 2),
        "middle":     round(float(sma.iloc[-1]), 2),
        "lower":      round(float(lower.iloc[-1]), 2),
        "pct_b":      round(pct_b, 3),
        "bandwidth":  round(band_w, 2),
        "squeeze":    band_w < 10,
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
    """Multi-period momentum — core quant factor"""
    ret_1m  = (prices.iloc[-1] / prices.iloc[-21]  - 1) * 100 if len(prices) > 21  else 0
    ret_3m  = (prices.iloc[-1] / prices.iloc[-63]  - 1) * 100 if len(prices) > 63  else 0
    ret_6m  = (prices.iloc[-1] / prices.iloc[-126] - 1) * 100 if len(prices) > 126 else 0
    ret_12m = (prices.iloc[-1] / prices.iloc[-252] - 1) * 100 if len(prices) > 252 else 0

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
    """Annualised volatility — risk metric"""
    daily_ret = prices.pct_change().dropna()
    vol_20d   = daily_ret.tail(20).std() * (252 ** 0.5) * 100
    vol_60d   = daily_ret.tail(60).std() * (252 ** 0.5) * 100
    return {
        "vol_20d": round(float(vol_20d), 2),
        "vol_60d": round(float(vol_60d), 2),
        "high_vol": float(vol_20d) > 40,
    }

def calc_trend_strength(prices: pd.Series) -> Dict[str, Any]:
    """ADX-based trend strength"""
    if len(prices) < 28:
        return {"adx": 0, "trending": False, "trend": "sideways"}

    # Simplified ADX calculation
    changes  = prices.diff().abs()
    smooth   = changes.rolling(14).mean()
    adx_val  = float(smooth.iloc[-1] / prices.iloc[-1] * 100)

    trend_dir = "up" if prices.iloc[-1] > prices.iloc[-20] else "down"

    return {
        "adx":      round(adx_val * 10, 2),
        "trending": adx_val > 2,
        "trend":    trend_dir if adx_val > 2 else "sideways",
    }

def calc_volume_trend(volumes: pd.Series) -> Dict[str, Any]:
    """Volume analysis — institutional activity signal"""
    avg_20 = float(volumes.tail(20).mean())
    avg_5  = float(volumes.tail(5).mean())
    last   = float(volumes.iloc[-1])

    vol_ratio    = round(last / avg_20, 2) if avg_20 > 0 else 1
    vol_trend    = round(avg_5 / avg_20, 2) if avg_20 > 0 else 1

    return {
        "vol_ratio":      vol_ratio,
        "vol_trend":      vol_trend,
        "spike":          vol_ratio >= 2.0,
        "accumulation":   vol_trend > 1.1 and last > avg_20,
        "distribution":   vol_trend < 0.9 and last < avg_20,
    }

def calc_support_resistance(prices: pd.Series, volumes: pd.Series) -> Dict[str, float]:
    """Volume-weighted support and resistance levels"""
    recent = prices.tail(60)
    high   = float(recent.max())
    low    = float(recent.min())
    cmp    = float(prices.iloc[-1])

    # Pivot point
    pivot  = (high + low + cmp) / 3
    r1     = 2 * pivot - low
    s1     = 2 * pivot - high
    r2     = pivot + (high - low)
    s2     = pivot - (high - low)

    return {
        "pivot": round(pivot, 2),
        "r1":    round(r1, 2),
        "r2":    round(r2, 2),
        "s1":    round(s1, 2),
        "s2":    round(s2, 2),
    }

def generate_quant_signal(
    prices:  pd.Series,
    volumes: pd.Series,
    df:      pd.DataFrame,
    fundamentals: dict = {}
) -> Dict[str, Any]:
    """
    Full quant signal engine — combines technical + momentum + volume
    Returns a Buy/Hold/Sell signal with confidence score
    """

    rsi        = calc_rsi(prices)
    macd       = calc_macd(prices)
    bollinger  = calc_bollinger(prices)
    momentum   = calc_momentum_score(prices)
    volatility = calc_volatility(prices)
    trend      = calc_trend_strength(prices)
    volume     = calc_volume_trend(volumes)
    sr_levels  = calc_support_resistance(prices, volumes)
    atr        = calc_atr(df)

    # DMA signals
    dma20  = float(prices.tail(20).mean())
    dma50  = float(prices.tail(50).mean())
    dma200 = float(prices.tail(200).mean()) if len(prices) >= 200 else dma50
    cmp    = float(prices.iloc[-1])

    # ── SCORING ENGINE ──────────────────────────────────────────
    score = 0
    max_score = 100
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

    # 2. Trend (20 points)
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

    # Normalize score to 0-100
    score = max(0, min(100, score + 30))

    # Generate signal
    if score >= 70:
        signal    = "Buy"
        signal_color = "green"
    elif score >= 55:
        signal    = "Outperform"
        signal_color = "teal"
    elif score >= 40:
        signal    = "Hold"
        signal_color = "amber"
    elif score >= 25:
        signal    = "Underperform"
        signal_color = "orange"
    else:
        signal    = "Sell"
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