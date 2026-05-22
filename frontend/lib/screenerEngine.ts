import { Stock } from './stockData'

export type Filters = {
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
  minMcap: number
  minPromoter: number
  f_near52wHigh: boolean
}

export const defaultFilters: Filters = {
  f_listed8y: true,
  f_mcap1000: true,
  f_promoter75: true,
  f_noDilution: true,
  f_dmaAligned: true,
  f_dma50_200: true,
  f_profit3Q: true,
  f_cashflow5Q: true,
  f_epsIncreasing: false,
   f_analystPositive: true,
  f_pledge5: false,
  f_rsiHealthy: false,
  f_peUnder60: false,
  f_revenueGrowth15: false,
  f_debtLow: false,
  f_roe15: false,
  f_recentUpgrade: false,
  f_priceTargetUpside20: false,
  f_instBuying: false,
  minMcap: 1000,
  minPromoter: 75,
  f_near52wHigh: false,
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
      f_listed8y:            s.ipoYear >= 2017,
      f_mcap1000:            s.mcap >= filters.minMcap,
      f_promoter75:          s.promoter >= filters.minPromoter,
      f_noDilution:          s.promoterStable,
      f_dmaAligned: s.dma20 > s.dma50 && s.dma50 > s.dma200,
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
      f_epsIncreasing: s.epsIncreasing ?? false,
      f_near52wHigh: (() => {
  if (!s.high52w || !s.cmp) return false
  const pctFromHigh = ((s.cmp - s.high52w) / s.high52w) * 100
  return pctFromHigh >= -10
})(),
    }

    // Score = all checks regardless of filter toggle
    const score = Object.values(checks).filter(Boolean).length
    const maxScore = Object.keys(checks).length

    // Passed = only active filters must be true
    const activeFilterKeys = Object.keys(filters).filter(
      (k) => k.startsWith('f_') && filters[k as keyof Filters] === true
    )
    const passed = activeFilterKeys.every((k) => checks[k])

    return { stock: s, checks, score, maxScore, passed }
  })

  // Sort: passed first, then by score descending
  return results.sort((a, b) => {
    if (a.passed && !b.passed) return -1
    if (!a.passed && b.passed) return 1
    return b.score - a.score
  })
}