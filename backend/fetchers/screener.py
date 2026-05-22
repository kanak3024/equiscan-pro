import os
import re
import httpx
from bs4 import BeautifulSoup

def get_screener_session():
    return os.getenv("SCREENER_SESSION", "")

def parse_number(text: str) -> float:
    if not text:
        return 0.0
    text = text.replace(",", "").replace("%", "").replace("₹", "").replace("Cr", "").strip()
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        return float(text)
    except:
        return 0.0

async def get_fundamentals(symbol: str) -> dict:
    session = get_screener_session()
    headers = {
        "Cookie": f"sessionid={session}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                f"https://www.screener.in/company/{symbol}/consolidated/",
                headers=headers
            )
            soup = BeautifulSoup(r.text, "html.parser")

            # Top Ratios
            ratios = {}
            for li in soup.select("#top-ratios li"):
                name = li.select_one(".name")
                value = li.select_one(".number")
                if name and value:
                    ratios[name.text.strip()] = value.text.strip()

            mcap = parse_number(ratios.get("Market Cap", "0"))
            pe   = parse_number(ratios.get("Stock P/E", "0")) or None
            roe  = parse_number(ratios.get("ROE", "0"))

            # Revenue growth + debt from tables
            debt_eq        = 0.0
            revenue_growth = 0.0
            for table in soup.select("table"):
                for row in table.select("tr"):
                    cols = row.select("td")
                    if len(cols) < 2:
                        continue
                    label = cols[0].text.strip()
                    if any(x in label for x in ["Debt to Equity", "Debt / Equity", "D/E"]):
                        debt_eq = parse_number(cols[-1].text)
                    if any(x in label for x in ["Sales Growth", "Revenue Growth"]):
                        vals = [parse_number(c.text) for c in cols[1:] if c.text.strip()]
                        if vals:
                            revenue_growth = vals[-1]

            # Balance sheet debt
            if debt_eq == 0.0:
                try:
                    bs_section = soup.find("section", {"id": "balance-sheet"})
                    if bs_section:
                        borrowings     = 0.0
                        equity_capital = 0.0
                        reserves       = 0.0
                        for row in bs_section.select("tr"):
                            cols = row.select("td")
                            if len(cols) < 2:
                                continue
                            label = cols[0].text.strip()
                            val   = parse_number(cols[-1].text)
                            if "Borrowings" in label:
                                borrowings = val
                            if "Equity Capital" in label:
                                equity_capital = val
                            if "Reserves" in label:
                                reserves = val
                        total_equity = equity_capital + reserves
                        if total_equity > 0 and borrowings > 0:
                            debt_eq = round(borrowings / total_equity, 2)
                except:
                    pass

            # Revenue growth fallback
            if revenue_growth == 0.0:
                try:
                    for section in soup.select(".company-ratios, #profit-loss"):
                        text = section.get_text()
                        matches = re.findall(r"Sales Growth[^\d]*(\d+\.?\d*)", text)
                        if matches:
                            revenue_growth = float(matches[0])
                            break
                except:
                    pass

            # Promoter shareholding
            promoter        = 0.0
            promoter_stable = True
            try:
                sh_section = soup.find("section", {"id": "shareholding"})
                if sh_section:
                    for row in sh_section.select("table tbody tr"):
                        cols = row.select("td")
                        if cols and "Promoters" in cols[0].text:
                            values = []
                            for c in cols[1:]:
                                try:
                                    values.append(float(
                                        c.text.strip().replace("%", "").replace(",", "")
                                    ))
                                except:
                                    pass
                            if values:
                                promoter = values[-1]
                                if len(values) >= 2:
                                    promoter_stable = values[-1] >= values[0]
                            break
            except:
                pass

            # Quarterly profits + EPS
            profit_3q      = False
            eps_increasing = False
            try:
                for row in soup.select("#quarters table tbody tr"):
                    cols = row.select("td")
                    if not cols:
                        continue
                    label = cols[0].text.strip()
                    if "Net Profit" in label:
                        vals = []
                        for c in cols[1:]:
                            try:
                                vals.append(parse_number(c.text))
                            except:
                                pass
                        if len(vals) >= 3:
                            profit_3q = all(v > 0 for v in vals[-3:])
                    if "EPS" in label:
                        vals = []
                        for c in cols[1:]:
                            try:
                                vals.append(parse_number(c.text))
                            except:
                                pass
                        if len(vals) >= 3:
                            last3 = vals[-3:]
                            eps_increasing = last3[2] > last3[1] > last3[0]
            except:
                pass

            # IPO Year
            ipo_year = 2020
            try:
                about = soup.find("div", {"id": "about"})
                if about:
                    text = about.get_text()
                    match = re.search(r'listed.*?(\d{4})', text, re.IGNORECASE)
                    if match:
                        ipo_year = int(match.group(1))
            except:
                pass

            # Cash flow
            cashflow_5q = False
            try:
                for row in soup.select("#cash-flow table tbody tr"):
                    if "Operating" in row.text:
                        cols = row.select("td")
                        vals = []
                        for c in cols[1:]:
                            try:
                                vals.append(parse_number(c.text))
                            except:
                                pass
                        if len(vals) >= 5:
                            cashflow_5q = all(v > 0 for v in vals[-5:])
                        break
            except:
                pass

            return {
                "symbol":          symbol,
                "mcap":            mcap,
                "pe":              pe,
                "roe":             roe,
                "debt_eq":         debt_eq,
                "revenue_growth":  revenue_growth,
                "promoter":        promoter,
                "promoter_stable": promoter_stable,
                "profit_3q":       profit_3q,
                "eps_increasing":  eps_increasing,
                "cashflow_5q":     cashflow_5q,
                "ipo_year":        ipo_year,
                "error":           None
            }

    except Exception as e:
        return {"symbol": symbol, "error": str(e)}