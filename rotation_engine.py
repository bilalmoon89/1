"""Pure rotation calculations. No network, Streamlit, or scanner-universe mutation."""
import numpy as np
import pandas as pd

WINDOWS = (1, 2, 5, 10, 21)

def normalize(frame):
    if frame is None or frame.empty or 'Close' not in frame:
        return pd.DataFrame()
    f = frame.copy()
    idx = pd.DatetimeIndex(pd.to_datetime(f.index))
    if idx.tz is not None:
        idx = idx.tz_convert('America/New_York').tz_localize(None)
    f.index = idx.normalize()
    f = f[~f.index.duplicated(keep='last')].sort_index()
    for c in f.columns:
        f[c] = pd.to_numeric(f[c], errors='coerce')
    return f.replace([np.inf, -np.inf], np.nan)

def stock_metrics(history, benchmark='SPY'):
    """All horizons use the same benchmark session endpoints; never forward fill."""
    b = normalize(history.get(benchmark))
    if b.empty:
        return pd.DataFrame(), None
    sessions = b.index[b.Close.notna() & (b.Close > 0)]
    if len(sessions) < 11:
        return pd.DataFrame(), None
    asof = sessions[-1]
    rows = []
    for symbol, raw in history.items():
        f = normalize(raw)
        r = {'Symbol': symbol, 'Data': 'Unavailable'}
        if f.empty:
            rows.append(r); continue
        good = f.loc[f.Close.notna() & (f.Close > 0)]
        if good.empty:
            rows.append(r); continue
        r['Bar date'] = str(good.index[-1].date())
        if asof not in good.index:
            r['Data'] = 'Stale / missing latest session'; rows.append(r); continue
        c = f.Close.reindex(sessions)
        r.update({'Price': float(c.iloc[-1]), 'Data': 'OK'})
        for n in WINDOWS:
            # Require every session, not merely both endpoints, to reveal gaps.
            window = c.iloc[-n-1:]
            r[f'{n}D %'] = (window.iloc[-1]/window.iloc[0]-1)*100 if len(window)==n+1 and window.notna().all() and (window > 0).all() else np.nan
        r['Complete 10D'] = bool(c.iloc[-11:].notna().all() and (c.iloc[-11:] > 0).all())
        if not r['Complete 10D']: r['Data'] = 'Short / gapped history'
        for n in (9, 21, 50):
            valid = c.iloc[-max(3*n, n):]
            ema = c.ewm(span=n, adjust=False, min_periods=n).mean().iloc[-1] if valid.notna().all() else np.nan
            r[f'EMA {n}'] = ema
            r[f'Above {n}'] = float(c.iloc[-1] > ema) if pd.notna(ema) else np.nan
        r['Vs 21 EMA %'] = (c.iloc[-1]/r['EMA 21']-1)*100
        vol = f.get('Volume', pd.Series(dtype=float)).reindex(sessions)
        prior = vol.iloc[-21:-1]
        r['Avg volume 20D'] = prior.mean() if len(prior)==20 and prior.notna().all() else np.nan
        dollars = (vol*c).iloc[-21:-1]
        r['Avg $ volume 20D'] = dollars.mean() if len(dollars)==20 and dollars.notna().all() else np.nan
        r['Volume / prior 20D'] = vol.iloc[-1]/r['Avg volume 20D'] if r['Avg volume 20D'] > 0 else np.nan
        high = f.get('High', f.Close).reindex(sessions)
        low = f.get('Low', f.Close).reindex(sessions)
        tr = pd.concat([high-low, (high-c.shift()).abs(), (low-c.shift()).abs()], axis=1).max(axis=1)
        atr = tr.iloc[-14:].mean() if tr.iloc[-14:].notna().all() else np.nan
        r['ATR14'] = atr
        r['Extension ATR'] = (c.iloc[-1]-r['EMA 21'])/atr if atr > 0 else np.nan
        rows.append(r)
    stocks = pd.DataFrame(rows)
    for n in WINDOWS:
        bench = (b.loc[asof,'Close']/b.loc[sessions[-n-1],'Close']-1)*100 if len(sessions)>n else np.nan
        stocks[f'RS {n}D pp'] = stocks.get(f'{n}D %', np.nan)-bench
    return stocks, asof

def theme_metrics(stocks, themes, min_coverage=.7):
    rows=[]
    indexed = stocks.set_index('Symbol') if not stocks.empty else pd.DataFrame()
    for t in themes:
        members = list(dict.fromkeys(t['symbols']))
        f = indexed.reindex(members) if not indexed.empty else pd.DataFrame(index=members)
        valid = f.loc[f.get('Complete 10D', pd.Series(False,index=f.index)).eq(True)]
        r={'Theme':t['name'], 'Group':t['group'], 'Members':len(members), 'Valid':len(valid),
           'Coverage %':100*len(valid)/len(members) if members else 0}
        r['Rank eligible'] = len(valid)>=3 and r['Coverage %']>=min_coverage*100
        for n in WINDOWS:
            x=valid.get(f'{n}D %',pd.Series(dtype=float)).dropna()
            r[f'Valid {n}D']=len(x)
            if n==21 and (len(x)<3 or len(x)<len(members)*min_coverage):x=pd.Series(dtype=float)
            r[f'{n}D %']=x.mean()
            r[f'Median {n}D %']=x.median()
            r[f'Breadth {n}D %']=100*(x>0).mean() if len(x) else np.nan
            r[f'RS {n}D pp']=valid.get(f'RS {n}D pp',pd.Series(dtype=float)).mean() if len(x) else np.nan
        r['Above 21 %']=100*valid.get('Above 21',pd.Series(dtype=float)).mean()
        r['Above 50 %']=100*valid.get('Above 50',pd.Series(dtype=float)).mean()
        # Geometric relative pace: recent 2 sessions versus preceding 8, percentage points/day.
        r['Acceleration pp/day']=((1+r['2D %']/100)**.5-((1+r['10D %']/100)/(1+r['2D %']/100))**(1/8))*100 if pd.notna(r['10D %']) and r['2D %']>-100 else np.nan
        if not r['Rank eligible']: state='Low coverage'
        elif r['RS 2D pp']>0 and r['Breadth 2D %']>=60 and r['Acceleration pp/day']>0:
            state='Heating' if r['RS 10D pp']<=0 else 'Leading + heating'
        elif r['RS 10D pp']>0 and (r['RS 2D pp']<0 or r['Breadth 2D %']<40): state='Cooling'
        elif r['RS 5D pp']>0 and r['RS 10D pp']>0 and r['Breadth 5D %']>=60: state='Leading'
        elif r['RS 2D pp']<0 and r['RS 10D pp']<0: state='Lagging'
        else: state='Mixed'
        r['State']=state
        r['Top movers']= ', '.join(valid.sort_values('1D %',ascending=False).head(3).index) if len(valid) else '—'
        rows.append(r)
    out=pd.DataFrame(rows)
    if out.empty: return out
    ok=out['Rank eligible']
    for n in WINDOWS:
        out.loc[ok,f'Rank {n}D']=out.loc[ok,f'{n}D %'].rank(ascending=False,method='min')
    out['Rank lift 10D → 2D']=out.get('Rank 10D',np.nan)-out.get('Rank 2D',np.nan)
    return out

def leader_table(stocks, symbols, min_dollars=5_000_000, max_extension=2.0):
    f=stocks[stocks.Symbol.isin(symbols)].copy()
    if f.empty: return f
    f['Liquid'] = f['Avg $ volume 20D'].ge(min_dollars)
    eligible=f['Complete 10D'].eq(True) & f['Liquid']
    f['Leader score']=np.nan
    # Rank only comparable liquid members; descriptive priority, not an entry signal.
    for n,w in [(2,.2),(5,.4),(10,.4)]:
        ranks=f.loc[eligible,f'RS {n}D pp'].rank(pct=True)*100*w
        f.loc[eligible,'Leader score']=f.loc[eligible,'Leader score'].fillna(0)+ranks
    f['Review'] = 'Watch'
    f.loc[~f['Liquid'],'Review']='Low liquidity / unknown'
    f.loc[eligible & f['Above 21'].eq(1) & f['Above 50'].eq(1) & f['RS 5D pp'].gt(0),'Review']='Trend leader'
    f.loc[eligible & f['Extension ATR'].gt(max_extension),'Review']='Extended — wait for setup'
    f.loc[~f['Complete 10D'].eq(True),'Review']='Data incomplete'
    return f.sort_values(['Leader score','5D %'],ascending=False,na_position='last')
