'use client'
import { useState, useMemo, useEffect, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import FilterPanel from '../../components/FilterPanel'
import StockTable from '../../components/StockTable'
import { stocks as demoStocks } from '../../lib/stockData'
import { runScreener, defaultFilters, Filters } from '../../lib/screenerEngine'

function ScreenerContent() {
  const searchParams = useSearchParams()

  const [filters, setFilters] = useState<Filters>(() => {
    if (typeof window !== 'undefined') {
      const saved = sessionStorage.getItem('equiscan_filters')
      if (saved) {
        try { return { ...defaultFilters, ...JSON.parse(saved) } }
        catch {}
      }
      const fromUrl = searchParams.get('filters')
      if (fromUrl) {
        try { return { ...defaultFilters, ...JSON.parse(atob(fromUrl)) } }
        catch {}
      }
    }
    return defaultFilters
  })

  const [isLive, setIsLive] = useState(() => {
    if (typeof window === 'undefined') return false
    return !!sessionStorage.getItem('equiscan_live_data')
  })

  const [loading, setLoading] = useState(false)

  const [liveData, setLiveData] = useState<any[]>(() => {
    if (typeof window === 'undefined') return []
    try {
      const cached = sessionStorage.getItem('equiscan_live_data')
      return cached ? JSON.parse(cached) : []
    } catch { return [] }
  })

  const [error, setError] = useState<string | null>(null)

  const [search, setSearch] = useState(() => {
    if (typeof window !== 'undefined') {
      return sessionStorage.getItem('equiscan_search') || searchParams.get('q') || ''
    }
    return searchParams.get('q') || ''
  })

  const [sectorFilter, setSectorFilter] = useState(() => {
    if (typeof window !== 'undefined') {
      return sessionStorage.getItem('equiscan_sector') || searchParams.get('sector') || 'All'
    }
    return searchParams.get('sector') || 'All'
  })

  const demoResults = useMemo(() => runScreener(demoStocks, filters), [filters])
  const liveResults = useMemo(() => {
    if (!liveData.length) return []
    return runScreener(liveData as any, filters)
  }, [liveData, filters])

  const allResults = isLive ? liveResults : demoResults
  const sectors = ['All', ...Array.from(new Set(allResults.map(r => r.stock.sector).filter(Boolean))).sort()]

  const results = allResults.filter(r => {
    const matchSearch = !search ||
      r.stock.name?.toLowerCase().includes(search.toLowerCase()) ||
      r.stock.sym?.toLowerCase().includes(search.toLowerCase()) ||
      r.stock.sector?.toLowerCase().includes(search.toLowerCase())
    const matchSector = sectorFilter === 'All' || r.stock.sector === sectorFilter
    return matchSearch && matchSector
  })

  const passed      = results.filter(r => r.passed)
  const activeCount = Object.keys(filters).filter(
    k => k.startsWith('f_') && filters[k as keyof Filters] === true
  ).length
  const avgScore = passed.length > 0
    ? (passed.reduce((s, r) => s + r.score, 0) / passed.length).toFixed(1)
    : '—'

  // Save filters + search + sector to sessionStorage and URL
  useEffect(() => {
    sessionStorage.setItem('equiscan_filters', JSON.stringify(filters))
    sessionStorage.setItem('equiscan_search', search)
    sessionStorage.setItem('equiscan_sector', sectorFilter)

    const params = new URLSearchParams()
    const activeOnly: Record<string, any> = {}
    Object.keys(filters).forEach(k => {
      const key = k as keyof Filters
      if (filters[key] !== defaultFilters[key]) {
        activeOnly[key] = filters[key]
      }
    })
    if (Object.keys(activeOnly).length > 0) {
      params.set('filters', btoa(JSON.stringify(activeOnly)))
    }
    if (search) params.set('q', search)
    if (sectorFilter !== 'All') params.set('sector', sectorFilter)
    const newUrl = params.toString() ? `/screener?${params.toString()}` : '/screener'
    window.history.replaceState(null, '', newUrl)
  }, [filters, search, sectorFilter])

  const loadLiveData = async () => {
    setLoading(true)
    setError(null)
    try {
      const res  = await fetch('http://localhost:8000/api/stocks?limit=504')
      const data = await res.json()
      const { mapLiveToStock } = await import('../../lib/api')
      const { stocks: demo }   = await import('../../lib/stockData')
      const mapped = data.stocks.map((live: any) => {
        const demoStock = demo.find(d => d.sym === live.symbol) || {}
        return {
          ...demoStock,
          ...mapLiveToStock(live),
          name:   live.name   || (demoStock as any).name   || live.symbol,
          sector: live.sector || (demoStock as any).sector || 'Unknown',
        }
      })
      setLiveData(mapped)
      setIsLive(true)
      sessionStorage.setItem('equiscan_live_data', JSON.stringify(mapped))
    } catch (e) {
      setError('Could not connect to backend.')
      setIsLive(false)
    } finally {
      setLoading(false)
    }
  }

  // Only fetch if not cached
  useEffect(() => {
    const cached = sessionStorage.getItem('equiscan_live_data')
    if (!cached) {
      loadLiveData()
    }
  }, [])

  return (
    <div className="max-w-screen-2xl mx-auto px-6 py-8">

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-white tracking-tight">Stock Screener</h1>
          <p className="text-white/40 text-sm mt-1 font-mono">
             NSE · BSE · 25-factor multi-criteria filter engine
          </p>
        </div>
        <div className="flex items-center gap-3">
          {error && <span className="text-xs text-red-400 font-mono">{error}</span>}
          <div className={`flex items-center gap-2 text-xs font-mono px-3 py-1.5 rounded-full border ${
            isLive
              ? 'bg-green-500/10 text-green-400 border-green-500/20'
              : 'bg-white/5 text-white/30 border-white/10'
          }`}>
            <div className={`w-1.5 h-1.5 rounded-full ${isLive ? 'bg-green-400 animate-pulse' : 'bg-white/20'}`} />
            {isLive ? 'Live Data' : 'Demo Mode'}
          </div>
          <button
            onClick={loadLiveData}
            disabled={loading}
            className="bg-blue-500 hover:bg-blue-600 disabled:opacity-50 transition-colors text-white text-sm font-medium px-4 py-1.5 rounded-lg"
          >
            {loading ? 'Loading...' : isLive ? '↺ Refresh' : '⚡ Load Live Data'}
          </button>
        </div>
      </div>

      {/* Search bar */}
      <div className="relative mb-4">
        <div className="absolute left-4 top-1/2 -translate-y-1/2 text-white/20 text-sm">⌕</div>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search by company, symbol or sector..."
          className="w-full bg-[#0f1218] border border-white/[0.07] rounded-xl pl-10 pr-4 py-3 text-sm text-white font-mono placeholder-white/20 outline-none focus:border-blue-500/40 transition-all"
        />
        {search && (
          <button
            onClick={() => setSearch('')}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-white/20 hover:text-white/60 transition-colors"
          >×</button>
        )}
      </div>

      {/* Sector filter */}
      <div className="flex gap-2 flex-wrap mb-6">
        {sectors.slice(0, 12).map(sector => (
          <button
            key={sector}
            onClick={() => setSectorFilter(sector)}
            className={`text-xs font-mono px-3 py-1.5 rounded-lg border transition-all ${
              sectorFilter === sector
                ? 'bg-blue-500/20 text-blue-400 border-blue-500/30'
                : 'text-white/30 border-white/[0.07] hover:text-white/60 hover:border-white/20'
            }`}
          >
            {sector}
          </button>
        ))}
        {sectors.length > 12 && (
          <select
            value={sectorFilter}
            onChange={e => setSectorFilter(e.target.value)}
            className="text-xs font-mono px-3 py-1.5 rounded-lg border border-white/[0.07] bg-[#0f1218] text-white/30 outline-none"
          >
            {sectors.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        )}
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {[
          { label: 'Universe',       value: results.length.toLocaleString() },
          { label: 'Passed Filters', value: passed.length.toString(), green: true },
          { label: 'Active Filters', value: activeCount.toString() },
          { label: 'Avg Score',      value: avgScore === '—' ? '—' : `${avgScore}/18` },
        ].map((stat) => (
          <div key={stat.label} className="bg-[#0f1218] border border-white/[0.07] rounded-xl p-4">
            <div className={`text-2xl font-mono font-semibold ${stat.green ? 'text-green-400' : 'text-white'}`}>
              {stat.value}
            </div>
            <div className="text-xs text-white/30 uppercase tracking-wider mt-1 font-mono">
              {stat.label}
            </div>
          </div>
        ))}
      </div>

      {/* Loading state */}
      {loading && (
        <div className="bg-[#0f1218] border border-white/[0.07] rounded-xl p-16 text-center mb-6">
          <div className="text-white/40 text-sm font-mono animate-pulse">
            Fetching live data from Kite + Screener.in...
          </div>
          <div className="text-white/20 text-xs mt-2 font-mono">
            This may take 20-30 seconds for all stocks
          </div>
        </div>
      )}

      {/* Main layout */}
      {!loading && (
        <div className="grid grid-cols-[280px_1fr] gap-6 items-start">
          <FilterPanel filters={filters} onChange={setFilters} />
          <StockTable results={results} />
        </div>
      )}

    </div>
  )
}

export default function ScreenerPage() {
  return (
    <Suspense fallback={
      <div className="max-w-screen-2xl mx-auto px-6 py-8">
        <div className="text-white/40 font-mono animate-pulse">Loading screener...</div>
      </div>
    }>
      <ScreenerContent />
    </Suspense>
  )
}