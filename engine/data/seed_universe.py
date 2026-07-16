"""Curated liquid US universe for the Polygon free tier.

Polygon's /v3/reference/tickers returns names alphabetically (not by liquidity),
so on a rate-limited free tier a naive cap yields a board of "A" names. This
seed is a hand-picked set of liquid, recognizable names across sectors (plus SPY
as the benchmark) so the first live board is meaningful. Swap to the full
dynamic universe later by setting data.polygon.use_seed_universe: false.
"""
from __future__ import annotations

from .base import TickerMeta

# (ticker, name, sector, type)
SEED: list[tuple[str, str, str, str]] = [
    ("SPY", "SPDR S&P 500 ETF", "Index", "ETF"),
    # Technology
    ("AAPL", "Apple", "Technology", "CS"),
    ("MSFT", "Microsoft", "Technology", "CS"),
    ("NVDA", "NVIDIA", "Technology", "CS"),
    ("AVGO", "Broadcom", "Technology", "CS"),
    ("AMD", "Advanced Micro Devices", "Technology", "CS"),
    ("CRM", "Salesforce", "Technology", "CS"),
    ("ORCL", "Oracle", "Technology", "CS"),
    ("ADBE", "Adobe", "Technology", "CS"),
    ("CSCO", "Cisco", "Technology", "CS"),
    ("QCOM", "Qualcomm", "Technology", "CS"),
    ("TXN", "Texas Instruments", "Technology", "CS"),
    ("INTC", "Intel", "Technology", "CS"),
    ("MU", "Micron", "Technology", "CS"),
    ("PANW", "Palo Alto Networks", "Technology", "CS"),
    ("CRWD", "CrowdStrike", "Technology", "CS"),
    ("SNOW", "Snowflake", "Technology", "CS"),
    ("PLTR", "Palantir", "Technology", "CS"),
    ("SMCI", "Super Micro Computer", "Technology", "CS"),
    ("NOW", "ServiceNow", "Technology", "CS"),
    ("MRVL", "Marvell", "Technology", "CS"),
    ("DELL", "Dell", "Technology", "CS"),
    # Communication
    ("GOOGL", "Alphabet", "Communication", "CS"),
    ("META", "Meta Platforms", "Communication", "CS"),
    ("NFLX", "Netflix", "Communication", "CS"),
    ("DIS", "Disney", "Communication", "CS"),
    ("T", "AT&T", "Communication", "CS"),
    ("VZ", "Verizon", "Communication", "CS"),
    # Consumer Discretionary
    ("AMZN", "Amazon", "Consumer Disc.", "CS"),
    ("TSLA", "Tesla", "Consumer Disc.", "CS"),
    ("HD", "Home Depot", "Consumer Disc.", "CS"),
    ("NKE", "Nike", "Consumer Disc.", "CS"),
    ("MCD", "McDonald's", "Consumer Disc.", "CS"),
    ("SBUX", "Starbucks", "Consumer Disc.", "CS"),
    ("LOW", "Lowe's", "Consumer Disc.", "CS"),
    ("ABNB", "Airbnb", "Consumer Disc.", "CS"),
    # Consumer Staples
    ("WMT", "Walmart", "Consumer Staples", "CS"),
    ("COST", "Costco", "Consumer Staples", "CS"),
    ("PG", "Procter & Gamble", "Consumer Staples", "CS"),
    ("KO", "Coca-Cola", "Consumer Staples", "CS"),
    ("PEP", "PepsiCo", "Consumer Staples", "CS"),
    # Financials
    ("JPM", "JPMorgan Chase", "Financials", "CS"),
    ("BAC", "Bank of America", "Financials", "CS"),
    ("WFC", "Wells Fargo", "Financials", "CS"),
    ("GS", "Goldman Sachs", "Financials", "CS"),
    ("MS", "Morgan Stanley", "Financials", "CS"),
    ("V", "Visa", "Financials", "CS"),
    ("MA", "Mastercard", "Financials", "CS"),
    ("AXP", "American Express", "Financials", "CS"),
    ("SOFI", "SoFi Technologies", "Financials", "CS"),
    ("COIN", "Coinbase", "Financials", "CS"),
    ("PYPL", "PayPal", "Financials", "CS"),
    # Healthcare
    ("LLY", "Eli Lilly", "Healthcare", "CS"),
    ("UNH", "UnitedHealth", "Healthcare", "CS"),
    ("JNJ", "Johnson & Johnson", "Healthcare", "CS"),
    ("ABBV", "AbbVie", "Healthcare", "CS"),
    ("MRK", "Merck", "Healthcare", "CS"),
    ("PFE", "Pfizer", "Healthcare", "CS"),
    ("TMO", "Thermo Fisher", "Healthcare", "CS"),
    ("ISRG", "Intuitive Surgical", "Healthcare", "CS"),
    # Industrials
    ("CAT", "Caterpillar", "Industrials", "CS"),
    ("BA", "Boeing", "Industrials", "CS"),
    ("GE", "GE Aerospace", "Industrials", "CS"),
    ("HON", "Honeywell", "Industrials", "CS"),
    ("UBER", "Uber Technologies", "Industrials", "CS"),
    ("DE", "Deere", "Industrials", "CS"),
    ("LMT", "Lockheed Martin", "Industrials", "CS"),
    # Energy
    ("XOM", "Exxon Mobil", "Energy", "CS"),
    ("CVX", "Chevron", "Energy", "CS"),
    ("COP", "ConocoPhillips", "Energy", "CS"),
    ("SLB", "Schlumberger", "Energy", "CS"),
    # Materials / Utilities / Real Estate
    ("LIN", "Linde", "Materials", "CS"),
    ("FCX", "Freeport-McMoRan", "Materials", "CS"),
    ("NEE", "NextEra Energy", "Utilities", "CS"),
    ("PLD", "Prologis", "Real Estate", "CS"),
]


def seed_metas() -> list[TickerMeta]:
    return [TickerMeta(t, n, ty, "US", s) for (t, n, s, ty) in SEED]
