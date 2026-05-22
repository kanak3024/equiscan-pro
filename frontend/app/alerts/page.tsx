'use client'
import { useState } from 'react'
import { stocks } from '../../lib/stockData'

type Alert = {
  id: number
  sym: string
  type: 'price_above' | 'price_below' | 'all_filters_pass'
  value?: number
  active: boolean
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([
    { id: 1, sym: 'MANKIND', type: 'price_above', value: 2500, active: true },
    { id: 2, sym: 'APTUS',   type: 'all_filters_pass', active: true },
    { id: 3, sym: 'EMARTIND', type: 'price_below', value: 150, active: false },
  ])
  const [newSym, setNewSym] = useState('')
  const [newType, setNewType] = useState<Alert['type']>('price_above')
  const [newValue, setNewValue] = useState('')

  const addAlert = () => {
    if (!newSym) return
    setAlerts(prev => [...prev, {
      id: Date.now(),
      sym: newSym.toUpperCase(),
      type: newType,
      value: newValue ? parseFloat(newValue) : undefined,
      active: true,
    }])
    setNewSym('')
    setNewValue('')
  }

  const toggleAlert = (id: number) => {
    setAlerts(prev => prev.map(a => a.id === id ? { ...a, active: !a.active } : a))
  }

  const deleteAlert = (id: number) => {
    setAlerts(prev => prev.filter(a => a.id !== id))
  }

  const getStockName = (sym: string) => stocks.find(s => s.sym === sym)?.name || sym

  const alertTypeLabel: Record<Alert['type'], string> = {
    price_above:      'Price goes above ₹',
    price_below:      'Price goes below ₹',
    all_filters_pass: 'Passes all active filters',
  }

  return (
    <div className="max-w-screen-xl mx-auto px-6 py-8">

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-white tracking-tight">Alerts</h1>
        <p className="text-white/40 text-sm mt-1 font-mono">
          Get notified when stocks hit your criteria
        </p>
      </div>

      <div className="grid grid-cols-[1fr_340px] gap-6 items-start">

        {/* Alerts list */}
        <div className="space-y-3">
          {alerts.length === 0 ? (
            <div className="bg-[#0f1218] border border-white/[0.07] rounded-xl p-16 text-center">
              <div className="text-4xl mb-4">🔔</div>
              <div className="text-white/40 text-sm">No alerts set</div>
            </div>
          ) : alerts.map(alert => (
            <div key={alert.id} className={`bg-[#0f1218] border rounded-xl p-5 flex items-center justify-between transition-all ${
              alert.active ? 'border-white/[0.07]' : 'border-white/[0.03] opacity-50'
            }`}>
              <div className="flex items-center gap-4">
                {/* Status dot */}
                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${alert.active ? 'bg-green-400 animate-pulse' : 'bg-white/20'}`} />
                <div>
                  <div className="text-white font-medium">{getStockName(alert.sym)}</div>
                  <div className="text-white/40 text-xs font-mono mt-0.5">
                    {alertTypeLabel[alert.type]}{alert.value ? alert.value.toLocaleString('en-IN') : ''}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <span className={`text-xs font-mono px-2 py-0.5 rounded-full border ${
                  alert.active
                    ? 'bg-green-500/10 text-green-400 border-green-500/20'
                    : 'bg-white/5 text-white/20 border-white/10'
                }`}>
                  {alert.active ? 'Active' : 'Paused'}
                </span>
                <button
                  onClick={() => toggleAlert(alert.id)}
                  className="text-xs font-mono text-white/30 hover:text-blue-400 transition-colors px-2"
                >
                  {alert.active ? 'Pause' : 'Resume'}
                </button>
                <button
                  onClick={() => deleteAlert(alert.id)}
                  className="text-white/20 hover:text-red-400 transition-colors text-lg px-2"
                >
                  ×
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Create alert panel */}
        <div className="bg-[#0f1218] border border-white/[0.07] rounded-xl p-5">
          <div className="text-xs font-mono text-white/30 uppercase tracking-wider mb-5">
            Create Alert
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-xs text-white/40 font-mono mb-1.5 block">Stock Symbol</label>
              <input
                value={newSym}
                onChange={e => setNewSym(e.target.value)}
                placeholder="e.g. MANKIND"
                className="w-full bg-[#151a22] border border-white/[0.07] rounded-lg px-3 py-2 text-sm text-white font-mono placeholder-white/20 outline-none focus:border-blue-500/40"
              />
            </div>

            <div>
              <label className="text-xs text-white/40 font-mono mb-1.5 block">Alert Type</label>
              <select
                value={newType}
                onChange={e => setNewType(e.target.value as Alert['type'])}
                className="w-full bg-[#151a22] border border-white/[0.07] rounded-lg px-3 py-2 text-sm text-white font-mono outline-none focus:border-blue-500/40"
              >
                <option value="price_above">Price goes above</option>
                <option value="price_below">Price goes below</option>
                <option value="all_filters_pass">Passes all filters</option>
              </select>
            </div>

            {newType !== 'all_filters_pass' && (
              <div>
                <label className="text-xs text-white/40 font-mono mb-1.5 block">Price (₹)</label>
                <input
                  value={newValue}
                  onChange={e => setNewValue(e.target.value)}
                  placeholder="e.g. 2500"
                  type="number"
                  className="w-full bg-[#151a22] border border-white/[0.07] rounded-lg px-3 py-2 text-sm text-white font-mono placeholder-white/20 outline-none focus:border-blue-500/40"
                />
              </div>
            )}

            <button
              onClick={addAlert}
              className="w-full bg-blue-500 hover:bg-blue-600 transition-colors text-white text-sm font-medium py-2.5 rounded-lg"
            >
              + Create Alert
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}