'use client'
import { useState } from 'react'
import { Filters } from '../lib/screenerEngine'

type Props = {
  filters: Filters
  onChange: (filters: Filters) => void
}

type FilterDef = {
  key: keyof Filters
  label: string
  hint: string
  cat: 'LISTING' | 'QUALITY' | 'TECH' | 'FUND' | 'ANALYST'
}

const filterDefs: FilterDef[] = [
  { key: 'f_listed8y',            label: 'Listed ≤ 8 Years',           hint: 'IPO between 2017–2026',         cat: 'LISTING' },
  { key: 'f_mcap1000',            label: 'Market Cap > ₹1000 Cr',      hint: 'Mid-cap and above only',        cat: 'LISTING' },
  { key: 'f_promoter75',          label: 'Promoter > 75%',             hint: 'High promoter conviction',      cat: 'QUALITY' },
  { key: 'f_noDilution',          label: 'No Promoter Dilution (5Y)',   hint: 'Holding stable or increased',   cat: 'QUALITY' },
  { key: 'f_pledge5',             label: 'Pledge < 5%',                hint: 'Minimal pledged shares',        cat: 'QUALITY' },
  { key: 'f_dmaAligned',          label: '20 DMA > 50 > 200 DMA',      hint: 'Full bullish alignment',        cat: 'TECH' },
  { key: 'f_dma50_200',           label: '50 DMA > 200 DMA',           hint: 'Medium-term uptrend',           cat: 'TECH' },
  { key: 'f_rsiHealthy',          label: 'RSI 40–70',                  hint: 'Not overbought or oversold',    cat: 'TECH' },
  { key: 'f_near52wHigh', label: 'Near 52W High (within 10%)', hint: 'Strong momentum signal', cat: 'TECH' },
  { key: 'f_profit3Q',            label: 'Profit — Last 3 Quarters',   hint: 'Consistent positive PAT',       cat: 'FUND' },
  { key: 'f_cashflow5Q',          label: 'Positive Cash Flow (5Q)',     hint: 'Operating CFO positive',        cat: 'FUND' },
  { key: 'f_peUnder60',           label: 'P/E < 60',                   hint: 'Reasonable valuation',          cat: 'FUND' },
  { key: 'f_revenueGrowth15',     label: 'Revenue Growth > 15%',       hint: 'Strong top-line growth',        cat: 'FUND' },
  { key: 'f_debtLow',             label: 'Debt/Equity < 0.5',          hint: 'Low leverage',                  cat: 'FUND' },
  { key: 'f_roe15',               label: 'ROE > 15%',                  hint: 'Efficient capital use',         cat: 'FUND' },
  { key: 'f_analystPositive',     label: 'Analyst: Buy/Outperform',    hint: 'Consensus next Q + 1Y',         cat: 'ANALYST' },
  { key: 'f_recentUpgrade',       label: 'Recent Upgrade (30D)',        hint: 'At least 1 upgrade',            cat: 'ANALYST' },
  { key: 'f_priceTargetUpside20', label: 'Price Target Upside > 20%',  hint: 'Consensus 12M target vs CMP',   cat: 'ANALYST' },
  { key: 'f_instBuying',          label: 'Institutional Buying (QoQ)', hint: 'FII/DII increased stake',       cat: 'ANALYST' },
  { key: 'f_epsIncreasing', label: 'EPS Increasing (3Q)', hint: 'EPS growing each quarter', cat: 'FUND' },
]

const catColors: Record<string, string> = {
  LISTING: 'text-blue-400',
  QUALITY: 'text-amber-400',
  TECH:    'text-purple-400',
  FUND:    'text-teal-400',
  ANALYST: 'text-green-400',
}

const categories = ['LISTING', 'QUALITY', 'TECH', 'FUND', 'ANALYST']

export default function FilterPanel({ filters, onChange }: Props) {
  const toggle = (key: keyof Filters) => {
    onChange({ ...filters, [key]: !filters[key] })
  }

  const activeCount = filterDefs.filter(f => filters[f.key] === true).length
  const sectors = Array.from(new Set(
  filterDefs.map(f => f.cat)
)).filter(Boolean)

const [selectedSector, setSelectedSector] = useState<string>('All')

  return (
 <div className="bg-[#0f1218] border border-white/[0.07] rounded-xl p-5 sticky top-20 max-h-[calc(100vh-120px)] overflow-y-auto">      
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <span className="text-xs font-mono text-white/30 uppercase tracking-wider">Filters</span>
        <span className="text-xs font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full">
          {activeCount} active
        </span>
      </div>

      {/* Filter groups */}
      {categories.map(cat => (
        <div key={cat} className="mb-5">
          <div className="text-[10px] font-mono text-white/20 uppercase tracking-widest mb-2 flex items-center gap-2">
            <span className={catColors[cat]}>{cat}</span>
          </div>
          {filterDefs.filter(f => f.cat === cat).map(f => (
            <div
              key={f.key}
              onClick={() => toggle(f.key)}
              className={`flex items-start gap-3 p-2.5 rounded-lg cursor-pointer mb-1 transition-all ${
                filters[f.key]
                  ? 'bg-blue-500/5 border border-blue-500/15'
                  : 'border border-transparent hover:bg-white/[0.03]'
              }`}
            >
              {/* Toggle */}
              <div className={`mt-0.5 w-8 h-4 rounded-full flex-shrink-0 relative transition-all ${
                filters[f.key] ? 'bg-blue-500/30 border border-blue-500/50' : 'bg-white/10 border border-white/10'
              }`}>
                <div className={`absolute top-0.5 w-3 h-3 rounded-full transition-all ${
                  filters[f.key] ? 'left-4 bg-blue-400' : 'left-0.5 bg-white/30'
                }`} />
              </div>
              {/* Label */}
              <div>
                <div className="text-xs font-medium text-white/80">{f.label}</div>
                <div className="text-[10px] text-white/30 mt-0.5">{f.hint}</div>
              </div>
            </div>
          ))}
        </div>
      ))}

      {/* Reset */}
      <button
        onClick={() => onChange({ ...filters, f_listed8y: false, f_mcap1000: false, f_promoter75: false, f_noDilution: false, f_dmaAligned: false, f_dma50_200: false, f_profit3Q: false, f_cashflow5Q: false, f_analystPositive: false, f_pledge5: false, f_rsiHealthy: false, f_peUnder60: false, f_revenueGrowth15: false, f_debtLow: false, f_roe15: false, f_recentUpgrade: false, f_priceTargetUpside20: false, f_instBuying: false })}
        className="w-full mt-2 py-2 text-xs font-mono text-white/30 border border-white/[0.07] rounded-lg hover:text-red-400 hover:border-red-500/30 transition-all"
      >
        ↺ Reset all
      </button>
    </div>
  )
}