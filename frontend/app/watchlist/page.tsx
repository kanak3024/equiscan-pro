'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { getWatchlist, removeFromWatchlist } from '../../lib/watchlist'

export default function WatchlistPage() {
  const router = useRouter()
  const [watchlist, setWatchlist] = useState<string[]>([])
  const [stocks, setStocks] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const symbols = getWatchlist()
    setWatchlist(symbols)
    if (symbols.length === 0) {
      setLoading(false)
      return
    }
    // Fetch live data for watchlisted stocks
    fetch(`http://localhost:8000/api/stocks?limit=504`)
      .then(r => r.json())
      .then(data => {
        const filtered = data.stocks.filter((s: any) =>
          symbols.includes(s.symbol)
        )
        setStocks(filtered)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  const remove = (symbol: string) => {
    removeFromWatchlist(symbol)
    setWatchlist(prev => prev.filter(s => s !== symbol))
    setStocks(prev => prev.filter(s => s.symbol !== symbol))
  }

  return (
    <div className="max-w-screen-xl mx-auto px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-white tracking-tight">Watchlist</h1>
        <p className="text-white/40 text-sm mt-1 font-mono">
          Track your selected stocks · {watchlist.length} stocks
        </p>
      </div>

      {loading && (
        <div className="text-white/30 font-mono text-sm animate-pulse">Loading...</div>
      )}

      {!loading && watchlist.length === 0 && (
        <div className="bg-[#0f1218] border border-white/[0.07] rounded-xl p-16 text-center">
          <div className="text-4xl mb-4">☆</div>
          <div className="text-white/40 text-sm">Your watchlist is empty</div>
          <div className="text-white/20 text-xs mt-1 font-mono">
            Open any stock and click "Add to Watchlist"
          </div>
          <button
            onClick={() => router.push('/screener')}
            className="mt-4 px-4 py-2 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-lg text-sm"
          >
            Go to Screener →
          </button>
        </div>
      )}

      {!loading && watchlist.length > 0 && stocks.length === 0 && (
        <div className="text-white/30 font-mono text-sm">
          Could not load stock data. Make sure the backend is running.
        </div>
      )}

      <div className="grid grid-cols-1 gap-3">
        {stocks.map(s => {
          const cmp    = s.cmp || 0
          const target = s.price_target || 0
          const upside = target && cmp ? (((target - cmp) / cmp) * 100).toFixed(1) : null
          const analystColor =
            s.analyst === 'Buy'        ? 'text-green-400' :
            s.analyst === 'Outperform' ? 'text-blue-400'  : 'text-amber-400'

          return (
            <div
              key={s.symbol}
              className="bg-[#0f1218] border border-white/[0.07] rounded-xl p-5 flex items-center justify-between hover:border-white/10 transition-all cursor-pointer"
              onClick={() => router.push(`/stock/${s.symbol}`)}
            >
              {/* Left */}
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 text-blue-300 flex items-center justify-center text-xs font-bold font-mono">
                  {s.symbol.slice(0, 2)}
                </div>
                <div>
                  <div className="text-white font-medium">{s.name}</div>
                  <div className="text-white/30 text-xs font-mono mt-0.5">{s.symbol} · {s.sector}</div>
                </div>
              </div>

              {/* Stats */}
              <div className="flex items-center gap-10">
                <div className="text-center min-w-[70px]">
                  <div className="text-white font-mono text-sm">₹{cmp.toLocaleString('en-IN')}</div>
                  <div className="text-white/30 text-[10px] font-mono uppercase">CMP</div>
                </div>
                {upside && (
                  <div className="text-center min-w-[70px]">
                    <div className="text-green-400 font-mono text-sm">+{upside}%</div>
                    <div className="text-white/30 text-[10px] font-mono uppercase">Upside</div>
                  </div>
                )}
                <div className="text-center min-w-[80px]">
                  <div className={`font-mono text-sm ${analystColor}`}>{s.analyst || 'Hold'}</div>
                  <div className="text-white/30 text-[10px] font-mono uppercase">Analyst</div>
                </div>
                <div className="text-center min-w-[70px]">
                  <div className={`font-mono text-sm ${s.promoter > 75 ? 'text-green-400' : 'text-white'}`}>
                    {s.promoter?.toFixed(1)}%
                  </div>
                  <div className="text-white/30 text-[10px] font-mono uppercase">Promoter</div>
                </div>
                <div className="text-center min-w-[60px]">
                  <div className="text-white font-mono text-sm">{s.pe ? `${s.pe}x` : 'N/A'}</div>
                  <div className="text-white/30 text-[10px] font-mono uppercase">P/E</div>
                </div>
              </div>

              {/* Remove */}
              <button
                onClick={(e) => { e.stopPropagation(); remove(s.symbol) }}
                className="text-white/20 hover:text-red-400 transition-colors text-lg px-3"
              >
                ×
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}