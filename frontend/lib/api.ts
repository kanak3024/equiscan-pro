const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export type LiveStock = {
  symbol: string
  mcap: number
  pe: number | null
  roe: number
  debt_eq: number
  revenue_growth: number
  profit_3q: boolean
  cashflow_5q: boolean
  cmp: number
  dma20: number
  dma50: number
  dma200: number
  rsi: number
  vol_above_avg: boolean
  analyst: string
  analyst_score: number
  price_target: number
  recent_upgrade: boolean
  inst_buying: boolean
  error: string | null
}

export async function fetchFundamentals(symbol: string) {
  const res = await fetch(`${API_BASE}/api/stock/${symbol}/fundamentals`)
  return res.json()
}

export async function fetchTechnical(symbol: string) {
  const res = await fetch(`${API_BASE}/api/stock/${symbol}/technical`)
  return res.json()
}

export async function fetchAnalyst(symbol: string) {
  const res = await fetch(`${API_BASE}/api/stock/${symbol}/analyst`)
  return res.json()
}

export async function fetchFullStock(symbol: string): Promise<LiveStock> {
  const [fund, tech, anal] = await Promise.all([
    fetchFundamentals(symbol),
    fetchTechnical(symbol),
    fetchAnalyst(symbol),
  ])
  return {
    symbol,
    ...fund,
    ...tech,
    ...anal,
  }
}

 export async function fetchScreened(symbols: string[]): Promise<any[]> {
  const params = symbols.join(',')
  const res = await fetch(`${API_BASE}/api/screen?symbols=${params}`)
  const data = await res.json()
  
  // Also fetch technical data for each stock
  const withTech = await Promise.all(
    data.results.map(async (stock: any) => {
      try {
        const tech = await fetchTechnical(stock.symbol)
        return { ...stock, ...tech }
      } catch {
        return stock
      }
    })
  )
  return withTech
}

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/api/health`)
  return res.json()
}

export function mapLiveToStock(live: any) {
  return {
    sym:            live.symbol,
    name:           live.name || live.symbol,
    sector:         live.sector || 'Unknown',
    ipoYear:        live.ipo_year || 2020,
    mcap:           live.mcap || 0,
    promoter:       live.promoter || 0,
    promoterStable: live.promoter_stable ?? true,
    pledge:         live.pledge || 0,
    dma20:          live.dma20 || 0,
    dma50:          live.dma50 || 0,
    dma200:         live.dma200 || 0,
    profit3Q:       live.profit_3q ?? false,
    cashflow5Q:     live.cashflow_5q ?? false,
    pe:             live.pe || null,
    roe:            live.roe || 0,
    revenueGrowth:  live.revenue_growth || 0,
    debtEq:         live.debt_eq || 0,
    rsi:            live.rsi || 50,
    volAboveAvg:    live.vol_above_avg ?? false,
    analyst:        live.analyst || 'Hold',
    analystScore:   live.analyst_score || 50,
    cmp:            live.cmp || 0,
    priceTarget:    live.price_target || 0,
    recentUpgrade:  live.recent_upgrade ?? false,
    instBuying:     live.inst_buying ?? false,
    epsIncreasing:  live.eps_increasing ?? false,
    high52w: live.high52w || 0,
    macdCrossover:   live.macd_crossover  ?? false,
    new3mHigh:       live.new_3m_high     ?? false,
    goldenCross:     live.golden_cross    ?? false,
    rsVsNifty:       live.rs_vs_nifty     ?? false,
    lowAtr:          live.low_atr         ?? false,
    atrPct:          live.atr_pct         ?? 0,
    bbSqueeze:       live.bb_squeeze      ?? false,
    stock1mReturn:   live.stock_1m_return ?? 0,
    supertrendBuy:   live.supertrend_buy  ?? false,
    supertrendSignal:live.supertrend_signal ?? 'SELL',
    supertrendValue: live.supertrend_value ?? 0,
    supertrendDays:  live.supertrend_days ?? 0,
    adxBullish:      live.adx_bullish     ?? false,
    adx:             live.adx             ?? 0,
    adxStrong:       live.adx_strong      ?? false,
    adxVeryStrong:   live.adx_very_strong ?? false,
    plusDi:          live.plus_di         ?? 0,
    minusDi:         live.minus_di        ?? 0,

  }
}