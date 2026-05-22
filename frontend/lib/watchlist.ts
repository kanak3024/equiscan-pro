const WATCHLIST_KEY = 'equiscan_watchlist'

export function getWatchlist(): string[] {
  if (typeof window === 'undefined') return []
  try {
    const saved = localStorage.getItem(WATCHLIST_KEY)
    return saved ? JSON.parse(saved) : []
  } catch {
    return []
  }
}

export function addToWatchlist(symbol: string): void {
  const list = getWatchlist()
  if (!list.includes(symbol)) {
    list.push(symbol)
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(list))
  }
}

export function removeFromWatchlist(symbol: string): void {
  const list = getWatchlist().filter(s => s !== symbol)
  localStorage.setItem(WATCHLIST_KEY, JSON.stringify(list))
}

export function isInWatchlist(symbol: string): boolean {
  return getWatchlist().includes(symbol)
}