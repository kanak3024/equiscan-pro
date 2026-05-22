'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

const links = [
  { href: '/screener', label: 'Screener' },
  { href: '/watchlist', label: 'Watchlist' },
  { href: '/alerts', label: 'Alerts' },
]

export default function Navbar() {
  const pathname = usePathname()

  return (
    <nav className="border-b border-white/[0.07] bg-[#0a0c10]/90 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-screen-2xl mx-auto px-6 h-14 flex items-center justify-between">
        
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 bg-blue-500 rounded-md flex items-center justify-center text-xs font-bold text-white font-mono">
            EQ
          </div>
          <span className="text-white font-semibold tracking-tight">EquiScan Pro</span>
          <span className="text-xs text-white/20 font-mono">NSE · BSE</span>
        </div>

        {/* Nav links */}
        <div className="flex items-center gap-1">
          {links.map(link => (
            <Link
              key={link.href}
              href={link.href}
              className={`px-4 py-1.5 rounded-md text-sm transition-all ${
                pathname === link.href
                  ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                  : 'text-white/50 hover:text-white hover:bg-white/5'
              }`}
            >
              {link.label}
            </Link>
          ))}
        </div>

        {/* Status */}
        <div className="flex items-center gap-2 text-xs font-mono text-white/30">
          <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          Demo Mode
        </div>

      </div>
    </nav>
  )
}