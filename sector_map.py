"""One shared sector -> proxy ETF map, used by the scan, the live check and themes.

Keys cover GICS names (stocks.csv), older aliases, and TradingView's own sector
taxonomy (used for names discovered by the screener). A missing key means the
sector has no honest ETF proxy, and the plan stays at WATCH.
"""

SECTOR_PROXY = {
    # GICS sectors (stocks.csv)
    'Information Technology': 'XLK', 'Health Care': 'XLV', 'Financials': 'XLF',
    'Industrials': 'XLI', 'Consumer Discretionary': 'XLY', 'Consumer Staples': 'XLP',
    'Energy': 'XLE', 'Materials': 'XLB', 'Utilities': 'XLU', 'Real Estate': 'XLRE',
    'Communication Services': 'XLC',
    # Aliases used elsewhere in the code base
    'Technology': 'XLK', 'Healthcare': 'XLV', 'Biotech': 'XBI', 'Semiconductors': 'SMH',
    'Precious Metals': 'GLD',
    # Non-equity ETF candidates are measured against their own asset class
    'Gold': 'GLD', 'Bonds': 'TLT', 'Crypto': 'IBIT',
    # TradingView sector taxonomy
    'Electronic Technology': 'XLK', 'Technology Services': 'XLK', 'Finance': 'XLF',
    'Health Technology': 'XLV', 'Health Services': 'XLV', 'Retail Trade': 'XLY',
    'Consumer Durables': 'XLY', 'Consumer Services': 'XLY', 'Consumer Non-Durables': 'XLP',
    'Energy Minerals': 'XLE', 'Industrial Services': 'XLI', 'Producer Manufacturing': 'XLI',
    'Transportation': 'XLI', 'Distribution Services': 'XLI', 'Commercial Services': 'XLI',
    'Process Industries': 'XLB', 'Non-Energy Minerals': 'XLB', 'Communications': 'XLC',
}

# Sector labels for the ETF trade candidates (not in stocks.csv).
ETF_SECTORS = {
    'XBI': 'Health Care', 'IHI': 'Health Care', 'KRE': 'Financials',
    'XRT': 'Consumer Discretionary', 'SMH': 'Information Technology',
    'GDX': 'Gold', 'GLD': 'Gold', 'TLT': 'Bonds', 'IBIT': 'Crypto',
}

UNCLASSIFIED = ('', 'Unclassified', 'Unknown', 'US Large/Mid Cap')


def proxy_for(sector):
    """Return the proxy ETF for a sector label, or None."""
    return SECTOR_PROXY.get(str(sector).strip()) if sector else None


def yahoo_symbol(symbol):
    """Yahoo uses '-' for share classes: BRK.B -> BRK-B.

    Only plain share-class tickers are changed; index/futures/FX symbols such as
    DX-Y.NYB, ^VIX or GC=F are passed through untouched.
    """
    s = str(symbol).strip().upper()
    head, dot, tail = s.partition('.')
    if dot and head.isalpha() and tail.isalpha() and len(tail) <= 2 and not s.startswith('^'):
        return f'{head}-{tail}'
    return s
