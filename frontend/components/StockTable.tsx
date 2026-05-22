'use client'
import { useRouter } from 'next/navigation'
import { StockResult } from '../lib/screenerEngine'

type Props = {
  results: StockResult[]
}

const analystColor: Record<string, string> = {
  Buy:        'bg-green-500/10 text-green-400 border-green-500/20',
  Outperform: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  Hold:       'bg-amber-500/10 text-amber-400 border-amber-500/20',
  Neutral:    'bg-white/5 text-white/30 border-white/10',
  Sell:       'bg-red-500/10 text-red-400 border-red-500/20',
}

const sectorColors = [
  'bg-blue-500/10 text-blue-300',
  'bg-purple-500/10 text-purple-300',
  'bg-teal-500/10 text-teal-300',
  'bg-amber-500/10 text-amber-300',
  'bg-green-500/10 text-green-300',
  'bg-pink-500/10 text-pink-300',
]

export default function StockTable({ results }: Props) {
  const router = useRouter()

  const passed = results.filter(r => r.passed)
  const activeFilters = results.length > 0 && results.some(r => !r.passed)

  if (passed.length === 0) {
    return (
      <div className="bg-[#0f1218] border border-white/[0.07] rounded-xl p-12 text-center">
        <div className="text-4xl mb-3">⊘</div>
        <div className="text-white/40 text-sm">
          {activeFilters ? 'No stocks match the active filters' : 'Loading stocks...'}
        </div>
        <div className="text-white/20 text-xs mt-1 font-mono">
          {activeFilters ? 'Try disabling some criteria' : 'Please wait'}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-[#0f1218] border border-white/[0.07] rounded-xl overflow-hidden">

      {/* Table header */}
      <div className="grid grid-cols-[1.8fr_1fr_1fr_1fr_1fr_1fr_80px] gap-0 px-4 py-3 bg-[#151a22] border-b border-white/[0.07]">
        {['Company', 'Mkt Cap', 'Promoter', 'P/E', 'ROE', 'Analyst', 'Score'].map(h => (
          <div key={h} className="text-[10px] font-mono text-white/30 uppercase tracking-wider">{h}</div>
        ))}
      </div>

      {/* Rows — only passed stocks */}
      {passed.map((r, i) => {
        const s = r.stock
        const mcapStr = s.mcap >= 100000
  ? `₹${(s.mcap / 100000).toFixed(1)}L Cr`
  : s.mcap >= 1000
  ? `₹${s.mcap.toLocaleString('en-IN')} Cr`
  : `₹${s.mcap} Cr`
        const scorePct  = Math.round((r.score / r.maxScore) * 100)
        const scoreColor = r.score >= 15 ? 'text-green-400' : r.score >= 10 ? 'text-blue-400' : r.score >= 7 ? 'text-amber-400' : 'text-red-400'
        const barColor   = r.score >= 15 ? 'bg-green-400' : r.score >= 10 ? 'bg-blue-400' : r.score >= 7 ? 'bg-amber-400' : 'bg-red-400'
        const sectorColor = sectorColors[i % sectorColors.length]

        return (
          <div
            key={s.sym}
            onClick={() => router.push(`/stock/${s.sym}`)}
            className="grid grid-cols-[1.8fr_1fr_1fr_1fr_1fr_1fr_80px] gap-0 px-4 py-3 border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors cursor-pointer"
          >
            {/* Company */}
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-[10px] font-bold font-mono flex-shrink-0 ${sectorColor}`}>
                {s.sym.slice(0, 2)}
              </div>
              <div>
                <div className="text-sm font-medium text-white">{s.name}</div>
                <div className="text-[10px] text-white/30 font-mono mt-0.5">{s.sym} · {s.sector}</div>
              </div>
            </div>

            {/* Mkt Cap */}
            <div className="flex items-center">
              <span className="text-sm font-mono text-white/70">{mcapStr}</span>
            </div>

            {/* Promoter */}
            <div className="flex items-center">
              <span className={`text-sm font-mono ${s.promoter > 75 ? 'text-green-400' : 'text-white/70'}`}>
                {s.promoter.toFixed(1)}%
              </span>
            </div>

            {/* P/E */}
            <div className="flex items-center">
              <span className="text-sm font-mono text-white/70">
                {s.pe !== null ? `${s.pe}x` : <span className="text-white/20">N/A</span>}
              </span>
            </div>

            {/* ROE */}
            <div className="flex items-center">
              <span className={`text-sm font-mono ${s.roe > 15 ? 'text-green-400' : 'text-white/70'}`}>
                {s.roe.toFixed(1)}%
              </span>
            </div>

            {/* Analyst */}
            <div className="flex items-center">
              <span className={`text-xs font-mono px-2 py-0.5 rounded-full border ${analystColor[s.analyst] || analystColor.Neutral}`}>
                {s.analyst}
              </span>
            </div>

            {/* Score */}
            <div className="flex items-center gap-2">
              <span className={`text-sm font-mono font-semibold ${scoreColor}`}>{r.score}</span>
              <div className="w-12 h-1.5 bg-white/5 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${barColor}`} style={{ width: `${scorePct}%` }} />
              </div>
            </div>
          </div>
        )
      })}

      {/* Footer */}
      <div className="px-4 py-3 border-t border-white/[0.04] flex items-center justify-between">
        <div className="text-xs font-mono text-white/20">
          Showing {passed.length} of {results.length} stocks
        </div>
        <div className="text-xs font-mono text-white/20">
          {results.length - passed.length} filtered out
        </div>
      </div>
    </div>
  )
}