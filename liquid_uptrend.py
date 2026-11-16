"""The user's liquid-uptrend preset, calculated from completed daily OHLCV."""
from dataclasses import dataclass
import pandas as pd
from crescent_engine import normalise, finite


@dataclass(frozen=True)
class LiquidFilters:
    volume20:float=1_000_000
    dollar_volume50:float=100_000_000
    above_sma200:float=.01
    above_sma50:float=.01
    adr1:float=3.0
    adr20:float=3.0


def _strength(f,close):
    """63-session return, distance from the 52-week high, and a tight / extended label."""
    from crescent_engine import atr14
    out={'63D %':None,'Off 52W high':None,'Setup':''}
    try:
        if len(f)>=64 and float(f.Close.iloc[-64])>0:out['63D %']=(close/float(f.Close.iloc[-64])-1)*100
        out['Off 52W high']=(close/max(float(f.High.tail(252).max()),close)-1)*100
        from setup_scanner import tight_area,PRESETS
        tight,_=tight_area(f,PRESETS['Standard'])
        atr=atr14(f);ema21=float(f.Close.ewm(span=21,adjust=False).mean().iloc[-1])
        out['Setup']='TIGHT · 8 EMA' if tight else 'EXTENDED' if atr and (close-ema21)/atr>2.5 else ''
    except Exception:pass
    return out


def _rank(rows,returns):
    """RS rank 1-99: percentile of the 63-session return across every loaded history (20 or more needed)."""
    ranks={}
    if len(returns)>=20:
        ranks=(pd.Series(returns).rank(pct=True)*99).clip(1,99).round().to_dict()
    for row in rows:row['RS rank']=ranks.get(row['Symbol'])
    return bool(ranks)


PHARMA_KEYS=('biotechnology','drug-manufacturers','diagnostics-research')


def screen_history(history,filters=None):
    filters=filters or LiquidFilters()
    rows=[];unavailable={};returns={}
    for symbol,raw in history.items():
        f=normalise(raw)
        if len(f)>=64 and float(f.Close.iloc[-64])>0:returns[symbol]=float(f.Close.iloc[-1])/float(f.Close.iloc[-64])-1
        if len(f)<200:
            unavailable[symbol]=f'{len(f)} daily bars; 200 required'
            continue
        if f.Volume.tail(50).isna().any() or (f.Volume.tail(50)<0).any():
            unavailable[symbol]='Incomplete or invalid volume history'
            continue
        close=float(f.Close.iloc[-1]);vol=float(f.Volume.tail(20).mean())
        dollar=float((f.Close*f.Volume).tail(50).mean())
        sma200=float(f.Close.tail(200).mean());sma50=float(f.Close.tail(50).mean())
        above200=(close/sma200-1)*100;above50=(close/sma50-1)*100
        adr1=float((f.High.iloc[-1]-f.Low.iloc[-1])/close*100)
        adr20=float((f.High.tail(20).mean()-f.Low.tail(20).mean())/close*100)
        values=[vol,dollar,above200,above50,adr1,adr20]
        thresholds=[filters.volume20,filters.dollar_volume50,filters.above_sma200,filters.above_sma50,filters.adr1,filters.adr20]
        if not all(finite(x) and x>limit for x,limit in zip(values,thresholds)):continue
        rows.append({'Symbol':symbol,'Close':round(close,2),'Avg volume 20D':round(vol),
            'Avg $ volume 50D':round(dollar),'Vs SMA200 %':round(above200,2),'Vs SMA50 %':round(above50,2),
            'ADR 1D %':round(adr1,2),'ADR 20D %':round(adr20,2),**_strength(f,close),'As of':str(f.index[-1].date())})
    ranked=_rank(rows,returns)
    result=pd.DataFrame(rows)
    # Strongest first when a universe-wide rank exists; otherwise most liquid first.
    if not result.empty:result=result.sort_values(['RS rank','Avg $ volume 50D'] if ranked else 'Avg $ volume 50D',ascending=False).reset_index(drop=True)
    return result,unavailable


def fetch_industries(symbols):
    result={s:{'industry':'','key':'','source':'Unavailable'} for s in symbols}
    if symbols:
        try:
            from tradingview_screener import Query,col
            _,rows=(Query().set_markets('america').select('name','industry')
                .where(col('name').isin(list(symbols))).limit(len(symbols)).get_scanner_data(timeout=6))
            for _,row in rows.iterrows():
                industry=row['industry'] if isinstance(row['industry'],str) else ''
                if row['name'] in result and industry:
                    result[row['name']]={'industry':industry,'key':'','source':'TradingView'}
        except Exception:pass
    return result


def apply_exclusions(frame,industries,exclude_pharma=True,tickers=(),keywords=()):
    included=[];excluded=[]
    for _,row in frame.iterrows():
        item=row.to_dict();meta=industries.get(item['Symbol'],{})
        raw_industry=meta.get('industry','');raw_key=meta.get('key','')
        industry=raw_industry if isinstance(raw_industry,str) else ''
        key=raw_key.lower() if isinstance(raw_key,str) else ''
        item['Industry']=industry or 'Unverified'
        item['Classification source']=meta.get('source','Supplied') if industry else 'Unavailable'
        reason=None
        if item['Symbol'] in set(tickers):reason='Excluded ticker'
        elif exclude_pharma and not industry and not key:reason='Industry unverified under the default exclusion'
        elif exclude_pharma and (any(x in key for x in PHARMA_KEYS) or any(x in industry.lower() for x in ['pharmaceutical','biotechnology','life science','drug manufacturer','diagnostics & research'])):
            reason='Pharmaceuticals / biotechnology / life sciences'
        elif any(x.strip().lower() in industry.lower() for x in keywords if x.strip()):reason='Excluded industry keyword'
        if reason:item['Exclusion']=reason;excluded.append(item)
        else:included.append(item)
    return pd.DataFrame(included),pd.DataFrame(excluded)


def screen_intraday(history,quotes,now,filters=None):
    """Active session ranges and prices; completed-session liquidity baselines."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from session_validity import session_clock,regular_status
    filters=filters or LiquidFilters()
    rows=[];missing={};returns={};et=ZoneInfo('America/New_York')
    now=now.astimezone(et)
    for symbol,raw in history.items():
        f=normalise(raw);q=quotes.get(symbol,{})
        try:
            stamp=datetime.fromtimestamp(float(q['last_bar_update_time']),et)
            session=datetime.fromtimestamp(float(q['time']),et)
            if (now-stamp).total_seconds() < -300:raise ValueError('Quote timestamp is in the future')
            clock=session_clock(now)
            if session.date()!=clock['date'] or stamp.date()!=clock['date']:raise ValueError('No quote for the latest regular session')
            status=regular_status(stamp,now,max_age_seconds=1800,close_tolerance_seconds=60)
            if status in ('STALE','UNVERIFIED'):raise ValueError('Regular-session quote is stale or incomplete')
            f=f[f.index.date<session.date()]
            if len(f)<200:raise ValueError('200 completed daily bars required')
            if f.Volume.tail(50).isna().any() or (f.Volume.tail(50)<0).any():raise ValueError('Invalid historical volume')
            close=float(q['close']);high=float(q['high']);low=float(q['low'])
            sma200=float(q['SMA200']);sma50=float(q['SMA50'])
            vol=float(f.Volume.tail(20).mean());dollar=float((f.Close*f.Volume).tail(50).mean())
            if close<=0 or high<low or sma200<=0 or sma50<=0:raise ValueError('Invalid session prices')
            if len(f)>=63 and float(f.Close.iloc[-63])>0:returns[symbol]=close/float(f.Close.iloc[-63])-1
            above200=(close/sma200-1)*100;above50=(close/sma50-1)*100
            adr1=(high-low)/close*100
            adr20=((f.High.tail(19).sum()+high)-(f.Low.tail(19).sum()+low))/20/close*100
            values=[vol,dollar,above200,above50,adr1,adr20]
            limits=[filters.volume20,filters.dollar_volume50,filters.above_sma200,filters.above_sma50,filters.adr1,filters.adr20]
            if not all(finite(x) and x>limit for x,limit in zip(values,limits)):continue
            vwap=pd.to_numeric(q.get('VWAP'),errors='coerce')
            mode=str(q.get('update_mode','Unknown'))
            if mode.startswith('delayed_streaming_'):
                mode=f"{int(mode.rsplit('_',1)[1])//60} min delayed"
            rows.append({'Symbol':symbol,'Last':round(close,2),'Today %':q.get('change'),
                'From open %':q.get('change_from_open'),'Vs VWAP %':(close/vwap-1)*100 if finite(vwap) and vwap>0 else None,
                'Session volume':q.get('volume'),'RVOL':q.get('relative_volume_10d_calc'),
                'Avg volume 20D':vol,'Avg $ volume 50D':dollar,'Vs SMA200 %':above200,'Vs SMA50 %':above50,
                'ADR 1D %':adr1,'ADR 20D %':adr20,**_strength(f,close),'Quote ET':stamp.isoformat(timespec='seconds'),
                'Session':str(session.date()),'Session status':status,'Feed':mode,'Source':'TradingView','Retrieved ET':q.get('retrieved',''),
                'Baseline through':str(f.index[-1].date())})
        except (KeyError,ValueError,TypeError,OverflowError,OSError) as exc:missing[symbol]=str(exc)
    _rank(rows,returns)
    result=pd.DataFrame(rows)
    if not result.empty:result=result.sort_values('Today %',ascending=False,na_position='last').reset_index(drop=True)
    return result,missing
