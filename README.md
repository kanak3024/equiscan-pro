# EquiScan Pro 📊

A production-grade quantitative stock screener for Indian equity markets —
built with the same analytical framework used by institutional fund managers
and PMS strategies in India.

> 504 stocks · 25-factor engine · Live data · Built solo

---

## 📸 Screenshots

| Stock Screener |
|----------------|
| ![Screener](./screener.png) |

| Stock Detail — Chart & Metrics | DMA & Relative Strength |
|-------------------------------|-------------------------|
| ![Detail](./detail.png) | ![Analysis](./analysis.png) |

---

## ✨ Features

**Screener**
- 🔍 25-factor multi-criteria filter engine across 504 NSE/BSE stocks
- 📊 Fundamentals: Listing age, Market cap, Promoter %, Pledge, P/E, ROE, D/E, Revenue growth, EPS momentum, Cash flow
- 📈 Technical: 20/50/200 DMA alignment, RSI 40–70, Near 52W High
- 🎯 Analyst consensus: Buy/Outperform filter, recent upgrades, price target upside, institutional buying
- 🏭 Sector filtering across all NSE/BSE sectors

**Tier 2 — Pro Signals**
- ⚡ MACD bullish crossover — momentum turning positive
- 🏔️ Price making new 3-month highs — breakout signal
- ✨ Golden Cross — 50 DMA crossing above 200 DMA
- 📊 Relative Strength vs Nifty 50 — stock outperforming the index
- 🎯 ATR < 3% — low volatility, controlled price action
- 💥 Bollinger Band squeeze — explosion imminent

**Stock Detail Page**
- 📉 Interactive price chart (30D / 90D / 180D / 365D)
- 📐 Moving average analysis — DMA visual with bullish/bearish signal
- ⚡ Relative strength vs Nifty 50 (1M / 3M / 6M)
- 🔊 Volume analysis with spike detection (normal / high / extreme)
- 🤖 Quant signal engine — composite Buy/Hold/Sell score
- ✅ All 25 criteria checked per stock with pass/fail breakdown

**Platform**
- ⭐ Watchlist — save and track shortlisted stocks
- 🔔 Alerts system
- 🔴 Live data pipeline — Kite Connect + Screener.in + Trendlyne with automated 6:30 AM IST daily refresh
- 💾 In-memory cache with disk persistence and batch rate-limiting

---

## 🛠️ Tech Stack

| Layer      | Technology                                              |
|------------|---------------------------------------------------------|
| Frontend   | Next.js, TypeScript, Tailwind CSS, Recharts             |
| Backend    | Python, FastAPI                                         |
| Data APIs  | Kite Connect (Zerodha), Screener.in, Trendlyne, Tickertape |
| Scheduler  | APScheduler — daily refresh at 6:30 AM IST             |
| Charts     | Recharts                                                |

---

## 📁 Project Structure

```
backend/
├── fetchers/         # Kite, NSE, Screener, Quant, Trendlyne fetchers
├── main.py           # FastAPI server
├── scheduler.py      # Daily data refresh
├── quant.py          # Signal generation engine
└── requirements.txt

frontend/
├── app/
│   ├── screener/     # Main screener page
│   ├── stock/[symbol]/ # Detailed stock page
│   ├── watchlist/    # Saved stocks
│   └── alerts/       # Price alerts
├── components/
│   ├── FilterPanel.tsx   # 19-factor filter UI
│   ├── StockTable.tsx    # Results table
│   └── Navbar.tsx
└── lib/
    ├── screenerEngine.ts # Filter logic
    ├── stockData.ts      # Demo data
    └── watchlist.ts      # Watchlist state
```

---

## 🚀 Running Locally

```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Add your API keys to `.env`:
```
KITE_API_KEY=
KITE_API_SECRET=
KITE_ACCESS_TOKEN=
SCREENER_SESSION=
DATABASE_URL=
```

---

## 👤 Built By

**Kanak Suryavanshi** — [@kanak3024](https://github.com/kanak3024)  
🌐 [thriftgennie.com](https://thriftgennie.com)
