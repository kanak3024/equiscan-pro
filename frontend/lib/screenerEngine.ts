import { Stock } from './stockData'

export type Filters = {
  // ── Existing filters ───────────────────────────────────────
  f_listed8y: boolean
  f_mcap1000: boolean
  f_promoter75: boolean
  f_noDilution: boolean
  f_dmaAligned: boolean
  f_dma50_200: boolean
  f_profit3Q: boolean
  f_cashflow5Q: boolean
  f_analystPositive: boolean
  f_pledge5: boolean
  f_rsiHealthy: boolean
  f_peUnder60: boolean
  f_revenueGrowth15: boolean
  f_debtLow: boolean
  f_roe15: boolean
  f_recentUpgrade: boolean
  f_priceTargetUpside20: boolean
  f_instBuying: boolean
  f_epsIncreasing: boolean
  f_near52wHigh: boolean
  minMcap: number
  minPromoter: number
  // ── Tier 2 filters ─────────────────────────────────────────
  f_macdCrossover: boolean
  f_new3mHigh: boolean
  f_goldenCross: boolean
  f_rsVsNifty: boolean
  f_lowAtr: boolean
  f_bbSqueeze: boolean
  f_supertrendBuy: boolean
  f_adxBullish: boolean
}

export const defaultFilters: Filters = {
  // ── Existing defaults ──────────────────────────────────────
  f_listed8y:            true,
  f_mcap1000:            true,
  f_promoter75:          true,
  f_noDilution:          true,
  f_dmaAligned:          true,
  f_dma50_200:           true,
  f_profit3Q:            true,
  f_cashflow5Q:          true,
  f_analystPositive:     true,
  f_pledge5:             false,
  f_rsiHealthy:          false,
  f_peUnder60:           false,
  f_revenueGrowth15:     false,
  f_debtLow:             false,
  f_roe15:               false,
  f_recentUpgrade:       false,
  f_priceTargetUpside20: false,
  f_instBuying:          false,
  f_epsIncreasing:       false,
  f_near52wHigh:         false,
  minMcap:               1000,
  minPromoter:           75,
  // ── Tier 2 defaults (all off — opt-in) ────────────────────
  f_macdCrossover:       false,
  f_new3mHigh:           false,
  f_goldenCross:         false,
  f_rsVsNifty:           false,
  f_lowAtr:              false,
  f_bbSqueeze:           false,
  f_supertrendBuy:       false,
  f_adxBullish:          false,
}

export type StockResult = {
  stock: Stock
  checks: Record<string, boolean>
  score: number
  maxScore: number
  passed: boolean
}

export function runScreener(stocks: Stock[], filters: Filters): StockResult[] {
  const results = stocks.map((s) => {
    const upside = ((s.priceTarget - s.cmp) / s.cmp) * 100

    const checks: Record<string, boolean> = {
      // ── Existing checks ──────────────────────────────────────
      f_listed8y:            s.ipoYear >= 2017,
      f_mcap1000:            s.mcap >= filters.minMcap,
      f_promoter75:          s.promoter >= filters.minPromoter,
      f_noDilution:          s.promoterStable,
      f_dmaAligned:          s.dma20 > s.dma50 && s.dma50 > s.dma200,
      f_dma50_200:           s.dma50 > s.dma200,
      f_profit3Q:            s.profit3Q,
      f_cashflow5Q:          s.cashflow5Q,
      f_analystPositive:     s.analyst === 'Buy' || s.analyst === 'Outperform',
      f_pledge5:             s.pledge < 5,
      f_rsiHealthy:          s.rsi >= 40 && s.rsi <= 70,
      f_peUnder60:           s.pe !== null && s.pe < 60,
      f_revenueGrowth15:     s.revenueGrowth > 15,
      f_debtLow:             s.debtEq < 0.5,
      f_roe15:               s.roe > 15,
      f_recentUpgrade:       s.recentUpgrade,
      f_priceTargetUpside20: upside > 20,
      f_instBuying:          s.instBuying,
      f_epsIncreasing:       s.epsIncreasing ?? false,
      f_near52wHigh: (() => {
        if (!s.high52w || !s.cmp) return false
        return ((s.cmp - s.high52w) / s.high52w) * 100 >= -10
      })(),
      // ── Tier 2 checks ────────────────────────────────────────
      f_macdCrossover: s.macdCrossover  ?? false,
      f_new3mHigh:     s.new3mHigh      ?? false,
      f_goldenCross:   s.goldenCross    ?? false,
      f_rsVsNifty:     s.rsVsNifty      ?? false,
      f_lowAtr:        s.lowAtr         ?? false,
      f_bbSqueeze:     s.bbSqueeze      ?? false,
      f_supertrendBuy: s.supertrendBuy  ?? false,
      f_adxBullish:    s.adxBullish     ?? false,
    }

    const score    = Object.values(checks).filter(Boolean).length
    const maxScore = Object.keys(checks).length

    const activeFilterKeys = Object.keys(filters).filter(
      (k) => k.startsWith('f_') && filters[k as keyof Filters] === true
    )
    const passed = activeFilterKeys.every((k) => checks[k])

    return { stock: s, checks, score, maxScore, passed }
  })

  return results.sort((a, b) => {
    if (a.passed && !b.passed) return -1
    if (!a.passed && b.passed) return 1
    return b.score - a.score
  })
}

// ── Tier 2 filter metadata (used by FilterPanel to render the section) ────────
export const TIER2_FILTERS = [
  {
    key:         'f_macdCrossover' as keyof Filters,
    label:       'MACD Bullish Crossover',
    description: 'MACD line just crossed above signal line — momentum turning positive',
  },
  {
    key:         'f_new3mHigh' as keyof Filters,
    label:       'Price Making New Highs',
    description: 'CMP is at or above the 3-month high — breakout signal',
  },
  {
    key:         'f_goldenCross' as keyof Filters,
    label:       'Golden Cross',
    description: '50 DMA crossed above 200 DMA recently — major bullish event',
  },
  {
    key:         'f_rsVsNifty' as keyof Filters,
    label:       'Relative Strength > Nifty',
    description: 'Stock 1M return beating Nifty 50 — outperformance signal',
  },
  {
    key:         'f_lowAtr' as keyof Filters,
    label:       'ATR < 3%',
    description: 'Daily volatility is low and controlled — stable price action',
  },
  {
    key:         'f_bbSqueeze' as keyof Filters,
    label:       'Bollinger Band Squeeze',
    description: 'Bands tightening — explosive move likely incoming',
  },
  {
    key:         'f_supertrendBuy' as keyof Filters,
    label:       'Supertrend — Buy Signal',
    description: 'Price above Supertrend line — clean trend-following buy signal',
  },
  {
    key:         'f_adxBullish' as keyof Filters,
    label:       'ADX > 25 — Strong Trend',
    description: 'Trend is strong enough to trade — filters out choppy sideways stocks',
  },
] as const