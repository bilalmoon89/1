"""Optional, non-authenticated market/news adapters. Fail closed and report coverage.
TradingView screener is a discovery aid, NOT the user's authenticated TradingView
connection, NOT an official TradingView API and not a guaranteed live data feed.
"""
from __future__ import annotations
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo
import io
import csv
import pandas as pd
import numpy as np
from crescent_engine import SECTORS, BENCHMARKS, CROSS_ASSETS, normalise

ET=ZoneInfo('America/New_York')


def symbols_from_file(filename='stocks.csv'):
    df=pd.read_csv(filename).fillna('')
    return dict(zip(df.Symbol.astype(str).str.upper(),df.Sector.astype(str)))


def seed_universe(sectors, pins=(), per_sector=8, limit=140):
    """Industry-balanced candidate sampling of the original stock universe.
    This sample is NOT a market-wide leadership discovery if TV is unavailable.
    """
    groups={};out=[]
    for ticker,sector in sectors.items():
        groups.setdefault(sector,[]).append(ticker)
    for x in pins:
        s=str(x).strip().upper()
        if s in sectors and s not in out:out.append(s)
    for sector in sorted(groups):
        count=0
        for s in groups[sector]:
            if s not in out and count<per_sector and len(out)<limit:
                out.append(s);count+=1
    return out[:limit]


def tv_leadership(limit=120):
    """Best-effort screener candidate discovery. Never infer permissions from failure."""
    from tradingview_screener import Query,col
    q=(Query().set_markets('america')
       .select('name','close','volume','sector','Perf.W','Perf.1M','EMA21','EMA50','market_cap_basic')
       .where(col('close')>5,col('market_cap_basic')>2_000_000_000,col('volume')>250_000)
       .order_by('Perf.1M',ascending=False).limit(limit*3))
    total,frame=q.get_scanner_data()
    if frame is None or frame.empty:return [],'TradingView screener returned no rows.'
    # Sector-balanced from ranked results. Do not overfit technology concentration.
    if 'sector' not in frame.columns or 'name' not in frame.columns:
        return [],'TradingView screener returned incomplete columns.'
    counts={};out=[]
    for _,row in frame.iterrows():
        symbol=str(row['name']).strip().upper()
        sector=str(row['sector'])
        if not symbol or not symbol.replace('-','').replace('.','').isalnum():continue
        if counts.get(sector,0)>=max(6,int(limit/9)):continue
        if symbol not in out:
            out.append(symbol);counts[sector]=counts.get(sector,0)+1
        if len(out)>=limit:break
    return out,f'Screener candidates: {len(out)} of approximately {total} market results; sector-balanced selection.'


def _extract_symbol(df,symbol,all_symbols):
    if df is None or len(df)==0:return pd.DataFrame()
    if isinstance(df.columns,pd.MultiIndex):
        a,b=df.columns.levels[0],df.columns.levels[1]
        try:
            if symbol in a: f=df[symbol].copy()
            elif symbol in b:f=df.xs(symbol,level=1,axis=1).copy()
            else:return pd.DataFrame()
        except Exception:return pd.DataFrame()
    else:f=df.copy() if len(all_symbols)==1 else pd.DataFrame()
    return normalise(f)


def yahoo_daily(symbols,period='1y',chunk_size=14,progress=None):
    """Download completed-session candidates, returning per-symbol failures, no false coverage.
    The caller removes incomplete current-day data with complete_daily().
    """
    import yfinance as yf
    symbols=list(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
    frames={};fail={}
    for at in range(0,len(symbols),chunk_size):
        group=symbols[at:at+chunk_size]
        try:
            data=yf.download(tickers=group,period=period,interval='1d',auto_adjust=False,
                             group_by='ticker',threads=True,progress=False,actions=False,
                             timeout=24)
            for symbol in group:
                frame=_extract_symbol(data,symbol,group)
                if len(frame)<65:fail[symbol]=f'Only {len(frame)} usable daily bars'
                else:frames[symbol]=frame
        except Exception as exc:
            for symbol in group:fail[symbol]=f'{type(exc).__name__}: {str(exc)[:100]}'
        if progress:progress(min(len(symbols),at+len(group)),len(symbols))
    return frames,fail


def yahoo_five_minute(symbol,days='10d',extended=False):
    import yfinance as yf
    raw=yf.Ticker(symbol).history(period=days,interval='5m',prepost=extended,auto_adjust=False,actions=False)
    if raw is None or len(raw)<12:raise ValueError(f'Insufficient 5m bars for {symbol}')
    f=raw.copy()
    if isinstance(f.columns,pd.MultiIndex):f.columns=f.columns.get_level_values(0)
    f.columns=[str(c).title() for c in f.columns]
    f=f[['Open','High','Low','Close','Volume']].dropna(subset=['Open','High','Low','Close'])
    if f.index.tz is None:raise ValueError('Missing timezone in intraday source; cannot guarantee RTH aggregation.')
    return f


def read_events(data):
    """CSV schema: Date,Time_ET,Title,Impact,Tickers,Source,Confirmed.
    Entries are user-provided, not auto-verified official calendar records.
    """
    if not data:return pd.DataFrame()
    f=pd.read_csv(io.BytesIO(data))
    required={'Date','Time_ET','Title','Impact','Tickers','Source','Confirmed'}
    if not required.issubset(set(f.columns)):
        raise ValueError('Events CSV needs: '+', '.join(sorted(required)))
    f=f.copy()
    dates=pd.to_datetime(f.Date.astype(str)+' '+f.Time_ET.astype(str),format='%Y-%m-%d %H:%M',errors='coerce')
    if dates.isna().any():raise ValueError('Invalid date/time in events CSV; use YYYY-MM-DD and HH:MM ET.')
    f['When ET']=dates
    f['Impact']=f.Impact.astype(str).str.upper()
    f['Confirmed']=f.Confirmed.astype(str).str.strip().str.lower().isin(('true','1','yes'))
    return f.sort_values('When ET')


def risk_events(events,now=None,symbol=None,window_minutes=75):
    """Only user-provided CONFIRMED HIGH events create timing blocks."""
    if events is None or events.empty:return []
    now=now or datetime.now(ET)
    if now.tzinfo is not None:now=now.astimezone(ET).replace(tzinfo=None)
    warnings=[]
    for _,r in events.iterrows():
        tickers={p.strip().upper() for p in str(r.get('Tickers','')).replace(';',',').split(',') if p.strip()}
        applies=not tickers or symbol is None or symbol.upper() in tickers or 'ALL' in tickers
        minutes=abs((r['When ET'].to_pydatetime()-now).total_seconds()/60)
        if applies and r.get('Impact')=='HIGH' and r.get('Confirmed') and minutes<=window_minutes:
            warnings.append(str(r['Title']))
    return warnings


def news_rss(query='markets tariffs geopolitical risk economic policy',max_entries=8):
    """Third-party RSS headlines only; content cannot authorize trades."""
    import requests,feedparser
    url='https://news.google.com/rss/search?q='+quote(query)+'&hl=en-US&gl=US&ceid=US:en'
    resp=requests.get(url,timeout=9,headers={'User-Agent':'Mozilla/5.0 CrescentResearch/1.0'})
    resp.raise_for_status()
    parsed=feedparser.parse(resp.content)
    articles=[];seen=set()
    for x in parsed.entries:
        title=x.get('title','').strip();link=x.get('link','').strip()
        if not title or not link or title in seen:continue
        seen.add(title)
        articles.append({'Title':title,'URL':link,'Published':x.get('published','Unknown'),
                         'Provider':'Google News RSS (aggregated; not independently verified)'})
        if len(articles)==max_entries:break
    return articles


def generate_demo():
    """Explicitly synthetic history for UX/testing. Never blend with live prices."""
    end=pd.Timestamp('2026-10-29'); dates=pd.bdate_range(end=end,periods=145)
    stocks=symbols_from_file('stocks.csv')
    tickers=['SPY','QQQ','RSP','IWM']+list(SECTORS)+list(CROSS_ASSETS)
    tickers+=['LLY','MRK','ABBV','JNJ','PFE','REGN','VRTX','UNH','PG','KO','PEP','WMT','CL','COST','DUK','SO',
             'XOM','CVX','STX','MRVL','NVDA','AMD','MSFT','AAPL','META','ANF','U','JPM','CAT','PLTR','GILD','HCA','WDC']
    tickers=list(dict.fromkeys(tickers))
    hist={}
    for sym in tickers:
        rng=np.random.default_rng(sum((i+1)*ord(c) for i,c in enumerate(sym))+712)
        sector=stocks.get(sym,'')
        defensive=sym in ('XLV','XLP','XLU') or sector in ('Health Care','Healthcare','Consumer Staples','Utilities')
        energy=sym in ('XLE','XOM','CVX') or sector=='Energy'
        tech=sym in ('XLK','QQQ','MRVL','STX','NVDA','AMD','MSFT','AAPL','META','WDC')
        if sym in ('SPY','RSP','IWM'):drift=0.0003
        elif defensive:drift=.0023
        elif energy:drift=.0028
        elif tech:drift=-.0010
        else:drift=.0006
        daily=rng.normal(.0005,.009,145)
        daily[-36:]=rng.normal(drift,.010,36)
        if sym in CROSS_ASSETS:daily=rng.normal(0,.012,145)
        base=85+(sum(ord(c) for c in sym)%70)
        close=base*np.exp(np.cumsum(daily))
        high=close*(1+np.abs(rng.normal(.007,.004,145)))
        low=close*(1-np.abs(rng.normal(.007,.004,145)))
        op=close*(1+rng.normal(0,.003,145))
        high=np.maximum.reduce([high,close,op]);low=np.minimum.reduce([low,close,op])
        vol=rng.integers(800000,5000000,145).astype(float)
        hist[sym]=pd.DataFrame({'Open':op,'High':high,'Low':low,'Close':close,'Volume':vol},index=dates)
    # Two deterministic SYNTHETIC, clearly labelled test setups so the UI can
    # exercise an ARMED plan rather than encourage interpretation of blank screens.
    for symbol,base in [('LLY',100.0),('PG',90.0)]:
        last=base+45
        close=np.r_[np.linspace(base,last,123),np.linspace(last,last+7,7),np.linspace(last+7,last+4,15)]
        hist[symbol]=pd.DataFrame({'Open':close-.15,'High':close+.60,
            'Low':close-.60,'Close':close,'Volume':np.full(145,3_000_000.0)},index=dates)
    return hist,stocks
