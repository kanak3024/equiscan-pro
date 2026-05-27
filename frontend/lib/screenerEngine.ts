export type Stock = {
  // ── Core identity ─────────────────────────────────────────
  sym:    string
  name:   string
  sector: string

  // FIX: number | null — backend returns null when IPO year is unparseable.
  // Was typed as `number` with a default of 2020, which reintroduced the
  // screener.py bug we fixed (stale default skewing age-based filters).
  ipoYear: number | null

  // ── Fundamentals ──────────────────────────────────────────
  mcap:           number
  promoter:       number
  promoterStable: boolean
  pledge:         number        // NOTE: not yet scraped — always 0 until screener.py adds it
  pe:             number | null
  roe:            number
  revenueGrowth:  number
  debtEq:         number

  // FIX: number | null — backend returns null when no price target available.
  // Was typed as `number` with default 0, causing upside calc to produce a
  // large negative number and failing f_priceTargetUpside20 for every stock
  // with no coverage.
  priceTarget: number | null

  // ── Technicals ────────────────────────────────────────────
  cmp:        number
  dma20:      number
  dma50:      number
  dma200:     number
  rsi:        number
  volAboveAvg: boolean
  high52w?:   number
  low52w?:    number

  // ── Quality flags ─────────────────────────────────────────
  profit3Q:   boolean

  // FIX: renamed from cashflow5Q → cashflow5Y. Backend renamed cashflow_5q
  // to cashflow_5y because Screener shows annual cash flows (5 years),
  // not quarterly. Old field was always undefined → always false.
  cashflow5Y: boolean

  epsIncreasing?: boolean

  // ── Analyst ───────────────────────────────────────────────
  analyst:       string
  analystScore:  number
  recentUpgrade: boolean
  instBuying:    boolean

  // ── Tier 2 fields ─────────────────────────────────────────
  macdCrossover?: boolean
  new3mHigh?:     boolean
  goldenCross?:   boolean

  // FIX: boolean | null — null means Nifty benchmark fetch failed (unknown),
  // not that the stock underperformed. Was typed as `boolean` which collapsed
  // null → false, incorrectly failing stocks when benchmark was unavailable.
  rsVsNifty?: boolean | null

  lowAtr?:        boolean
  atrPct?:        number
  bbSqueeze?:     boolean
  stock1mReturn?: number

  supertrendBuy?:    boolean
  // FIX: default undefined not 'SELL' — 'SELL' was a false negative signal
  // when Supertrend data was simply unavailable.
  supertrendSignal?: string
  supertrendValue?:  number
  supertrendDays?:   number

  adxBullish?:    boolean
  adx?:           number
  adxStrong?:     boolean
  adxVeryStrong?: boolean
  plusDi?:        number
  minusDi?:       number

  // ── Meta ──────────────────────────────────────────────────
  trendlyneAvailable?: boolean
  usedConsolidated?:   boolean
  lastUpdated?:        string
}

// ── Map raw backend response → Stock type ─────────────────────────────────────
export function mapApiStock(raw: Record<string, unknown>): Stock {
  return {
    // ── Core identity ───────────────────────────────────────
    sym:    (raw.symbol as string) ?? '',
    name:   (raw.name   as string) ?? '',
    sector: (raw.sector as string) ?? '',

    // FIX: null when unparseable — do not default to 2020
    ipoYear: raw.ipo_year != null ? (raw.ipo_year as number) : null,

    // ── Fundamentals ────────────────────────────────────────
    mcap:          (raw.mcap           as number)  ?? 0,
    promoter:      (raw.promoter       as number)  ?? 0,
    promoterStable:(raw.promoter_stable as boolean) ?? false,
    pledge:        (raw.pledge         as number)  ?? 0,
    pe:            raw.pe != null ? (raw.pe as number) : null,
    roe:           (raw.roe            as number)  ?? 0,
    revenueGrowth: (raw.revenue_growth as number)  ?? 0,
    debtEq:        (raw.debt_eq        as number)  ?? 0,

    // FIX: null when no price target — do not default to 0
    // 0 caused upside = ((0 - cmp) / cmp) * 100 → large negative → failed filter
    priceTarget: raw.price_target != null ? (raw.price_target as number) : null,

    // ── Technicals ──────────────────────────────────────────
    cmp:         (raw.cmp           as number)  ?? 0,
    dma20:       (raw.dma20         as number)  ?? 0,
    dma50:       (raw.dma50         as number)  ?? 0,
    dma200:      (raw.dma200        as number)  ?? 0,
    rsi:         (raw.rsi           as number)  ?? 0,
    volAboveAvg: (raw.vol_above_avg as boolean) ?? false,
    high52w:     raw.high52w != null ? (raw.high52w as number) : undefined,
    low52w:      raw.low52w  != null ? (raw.low52w  as number) : undefined,

    // ── Quality flags ────────────────────────────────────────
    profit3Q:     (raw.profit_3q     as boolean) ?? false,

    // FIX: reads cashflow_5y (renamed from cashflow_5q in screener.py)
    cashflow5Y:   (raw.cashflow_5y   as boolean) ?? false,

    epsIncreasing:(raw.eps_increasing as boolean) ?? false,

    // ── Analyst ─────────────────────────────────────────────
    analyst:      (raw.analyst       as string)  ?? 'Hold',
    analystScore: (raw.analyst_score as number)  ?? 50,
    recentUpgrade:(raw.recent_upgrade as boolean) ?? false,
    instBuying:   (raw.inst_buying   as boolean) ?? false,

    // ── Tier 2 ──────────────────────────────────────────────
    macdCrossover: (raw.macd_crossover as boolean) ?? false,
    new3mHigh:     (raw.new_3m_high   as boolean) ?? false,
    goldenCross:   (raw.golden_cross  as boolean) ?? false,

    // FIX: preserve null (benchmark unavailable) — do not collapse to false.
    // screenerEngine.ts treats null as "unknown — pass the filter".
    rsVsNifty: raw.rs_vs_nifty === undefined
      ? false
      : (raw.rs_vs_nifty as boolean | null),

    lowAtr:       (raw.low_atr        as boolean) ?? false,
    atrPct:       raw.atr_pct   != null ? (raw.atr_pct   as number) : undefined,
    bbSqueeze:    (raw.bb_squeeze     as boolean) ?? false,
    stock1mReturn:raw.stock_1m_return != null ? (raw.stock_1m_return as number) : undefined,

    supertrendBuy:   (raw.supertrend_buy    as boolean) ?? false,
    // FIX: undefined when missing — not 'SELL' (false negative signal)
    supertrendSignal:raw.supertrend_signal != null
      ? (raw.supertrend_signal as string)
      : undefined,
    supertrendValue: raw.supertrend_value != null
      ? (raw.supertrend_value as number)
      : undefined,
    supertrendDays:  raw.supertrend_days != null
      ? (raw.supertrend_days as number)
      : undefined,

    adxBullish:    (raw.adx_bullish    as boolean) ?? false,
    adx:           raw.adx      != null ? (raw.adx      as number)  : undefined,
    adxStrong:     (raw.adx_strong     as boolean) ?? false,
    adxVeryStrong: (raw.adx_very_strong as boolean) ?? false,
    plusDi:        raw.plus_di  != null ? (raw.plus_di  as number)  : undefined,
    minusDi:       raw.minus_di != null ? (raw.minus_di as number)  : undefined,

    // ── Meta ────────────────────────────────────────────────
    trendlyneAvailable: raw.trendlyne_available != null
      ? (raw.trendlyne_available as boolean)
      : undefined,
    usedConsolidated: raw.used_consolidated != null
      ? (raw.used_consolidated as boolean)
      : undefined,
    lastUpdated: raw.last_updated != null
      ? (raw.last_updated as string)
      : undefined,
  }
}

// ── Hardcoded fallback — used in dev when backend is offline ──────────────────
// FIX: updated all entries to use cashflow5Y (was cashflow5Q — compile error
// after type rename). Also updated ipoYear and priceTarget to match new types.
export const stocks: Stock[] = [
  { sym:"WAAREE",     name:"Waaree Energies",        sector:"Renewable Energy",  ipoYear:2024, mcap:28400, promoter:72.5, promoterStable:true,  pledge:1.2, dma20:2850, dma50:2700, dma200:2400, profit3Q:true,  cashflow5Y:true,  pe:62,   roe:18.4, revenueGrowth:38, debtEq:0.3, rsi:58, volAboveAvg:true,  analyst:"Buy",        analystScore:82, cmp:2780, priceTarget:3200, recentUpgrade:true,  instBuying:true  },
  { sym:"MANKIND",    name:"Mankind Pharma",         sector:"Pharmaceuticals",   ipoYear:2023, mcap:41200, promoter:75.8, promoterStable:true,  pledge:0,   dma20:2200, dma50:2100, dma200:1950, profit3Q:true,  cashflow5Y:true,  pe:38,   roe:22.1, revenueGrowth:19, debtEq:0.1, rsi:62, volAboveAvg:true,  analyst:"Buy",        analystScore:78, cmp:2180, priceTarget:2600, recentUpgrade:true,  instBuying:true  },
  { sym:"KAYNES",     name:"Kaynes Technology",      sector:"Electronics Mfg",   ipoYear:2022, mcap:14800, promoter:54.2, promoterStable:true,  pledge:0,   dma20:6100, dma50:5800, dma200:5200, profit3Q:true,  cashflow5Y:false, pe:95,   roe:14.2, revenueGrowth:42, debtEq:0.4, rsi:68, volAboveAvg:false, analyst:"Outperform", analystScore:72, cmp:5950, priceTarget:7000, recentUpgrade:false, instBuying:true  },
  { sym:"EMARTIND",   name:"Electronics Mart India", sector:"Retail",            ipoYear:2022, mcap:5200,  promoter:76.4, promoterStable:true,  pledge:0,   dma20:192,  dma50:180,  dma200:165,  profit3Q:true,  cashflow5Y:true,  pe:28,   roe:17.8, revenueGrowth:22, debtEq:0.2, rsi:55, volAboveAvg:true,  analyst:"Buy",        analystScore:74, cmp:188,  priceTarget:230,  recentUpgrade:true,  instBuying:true  },
  { sym:"APTUS",      name:"Aptus Value Housing",    sector:"Housing Finance",   ipoYear:2021, mcap:9500,  promoter:78.3, promoterStable:true,  pledge:0,   dma20:380,  dma50:355,  dma200:310,  profit3Q:true,  cashflow5Y:true,  pe:22,   roe:19.6, revenueGrowth:25, debtEq:0.8, rsi:60, volAboveAvg:false, analyst:"Outperform", analystScore:76, cmp:375,  priceTarget:440,  recentUpgrade:true,  instBuying:true  },
  { sym:"VERITAS",    name:"Veritas (India)",        sector:"Chemicals",         ipoYear:2020, mcap:1100,  promoter:77.5, promoterStable:true,  pledge:2.1, dma20:285,  dma50:270,  dma200:245,  profit3Q:true,  cashflow5Y:true,  pe:18,   roe:16.3, revenueGrowth:14, debtEq:0.3, rsi:52, volAboveAvg:false, analyst:"Buy",        analystScore:70, cmp:282,  priceTarget:340,  recentUpgrade:false, instBuying:false },
  { sym:"LATENTVIEW", name:"Latent View Analytics",  sector:"Data Analytics",    ipoYear:2021, mcap:5600,  promoter:61.2, promoterStable:true,  pledge:0,   dma20:450,  dma50:420,  dma200:380,  profit3Q:true,  cashflow5Y:true,  pe:42,   roe:20.1, revenueGrowth:28, debtEq:0.0, rsi:57, volAboveAvg:true,  analyst:"Buy",        analystScore:68, cmp:445,  priceTarget:520,  recentUpgrade:false, instBuying:true  },
  { sym:"ROLEX",      name:"Rolex Rings",            sector:"Auto Components",   ipoYear:2021, mcap:3300,  promoter:71.2, promoterStable:true,  pledge:0,   dma20:2100, dma50:1980, dma200:1780, profit3Q:true,  cashflow5Y:true,  pe:25,   roe:23.5, revenueGrowth:17, debtEq:0.4, rsi:61, volAboveAvg:true,  analyst:"Buy",        analystScore:71, cmp:2050, priceTarget:2500, recentUpgrade:true,  instBuying:true  },
  { sym:"HARSHA",     name:"Harsha Engineers",       sector:"Engineering",       ipoYear:2022, mcap:4600,  promoter:59.8, promoterStable:true,  pledge:0,   dma20:810,  dma50:770,  dma200:690,  profit3Q:true,  cashflow5Y:true,  pe:32,   roe:15.4, revenueGrowth:21, debtEq:0.5, rsi:54, volAboveAvg:false, analyst:"Buy",        analystScore:66, cmp:800,  priceTarget:960,  recentUpgrade:false, instBuying:false },
  { sym:"CLEAN",      name:"Clean Science",          sector:"Specialty Chem",    ipoYear:2021, mcap:11200, promoter:67.4, promoterStable:true,  pledge:0,   dma20:1420, dma50:1380, dma200:1300, profit3Q:true,  cashflow5Y:true,  pe:45,   roe:28.4, revenueGrowth:8,  debtEq:0.0, rsi:48, volAboveAvg:false, analyst:"Hold",       analystScore:51, cmp:1395, priceTarget:1480, recentUpgrade:false, instBuying:false },
  { sym:"AMI",        name:"Ami Organics",           sector:"Pharma Chem",       ipoYear:2021, mcap:4800,  promoter:52.4, promoterStable:true,  pledge:0,   dma20:1550, dma50:1480, dma200:1350, profit3Q:true,  cashflow5Y:true,  pe:36,   roe:17.9, revenueGrowth:24, debtEq:0.3, rsi:63, volAboveAvg:true,  analyst:"Outperform", analystScore:69, cmp:1520, priceTarget:1900, recentUpgrade:true,  instBuying:true  },
  { sym:"DEVYANI",    name:"Devyani International",  sector:"QSR",               ipoYear:2021, mcap:13500, promoter:65.7, promoterStable:true,  pledge:0,   dma20:185,  dma50:172,  dma200:158,  profit3Q:false, cashflow5Y:true,  pe:110,  roe:12.1, revenueGrowth:16, debtEq:1.2, rsi:44, volAboveAvg:false, analyst:"Hold",       analystScore:48, cmp:182,  priceTarget:195,  recentUpgrade:false, instBuying:false },
  { sym:"NAZARA",     name:"Nazara Technologies",    sector:"Gaming",            ipoYear:2021, mcap:8300,  promoter:22.6, promoterStable:false, pledge:0,   dma20:990,  dma50:950,  dma200:880,  profit3Q:false, cashflow5Y:false, pe:null, roe:8.2,  revenueGrowth:30, debtEq:0.1, rsi:41, volAboveAvg:false, analyst:"Neutral",    analystScore:42, cmp:965,  priceTarget:1050, recentUpgrade:false, instBuying:false },
  { sym:"FUSION",     name:"Fusion Finance",         sector:"NBFC",              ipoYear:2022, mcap:3800,  promoter:38.9, promoterStable:false, pledge:0,   dma20:340,  dma50:380,  dma200:420,  profit3Q:false, cashflow5Y:false, pe:8,    roe:6.1,  revenueGrowth:5,  debtEq:4.2, rsi:38, volAboveAvg:false, analyst:"Hold",       analystScore:35, cmp:335,  priceTarget:null, recentUpgrade:false, instBuying:false },
  { sym:"VENUS",      name:"Venus Pipes",            sector:"Capital Goods",     ipoYear:2022, mcap:2700,  promoter:62.1, promoterStable:true,  pledge:1.5, dma20:1450, dma50:1380, dma200:1200, profit3Q:true,  cashflow5Y:true,  pe:28,   roe:21.3, revenueGrowth:19, debtEq:0.4, rsi:59, volAboveAvg:true,  analyst:"Outperform", analystScore:64, cmp:1420, priceTarget:1700, recentUpgrade:false, instBuying:true  },
]