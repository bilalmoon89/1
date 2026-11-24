"""Overlay validated session quotes on daily rotation metrics without fabricating candles."""
import pandas as pd
from rotation_engine import stock_metrics, normalize, WINDOWS
from session_validity import session_clock, regular_status
from ticker_check import number


def intraday_metrics(history, quotes, benchmark, now):
    stocks, _ = stock_metrics(history, benchmark)
    if stocks.empty:
        return stocks, None
    clock = session_clock(now)
    valid = {}
    for symbol, q in quotes.items():
        try:
            stamp = pd.Timestamp(float(q['last_bar_update_time']), unit='s', tz='UTC')
            session = pd.Timestamp(float(q['time']), unit='s', tz='UTC').tz_convert('America/New_York')
            price, change = number(q.get('close')), number(q.get('change'))
            if not clock['open'] or session.date() != clock['date']:
                continue
            if regular_status(stamp, now, max_age_seconds=1800) != 'CURRENT':
                continue
            if price is None or price <= 0 or change is None:
                continue
            valid[symbol] = (price, change, stamp)
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
    if benchmark not in valid:
        return pd.DataFrame(), None
    anchor = valid[benchmark][2]
    for i, row in stocks.iterrows():
        symbol = row.Symbol
        q = valid.get(symbol)
        f = normalize(history.get(symbol))
        f = f[f.index.date < clock['date']]
        # A stale daily baseline must not be promoted by a fresh quote.
        prior = pd.Timestamp(clock['date'])
        from session_validity import calendar
        previous = calendar().previous_session(prior).date()
        if q is None or abs((q[2]-anchor).total_seconds()) > 300 or f.empty or f.index[-1].date() != previous:
            stocks.loc[i, 'Data'] = 'Intraday unavailable / stale'
            stocks.loc[i, 'Complete 10D'] = False
            for n in WINDOWS:
                stocks.loc[i, f'{n}D %'] = float('nan')
            continue
        price, change, stamp = q
        stocks.loc[i, 'Price'] = price
        stocks.loc[i, 'Bar date'] = str(clock['date'])
        stocks.loc[i, '1D %'] = change
        stocks.loc[i, 'Data'] = 'OK'
        for n in WINDOWS:
            if n > 1:
                stocks.loc[i, f'{n}D %'] = (price/f.Close.iloc[-n]-1)*100 if len(f)>=n else float('nan')
        stocks.loc[i, 'Quote ET'] = stamp.tz_convert('America/New_York').isoformat(timespec='seconds')
    b = stocks[stocks.Symbol.eq(benchmark)]
    if b.empty or b.iloc[0].Data != 'OK':
        return pd.DataFrame(), None
    for n in WINDOWS:
        stocks[f'RS {n}D pp'] = stocks[f'{n}D %'] - b.iloc[0][f'{n}D %']
    return stocks, anchor.tz_convert('America/New_York')
