'use client'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { stocks, mapApiStock, Stock } from '../../../lib/stockData'
import { runScreener, defaultFilters } from '../../../lib/screenerEngine'
import { getWatchlist, addToWatchlist, removeFromWatchlist, isInWatchlist } from '../../../lib/watchlist'

const API = 'http://localhost:8000'

// FIX: added 'Strong Buy' — falls through to red Sell style without this
const analystSignalColor: Record<string, string> = {
  'Strong Buy':  'bg-green-500/20 text-green-300 border-green-500/30',
  'Buy':         'bg-green-500/10 text-green-400 border-green-500/20',
  'Outperform':  'bg-blue-500/10 text-blue-400 border-blue-500/20',
  'Hold':        'bg-amber-500/10 text-amber-400 border-amber-500/20',
  'Neutral':     'bg-white/5 text-white/30 border-white/10',
  'Underperform':'bg-orange-500/10 text-orange-400 border-orange-500/20',
  'Sell':        'bg-red-500/10 text-red-400 border-red-500/20',
}

// FIX: updated key from f_cashflow5Q → f_cashflow5Y to match screenerEngine rename
const criteriaLabels: Record<string, string> = {
  f_listed8y:            'Listed ≥ 8 years',
  f_mcap1000:            'Market Cap > ₹1000 Cr',
  f_promoter75:          'Promoter > 75%',
  f_noDilution:          'No promoter dilution (QoQ)',
  f_dmaAligned:          '20 DMA > 50 > 200 DMA',
  f_dma50_200:           '50 DMA > 200 DMA',
  f_profit3Q:            'Profit — last 3 quarters',
  f_cashflow5Y:          'Positive cash flow (5 years)',   // FIX: was f_cashflow5Q
  f_analystPositive:     'Analyst: Buy / Outperform',
  f_pledge5:             'Pledge < 5%',
  f_rsiHealthy:          'RSI 40–70',
  f_peUnder60:           'P/E < 60',
  f_revenueGrowth15:     'Revenue growth > 15%',
  f_debtLow:             'Debt/Equity < 0.5',
  f_roe15:               'ROE > 15%',
  f_recentUpgrade:       'Recent analyst upgrade (30D)',
  f_priceTargetUpside20: 'Price target upside > 20%',
  f_instBuying:          'Institutional buying (QoQ)',
  f_epsIncreasing:       'EPS increasing (3Q)',
  f_near52wHigh:         'Near 52W High (within 10%)',
}

// FIX: returns null instead of 0 when data is insufficient — avoids showing
// a misleading +0.00% RS when the history array is shorter than the period
function calcReturn(data: { close: number }[], period: number): number | null {
  if (data.length < period) return null
  const start = data[data.length - period]?.close
  const end   = data[data.length - 1]?.close
  if (!start || !end) return null
  return ((end - start) / start) * 100
}

function formatRs(val: number | null): string {
  if (val === null) return 'N/A'
  return `${val > 0 ? '+' : ''}${val.toFixed(1)}%`
}

export default function StockDetailPage() {
  const params = useParams()
  const symbol = (params.symbol as string)?.toUpperCase()

  const [history,      setHistory]      = useState<any[]>([])
  const [liveData,     setLiveData]     = useState<Record<string, unknown> | null>(null)
  const [quantData,    setQuantData]    = useState<any>(null)
  const [loading,      setLoading]      = useState(true)
  const [days,         setDays]         = useState(365)
  const [niftyHistory, setNiftyHistory] = useState<any[]>([])
  const [volumeData,   setVolumeData]   = useState<any>(null)
  const [inWatchlist,  setInWatchlist]  = useState(false)

  const demoStock  = stocks.find(s => s.sym === symbol) ?? null
  // FIX: use mapApiStock to build the Stock object from live data —
  // replaces the manual object that was out of sync with stockData.ts
  // (had stale cashflow_5q, hardcoded priceTarget: 0, ipoYear: 2020 default)
  const mappedLive: Stock | null = liveData ? mapApiStock(liveData) : null
  const stock = mappedLive ?? demoStock

  useEffect(() => {
    setInWatchlist(isInWatchlist(symbol))
  }, [symbol])

  const toggleWatchlist = () => {
    if (inWatchlist) {
      removeFromWatchlist(symbol)
      setInWatchlist(false)
    } else {
      addToWatchlist(symbol)
      setInWatchlist(true)
    }
  }

  useEffect(() => {
    async function load() {
      setLoading(true)

      // FIX: Promise.allSettled instead of Promise.all — a single failed
      // fetch (e.g. volume endpoint down) no longer kills all data on the page
      const [histRes, liveRes, techRes, niftyRes, volRes, quantRes] =
        await Promise.allSettled([
          fetch(`${API}/api/stock/${symbol}/history?days=${days}`),
          fetch(`${API}/api/stock/${symbol}/fresh`),
          fetch(`${API}/api/stock/${symbol}/technical`),
          fetch(`${API}/api/nifty/history?days=${days}`),
          fetch(`${API}/api/stock/${symbol}/volume`),
          // FIX: fetch the quant endpoint — liveData.quant_signals never
          // existed on the technical endpoint so the section never rendered
          fetch(`${API}/api/stock/${symbol}/quant`),
        ])

      try {
        if (histRes.status === 'fulfilled') {
          const d = await histRes.value.json()
          setHistory(d.data || [])
        }
      } catch (e) { console.error('history fetch failed', e) }

      try {
        const liveJson = liveRes.status  === 'fulfilled' ? await liveRes.value.json()  : {}
        const techJson = techRes.status  === 'fulfilled' ? await techRes.value.json()  : {}
        if (liveJson || techJson) setLiveData({ ...liveJson, ...techJson })
      } catch (e) { console.error('live/tech fetch failed', e) }

      try {
        if (niftyRes.status === 'fulfilled') {
          const d = await niftyRes.value.json()
          setNiftyHistory(d.data || [])
        }
      } catch (e) { console.error('nifty fetch failed', e) }

      try {
        if (volRes.status === 'fulfilled') {
          setVolumeData(await volRes.value.json())
        }
      } catch (e) { console.error('volume fetch failed', e) }

      try {
        if (quantRes.status === 'fulfilled') {
          setQuantData(await quantRes.value.json())
        }
      } catch (e) { console.error('quant fetch failed', e) }

      setLoading(false)
    }
    load()
  }, [symbol, days])

  if (!stock) {
    return (
      <div className="max-w-screen-xl mx-auto px-6 py-16 text-center">
        <div className="text-4xl mb-4">⊘</div>
        <div className="text-white/40">Stock not found</div>
        <Link href="/screener" className="text-blue-400 text-sm mt-4 inline-block">← Back to Screener</Link>
      </div>
    )
  }

  // FIX: use mappedLive (via mapApiStock) for screener — replaces the manual
  // inline object that was missing cashflow5Y, had priceTarget:0, ipoYear:2020
  const stockForScreener: Stock | null = mappedLive ?? demoStock
  const demoResult = stockForScreener
    ? runScreener([stockForScreener], defaultFilters)[0]
    : null

  const cmp = stock.cmp ?? 0

  // FIX: price target from mapped live data, not hardcoded 0 or mock demoStock
  const target: number | null = mappedLive?.priceTarget ?? demoStock?.priceTarget ?? null
  const upside: number | null =
    target !== null && cmp > 0
      ? ((target - cmp) / cmp) * 100
      : null

  const maxDma = Math.max(stock.dma20 ?? 0, stock.dma50 ?? 0, stock.dma200 ?? 0)

  const firstClose    = history[0]?.close ?? 0
  const lastClose     = history[history.length - 1]?.close ?? 0
  const chartChange   = firstClose ? (((lastClose - firstClose) / firstClose) * 100).toFixed(1) : '0'
  const chartPositive = parseFloat(chartChange) >= 0

  const high52w = history.length > 0 ? Math.max(...history.map((h: any) => h.high)) : 0
  const low52w  = history.length > 0 ? Math.min(...history.map((h: any) => h.low))  : 0
  const pctFrom52wHigh = high52w && cmp
    ? (((cmp - high52w) / high52w) * 100).toFixed(1)
    : null

  const rs1M    = calcReturn(history, 21)  !== null && calcReturn(niftyHistory, 21)  !== null ? (calcReturn(history, 21)!  - calcReturn(niftyHistory, 21)!).toFixed(1)  : null
  const rs3M    = calcReturn(history, 63)  !== null && calcReturn(niftyHistory, 63)  !== null ? (calcReturn(history, 63)!  - calcReturn(niftyHistory, 63)!).toFixed(1)  : null
  const rs6M    = calcReturn(history, 126) !== null && calcReturn(niftyHistory, 126) !== null ? (calcReturn(history, 126)! - calcReturn(niftyHistory, 126)!).toFixed(1) : null

  const rsVals  = [rs1M, rs3M, rs6M].filter(v => v !== null).map(v => parseFloat(v!))
  const rsScore = rsVals.length > 0
    ? (rsVals.reduce((a, b) => a + b, 0) / rsVals.length).toFixed(1)
    : null

  // FIX: ipoYear null guard — avoids rendering "Listed null" in header
  const ipoYearDisplay = (liveData?.ipo_year as number | null) ?? demoStock?.ipoYear
  const analystConsensus = (liveData?.analyst as string) ?? demoStock?.analyst ?? '—'

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload?.length) {
      return (
        <div className="bg-[#1c2330] border border-white/10 rounded-lg px-3 py-2">
          <div className="text-xs text-white/40 font-mono mb-1">{label}</div>
          <div className="text-sm font-mono text-white font-semibold">₹{payload[0].value.toFixed(1)}</div>
        </div>
      )
    }
    return null
  }

  return (
    <div className="max-w-screen-xl mx-auto px-6 py-8">

      {/* Back */}
      <Link href="/screener" className="text-white/30 text-sm font-mono hover:text-white/60 transition-colors mb-6 inline-block">
        ← Back to Screener
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-3xl font-semibold text-white tracking-tight">
            {stock.name}
          </h1>
          <div className="text-white/30 font-mono text-sm mt-1">
            {symbol} · {stock.sector}
            {/* FIX: only render "Listed YYYY" when ipoYear is non-null */}
            {ipoYearDisplay != null ? ` · Listed ${ipoYearDisplay}` : ''}
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-mono font-semibold text-white">
            {cmp ? `₹${cmp.toLocaleString('en-IN')}` : '—'}
          </div>
          {/* FIX: upside uses live mapped priceTarget, not mock demoStock */}
          {upside !== null && target !== null && (
            <div className={`font-mono text-sm ${upside >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              Target ₹{target} ({upside >= 0 ? '+' : ''}{upside.toFixed(1)}%)
            </div>
          )}
          <button
            onClick={toggleWatchlist}
            className={`mt-3 px-4 py-2 rounded-lg text-sm font-medium transition-all border ${
              inWatchlist
                ? 'bg-amber-500/10 text-amber-400 border-amber-500/20 hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/20'
                : 'bg-blue-500/10 text-blue-400 border-blue-500/20 hover:bg-blue-500/20'
            }`}
          >
            {inWatchlist ? '★ In Watchlist' : '☆ Add to Watchlist'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">

        {/* ── LEFT COLUMN ── */}
        <div className="col-span-2 space-y-6">

          {/* Price Chart */}
          <div className="bg-[#0f1218] border border-white/[0.07] rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-xs font-mono text-white/30 uppercase tracking-wider">Price Chart</div>
                <div className={`text-sm font-mono mt-1 ${chartPositive ? 'text-green-400' : 'text-red-400'}`}>
                  {chartPositive ? '+' : ''}{chartChange}% over {days} days
                </div>
              </div>
              <div className="flex gap-2">
                {[30, 90, 180, 365].map(d => (
                  <button key={d} onClick={() => setDays(d)}
                    className={`text-xs font-mono px-3 py-1 rounded-lg transition-all ${
                      days === d
                        ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                        : 'text-white/30 border border-white/10 hover:text-white/60'
                    }`}>{d}D</button>
                ))}
              </div>
            </div>
            {loading ? (
              <div className="h-48 flex items-center justify-center text-white/20 font-mono text-sm animate-pulse">Loading chart...</div>
            ) : history.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={history} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                  <XAxis dataKey="date" tick={{ fill: '#4d5566', fontSize: 10, fontFamily: 'monospace' }} tickLine={false} axisLine={false} interval={Math.floor(history.length / 5)} tickFormatter={d => d.slice(5)} />
                  <YAxis tick={{ fill: '#4d5566', fontSize: 10, fontFamily: 'monospace' }} tickLine={false} axisLine={false} domain={['auto', 'auto']} tickFormatter={v => `₹${v}`} width={60} />
                  <Tooltip content={<CustomTooltip />} />
                  <Line type="monotone" dataKey="close" stroke={chartPositive ? '#22c55e' : '#ef4444'} strokeWidth={2} dot={false} activeDot={{ r: 4, fill: chartPositive ? '#22c55e' : '#ef4444' }} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-48 flex items-center justify-center text-white/20 font-mono text-sm">No chart data available</div>
            )}
          </div>

          {/* Key Metrics */}
          <div className="bg-[#0f1218] border border-white/[0.07] rounded-xl p-5">
            <div className="text-xs font-mono text-white/30 uppercase tracking-wider mb-4">Key Metrics</div>
            <div className="grid grid-cols-4 gap-4">
              {[
                { label: 'Market Cap',  value: stock.mcap ? `₹${stock.mcap.toLocaleString('en-IN')} Cr` : '—' },
                { label: 'Promoter',    value: stock.promoter ? `${stock.promoter.toFixed(1)}%` : '—',    green: (stock.promoter ?? 0) > 75 },
                { label: 'P/E Ratio',   value: stock.pe !== null ? `${stock.pe}x` : 'N/A' },
                { label: 'ROE',         value: stock.roe ? `${stock.roe.toFixed(1)}%` : '—',              green: (stock.roe ?? 0) > 15 },
                { label: 'Rev Growth',  value: stock.revenueGrowth ? `+${stock.revenueGrowth}%` : '—',   green: (stock.revenueGrowth ?? 0) > 15 },
                { label: 'Debt/Equity', value: stock.debtEq !== undefined ? `${stock.debtEq}x` : '—',    green: (stock.debtEq ?? 1) < 0.5 },
                { label: 'RSI',         value: stock.rsi ? stock.rsi.toString() : '—' },
                { label: 'Pledge',      value: `${stock.pledge ?? 0}%`,                                   green: (stock.pledge ?? 0) < 5 },
                { label: '52W High',    value: high52w ? `₹${high52w.toLocaleString('en-IN')}` : '—' },
                { label: '52W Low',     value: low52w  ? `₹${low52w.toLocaleString('en-IN')}`  : '—', green: true },
                { label: 'From 52W H',  value: pctFrom52wHigh !== null ? `${pctFrom52wHigh}%` : '—',     green: pctFrom52wHigh !== null && parseFloat(pctFrom52wHigh) > -10 },
              ].map(m => (
                <div key={m.label} className="bg-[#151a22] rounded-lg p-3">
                  <div className="text-[10px] font-mono text-white/30 uppercase tracking-wider mb-1">{m.label}</div>
                  <div className={`text-lg font-mono font-medium ${(m as any).green ? 'text-green-400' : 'text-white'}`}>{m.value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* DMA Visual */}
          {stock.dma20 != null && stock.dma20 > 0 && (
            <div className="bg-[#0f1218] border border-white/[0.07] rounded-xl p-5">
              <div className="text-xs font-mono text-white/30 uppercase tracking-wider mb-4">Moving Average Analysis</div>
              <div className="space-y-3">
                {[
                  { label: '20 DMA',  value: stock.dma20,  color: 'bg-blue-400' },
                  { label: '50 DMA',  value: stock.dma50,  color: 'bg-purple-400' },
                  { label: '200 DMA', value: stock.dma200, color: 'bg-amber-400' },
                ].map(dma => (
                  <div key={dma.label} className="flex items-center gap-4">
                    <div className="w-16 text-xs font-mono text-white/40">{dma.label}</div>
                    <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${dma.color}`} style={{ width: `${maxDma > 0 ? Math.round((dma.value / maxDma) * 100) : 0}%` }} />
                    </div>
                    <div className="w-24 text-right text-sm font-mono text-white/60">₹{dma.value.toLocaleString('en-IN')}</div>
                  </div>
                ))}
              </div>
              <div className={`mt-4 text-xs font-mono px-3 py-2 rounded-lg ${
                stock.dma20 > stock.dma50 && stock.dma50 > stock.dma200
                  ? 'bg-green-500/10 text-green-400 border border-green-500/20'
                  : 'bg-red-500/10 text-red-400 border border-red-500/20'
              }`}>
                {stock.dma20 > stock.dma50 && stock.dma50 > stock.dma200
                  ? '▲ Fully bullish DMA alignment — 20 > 50 > 200'
                  : '▼ DMA alignment not bullish'}
              </div>
            </div>
          )}

          {/* Relative Strength vs Nifty */}
          <div className="bg-[#0f1218] border border-white/[0.07] rounded-xl p-5">
            <div className="text-xs font-mono text-white/30 uppercase tracking-wider mb-4">Relative Strength vs Nifty 50</div>
            <div className="grid grid-cols-4 gap-4">
              {[
                { label: '1M RS',    value: rs1M    !== null ? rs1M    : null },
                { label: '3M RS',    value: rs3M    !== null ? rs3M    : null },
                { label: '6M RS',    value: rs6M    !== null ? rs6M    : null },
                { label: 'RS Score', value: rsScore !== null ? rsScore : null },
              ].map(rs => (
                <div key={rs.label} className="bg-[#151a22] rounded-lg p-3">
                  <div className="text-[10px] font-mono text-white/30 uppercase tracking-wider mb-1">{rs.label}</div>
                  <div className={`text-lg font-mono font-semibold ${
                    rs.value === null           ? 'text-white/20'
                    : parseFloat(rs.value) > 0 ? 'text-green-400'
                    : 'text-red-400'
                  }`}>
                    {/* FIX: show N/A when history too short, not misleading +0.00% */}
                    {rs.value === null ? 'N/A' : `${parseFloat(rs.value) > 0 ? '+' : ''}${rs.value}%`}
                  </div>
                </div>
              ))}
            </div>
            {rsScore !== null && (
              <div className={`mt-4 text-xs font-mono px-3 py-2 rounded-lg ${
                parseFloat(rsScore) > 0
                  ? 'bg-green-500/10 text-green-400 border border-green-500/20'
                  : 'bg-red-500/10 text-red-400 border border-red-500/20'
              }`}>
                {parseFloat(rsScore) > 0
                  ? `▲ Outperforming Nifty 50 by ${rsScore}% on average`
                  : `▼ Underperforming Nifty 50 by ${Math.abs(parseFloat(rsScore))}% on average`}
              </div>
            )}
          </div>

          {/* Volume Analysis */}
          {volumeData && (
            <div className="bg-[#0f1218] border border-white/[0.07] rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="text-xs font-mono text-white/30 uppercase tracking-wider">Volume Analysis</div>
                <span className={`text-xs font-mono px-2 py-1 rounded-full border ${
                  volumeData.spike_level === 'extreme' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                  volumeData.spike_level === 'high'    ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
                  'bg-white/5 text-white/30 border-white/10'
                }`}>
                  {volumeData.spike_level === 'extreme' ? '🔥 Extreme Spike' :
                   volumeData.spike_level === 'high'    ? '⚡ Volume Spike'  : '• Normal Volume'}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="bg-[#151a22] rounded-lg p-3">
                  <div className="text-[10px] font-mono text-white/30 uppercase tracking-wider mb-1">Today's Volume</div>
                  <div className="text-base font-mono font-medium text-white">{(volumeData.last_volume / 100000).toFixed(2)}L</div>
                </div>
                <div className="bg-[#151a22] rounded-lg p-3">
                  <div className="text-[10px] font-mono text-white/30 uppercase tracking-wider mb-1">20D Avg Volume</div>
                  <div className="text-base font-mono font-medium text-white">{(volumeData.avg_volume_20 / 100000).toFixed(2)}L</div>
                </div>
                <div className="bg-[#151a22] rounded-lg p-3">
                  <div className="text-[10px] font-mono text-white/30 uppercase tracking-wider mb-1">Vol Ratio</div>
                  <div className={`text-base font-mono font-medium ${volumeData.vol_ratio >= 2 ? 'text-amber-400' : 'text-white'}`}>{volumeData.vol_ratio}x</div>
                </div>
              </div>
              <div className="space-y-1">
                {volumeData.data?.slice(-15).map((d: any) => {
                  const maxVol = Math.max(...volumeData.data.map((x: any) => x.volume))
                  const pct    = Math.round((d.volume / maxVol) * 100)
                  const isHigh = d.volume > volumeData.avg_volume_20 * 1.5
                  return (
                    <div key={d.date} className="flex items-center gap-3">
                      <div className="w-12 text-[10px] font-mono text-white/30">{d.date.slice(5)}</div>
                      <div className="flex-1 h-3 bg-white/5 rounded-sm overflow-hidden">
                        <div className={`h-full rounded-sm ${isHigh ? 'bg-amber-400' : 'bg-blue-400/40'}`} style={{ width: `${pct}%` }} />
                      </div>
                      <div className="w-16 text-right text-[10px] font-mono text-white/30">{(d.volume / 100000).toFixed(1)}L</div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Quant Signal Engine */}
          {/* FIX: now reads from quantData (fetched from /api/stock/{sym}/quant)
              instead of liveData.quant_signals which never existed on the
              technical endpoint — this section was permanently hidden before */}
          {quantData && !quantData.error && (
            <div className="bg-[#0f1218] border border-white/[0.07] rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="text-xs font-mono text-white/30 uppercase tracking-wider">Quant Signal Engine</div>
                <span className={`text-sm font-mono font-semibold px-3 py-1 rounded-full border ${
                  analystSignalColor[quantData.signal] ?? analystSignalColor['Neutral']
                }`}>
                  {quantData.signal} · {quantData.score}/100
                </span>
              </div>
              <div className="mb-4">
                <div className="flex justify-between text-xs font-mono text-white/30 mb-1">
                  <span>Sell</span><span>Hold</span><span>Buy</span>
                </div>
                <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full transition-all ${
                    quantData.score >= 70 ? 'bg-green-400' :
                    quantData.score >= 55 ? 'bg-blue-400'  :
                    quantData.score >= 40 ? 'bg-amber-400' : 'bg-red-400'
                  }`} style={{ width: `${quantData.score}%` }} />
                </div>
              </div>
              {quantData.signals?.length > 0 && (
                <div className="space-y-2">
                  {quantData.signals.map((sig: [string, string, string], i: number) => (
                    <div key={i} className="flex items-center justify-between py-1.5 border-b border-white/[0.04]">
                      <span className="text-xs text-white/50">{sig[0]}</span>
                      <span className={`text-xs font-mono font-semibold ${
                        sig[2] === 'green' ? 'text-green-400' :
                        sig[2] === 'amber' ? 'text-amber-400' : 'text-red-400'
                      }`}>{sig[1]}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

        </div>

        {/* ── RIGHT COLUMN ── */}
        <div className="space-y-6">

          {/* All Criteria */}
          <div className="bg-[#0f1218] border border-white/[0.07] rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="text-xs font-mono text-white/30 uppercase tracking-wider">All Criteria</div>
              {demoResult && (
                <div className="text-sm font-mono font-semibold text-blue-400">
                  {demoResult.score}/{demoResult.maxScore}
                </div>
              )}
            </div>
            {demoResult ? (
              <div className="space-y-1">
                {Object.entries(demoResult.checks).map(([key, pass]) => (
                  <div key={key} className="flex items-center justify-between py-2 border-b border-white/[0.04]">
                    <div className="text-xs text-white/50">
                      {criteriaLabels[key] ?? key}
                    </div>
                    <span className={`text-xs font-mono ${pass ? 'text-green-400' : 'text-red-400/50'}`}>
                      {pass ? '✓' : '✗'}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-white/20 text-xs font-mono">No criteria data</div>
            )}
          </div>

          {/* Analyst */}
          <div className="bg-[#0f1218] border border-white/[0.07] rounded-xl p-5">
            <div className="text-xs font-mono text-white/30 uppercase tracking-wider mb-3">Analyst</div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-white/60">Consensus</span>
              <span className={`text-sm font-mono font-semibold ${
                analystSignalColor[analystConsensus]
                  ? analystConsensus === 'Strong Buy' || analystConsensus === 'Buy' || analystConsensus === 'Outperform'
                    ? 'text-green-400'
                    : analystConsensus === 'Underperform' || analystConsensus === 'Sell'
                    ? 'text-red-400'
                    : 'text-amber-400'
                  : 'text-white/60'
              }`}>
                {analystConsensus}
              </span>
            </div>
            <div className="flex items-center justify-between mt-2">
              <span className="text-sm text-white/60">Score</span>
              <span className="text-sm font-mono text-white/60">
                {stock.analystScore ?? '—'}/100
              </span>
            </div>
            {stock.trendlyneAvailable === false && (
              <div className="mt-3 text-[10px] font-mono text-white/20 border border-white/[0.06] rounded-lg px-2 py-1.5">
                ⚠ Analyst data unavailable
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  )
}