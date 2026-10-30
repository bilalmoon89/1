"""Crescent Cloud & Air Gap V6 — pure analytical functions.

Source-aligned components: Team Tape EMA Cloud PDF (Oct 2026)
- cloud hierarchy: 10m,30m,1h,4h,daily; 5/12 and 34/50
- classic MTF trigger: completed 1h 34/50 break
- first possible magnet: daily 20/21; second: daily 50/55
- A+ grade: 3+ of 4 setup checks (separation, velocity, RVOL, SPY alignment)

Additional Crescent safeguards and scoring are our implementation hypotheses,
NOT verified TAPERDR source algorithms or historical performance probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional
import math
import numpy as np
import pandas as pd

CLOUD_FAST = (5, 12)
CLOUD_SLOW = (34, 50)
DAILY_MAGNET_ONE = (20, 21)
DAILY_MAGNET_TWO = (50, 55)
TZ = 'America/New_York'


def finite(x):
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def safe_float(x, default=None):
    return float(x) if finite(x) else default


def normalize_bars(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize OHLCV frame to monotonic timestamp index and title-case columns."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=['Open','High','Low','Close','Volume'])
    data = df.copy()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data.columns = [str(c).capitalize() for c in data.columns]
    required = ['Open','High','Low','Close','Volume']
    if any(c not in data for c in required):
        raise ValueError(f'OHLCV data must include {required}')
    data = data[required].apply(pd.to_numeric, errors='coerce')
    data = data.dropna(subset=['Open','High','Low','Close']).sort_index()
    data = data.loc[~data.index.duplicated(keep='last')]
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError('OHLCV index must be datetime.')
    if data.index.tz is None:
        data.index = data.index.tz_localize('UTC')
    data.index = data.index.tz_convert(TZ)
    data['Volume'] = data['Volume'].fillna(0).clip(lower=0)
    return data


def emacloud(frame: pd.DataFrame, short: int, long: int, source: str='hl2') -> pd.DataFrame:
    if not len(frame):
        return pd.DataFrame(index=frame.index, columns=['low','high','ema_short','ema_long'])
    if source not in ('hl2','close'):
        raise ValueError('source must be hl2 or close')
    series = ((frame.High + frame.Low)/2) if source == 'hl2' else frame.Close
    a = series.ewm(span=short, adjust=False, min_periods=short).mean()
    b = series.ewm(span=long, adjust=False, min_periods=long).mean()
    return pd.DataFrame({'low':np.minimum(a,b), 'high':np.maximum(a,b),
                         'ema_short':a, 'ema_long':b}, index=frame.index)


def atr(frame: pd.DataFrame, period:int=14) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype='float64')
    high,low,close=frame.High, frame.Low, frame.Close
    true_range=pd.concat([high-low,(high-close.shift()).abs(),(low-close.shift()).abs()],axis=1).max(axis=1)
    return true_range.ewm(alpha=1/period, adjust=False, min_periods=period).mean()


def bar_session_resample(five_min:pd.DataFrame, freq_minutes:int, regular_only:bool=True) -> pd.DataFrame:
    """Aggregate interval-start stamped 5m bars within each US session.

    Session anchoring: RTH starts 09:30, extended starts 04:00. Bars ending at
    session close may be shorter than nominal size; only return completed bars
    (closing at session end is accepted). Never aggregate across dates.
    """
    if five_min.empty:
        return five_min.copy()
    if freq_minutes not in (10,30,60,240):
        raise ValueError('frequency must be 10, 30, 60 or 240 minutes')
    x=normalize_bars(five_min)
    start_minutes=570 if regular_only else 240
    end_minutes=960 if regular_only else 1200
    out=[]
    for _, day in x.groupby(x.index.date):
        mins=day.index.hour*60+day.index.minute
        valid=(mins>=start_minutes)&(mins<end_minutes)
        day=day[valid]
        if day.empty: continue
        mins=day.index.hour*60+day.index.minute
        bucket=((mins-start_minutes)//freq_minutes).astype(int)
        for bid,grp in day.groupby(bucket):
            start=start_minutes+int(bid)*freq_minutes
            end=min(start+freq_minutes,end_minutes)
            # No unfinished bucket: need the final 5m interval at expected end.
            expected_last=end-5
            last=grp.index[-1]
            lastmin=last.hour*60+last.minute
            if lastmin < expected_last: continue
            if int(grp.index[0].hour*60+grp.index[0].minute) > start: continue
            idx=pd.Timestamp(day.index[0].date(),tz=TZ)+pd.Timedelta(minutes=start)
            out.append((idx,grp.Open.iloc[0],grp.High.max(),grp.Low.min(),grp.Close.iloc[-1],grp.Volume.sum()))
    if not out:
        return x.iloc[:0]
    return pd.DataFrame(out,columns=['Date','Open','High','Low','Close','Volume']).set_index('Date').sort_index()


def last_candle_cloud(df, a:int,b:int, source='hl2') -> Optional[dict]:
    v=emacloud(df,a,b,source)
    if v.empty or not finite(v['low'].iloc[-1]):return None
    return {k:float(v[k].iloc[-1]) for k in ('low','high','ema_short','ema_long')}


def cloud_state(price,cloud):
    if not cloud or not finite(price):return 'UNKNOWN'
    if price>cloud['high']:return 'ABOVE'
    if price<cloud['low']:return 'BELOW'
    return 'INSIDE'


def cloud_breaks(hourly:pd.DataFrame, source='hl2', lookback_bars=3) -> list[dict]:
    """Confirmed hourly 34/50 cloud breaks; latest events first."""
    if len(hourly)<60:return []
    c=emacloud(hourly,34,50,source)
    result=[]
    lo=max(1,len(hourly)-lookback_bars)
    for i in range(lo,len(hourly)):
        prev=float(hourly.Close.iloc[i-1]);cur=float(hourly.Close.iloc[i])
        old_hi,old_lo=c['high'].iloc[i-1],c['low'].iloc[i-1]
        hi,low=c['high'].iloc[i],c['low'].iloc[i]
        if not all(finite(v) for v in (old_hi,old_lo,hi,low)):continue
        if prev>=old_lo and cur<low:direction='BEAR'
        elif prev<=old_hi and cur>hi:direction='BULL'
        else:continue
        result.append({'direction':direction,'index':i,'time':hourly.index[i],
                       'price_at_break':cur,'cloud_low':float(low),'cloud_high':float(hi),
                       'previous_close':prev})
    return result[::-1]


def daily_magnets(price:float, direction:str, daily:pd.DataFrame, source='hl2') -> list[dict]:
    """Only actual daily clouds ahead of current price; no invented targets."""
    if daily.empty:return []
    magnets=[]
    for name,pair in [('D20/21',(20,21)),('D50/55',(50,55))]:
        c=last_candle_cloud(daily,*pair,source=source)
        if c is None:continue
        target = c['low'] if direction=='BULL' else c['high']
        if (direction=='BULL' and target>price) or (direction=='BEAR' and target<price):
            magnets.append({'name':name,'target':target,'low':c['low'],'high':c['high'],
                            'distance':abs(target-price)})
    return sorted(magnets,key=lambda m:m['distance'])


def detect_double_mtf(tenmin: pd.DataFrame, daily: pd.DataFrame, event: dict, source='hl2') -> bool:
    """Both hourly break and DAILY 20/21 broken on the event date.

    Uses the daily cloud known *before* the event date, avoiding the completed
    daily candle from the event day even when scanning after the close.
    A crossed daily 20/21 must be evidenced by a completed 10m closing bar.
    """
    if tenmin.empty or daily.empty or not event:
        return False
    date=event['time'].date()
    previous_daily=daily[daily.index.date < date]
    c=last_candle_cloud(previous_daily,20,21,source)
    if not c:return False
    same_day=tenmin[tenmin.index.date==date]
    if len(same_day)<2:return False
    threshold=c['high'] if event['direction']=='BULL' else c['low']
    prev=same_day.Close.shift(1)
    cur=same_day.Close
    crossed=((prev<=threshold)&(cur>threshold)) if event['direction']=='BULL' else ((prev>=threshold)&(cur<threshold))
    return bool(crossed.fillna(False).any())


def same_slot_rvol(bars:pd.DataFrame, current_idx, prior_days:int=15):
    if bars.empty or current_idx not in bars.index:return None
    cur=bars.loc[current_idx]
    if isinstance(cur,pd.DataFrame):cur=cur.iloc[-1]
    prev=bars[(bars.index < current_idx)&(bars.index.strftime('%H:%M')==current_idx.strftime('%H:%M'))]
    if len(prev)<5:return None
    mean=prev.Volume.tail(prior_days).mean()
    return float(cur.Volume/mean) if mean>0 else None


def breakout_impulse(tenmin:pd.DataFrame, hourly_event:dict):
    """First 10m bar after break-hour open with largest range; its RVOL and ATR.

    This is a documented Crescent approximation of the PDF's 10m break-bar test,
    not a claim that TAPERDR selects the same bar.
    """
    if tenmin.empty or len(tenmin)<20:return {'velocity':None,'rvol':None,'bar_time':None}
    t=hourly_event['time']
    window=tenmin[(tenmin.index>=t)&(tenmin.index<t+pd.Timedelta(hours=1))]
    if window.empty:return {'velocity':None,'rvol':None,'bar_time':None}
    ranges=(window.High-window.Low)
    idx=ranges.idxmax()
    series_atr=atr(tenmin)
    bar_atr=float(series_atr.loc[idx]) if finite(series_atr.loc[idx]) else None
    velocity=(float(ranges.loc[idx])/bar_atr) if bar_atr and bar_atr>0 else None
    return {'velocity':velocity,'rvol':same_slot_rvol(tenmin,idx),'bar_time':idx}


def safe_qualify_score(gap_atr,velocity,rvol,spy_agrees):
    checks={'separation':bool(finite(gap_atr) and gap_atr>=0.5),
            'velocity':bool(finite(velocity) and velocity>=1.5),
            'rvol':bool(finite(rvol) and rvol>=2.0),
            'spy':bool(spy_agrees)}
    score=sum(checks.values())
    return score, 'A+' if score>=3 else 'A' if score==2 else 'B',checks


def market_bias(hourly:pd.DataFrame, daily:pd.DataFrame, source='hl2') -> str:
    hc=last_candle_cloud(hourly,34,50,source)
    dc=last_candle_cloud(daily,34,50,source)
    hs=cloud_state(float(hourly.Close.iloc[-1]),hc) if len(hourly) else 'UNKNOWN'
    ds=cloud_state(float(daily.Close.iloc[-1]),dc) if len(daily) else 'UNKNOWN'
    if hs==ds=='ABOVE':return 'BULL'
    if hs==ds=='BELOW':return 'BEAR'
    return 'MIXED'


def scan_symbol(symbol:str, bars_by_tf:dict, spy_bias:str='MIXED',source='hl2',
                sector_bias='UNKNOWN', recent_hourly_bars=3) -> dict:
    """Return one honest candidate with entire ladder and evidence.

    When the MTF pattern is not present, emit a watch-state rather than invent a
    cloud-magnet. It does NOT generate actual orders.
    """
    daily=bars_by_tf.get('1D',pd.DataFrame());h1=bars_by_tf.get('1H',pd.DataFrame())
    m10=bars_by_tf.get('10m',pd.DataFrame());m30=bars_by_tf.get('30m',pd.DataFrame())
    h4=bars_by_tf.get('4H',pd.DataFrame())
    if daily.empty or h1.empty or len(h1)<60:
        raise ValueError('Insufficient completed 1H and daily candles.')
    price=float(m10.Close.iloc[-1] if len(m10) else h1.Close.iloc[-1])
    d_atr=atr(daily)
    d_atr_last=float(d_atr.iloc[-1]) if finite(d_atr.iloc[-1]) else None
    clouds={}
    for tf,df in [('10m',m10),('30m',m30),('1H',h1),('4H',h4),('1D',daily)]:
        clouds[tf]={}
        for label,a,b in [('fast',5,12),('slow',34,50)]:
            c=last_candle_cloud(df,a,b,source)
            clouds[tf][label]={'bounds':c,'state':cloud_state(price,c)}
    bias=market_bias(h1,daily,source)
    events=cloud_breaks(h1,source,recent_hourly_bars)
    event=events[0] if events else None
    direction=event['direction'] if event else (bias if bias!='MIXED' else None)
    current_targets=daily_magnets(price,direction,daily,source) if direction else []
    base={'symbol':symbol.upper().strip(),'price':price,'time':m10.index[-1] if len(m10) else h1.index[-1],
          'bias':bias,'market_bias':spy_bias,'sector_bias':sector_bias,
          'clouds':clouds,'daily_atr':d_atr_last, 'direction':direction,
          'event':event,'magnets':current_targets, 'source':source,
          'score':0, 'grade':'—', 'checks':{}, 'gap_atr':None,'gap_left':None,
          'gap_dollars':None,'rvol':None,'velocity':None,'rr':None,
          'stop':None,'target':None,'entry':None,'status':'WAIT',
          'setup':'Trend Watch','reason':'Await a completed 1H 34/50 cloud break.',
          'conflict':False}
    if not event:
        base['reason']=f'{bias.title()} hourly/daily structure; no recent confirmed 1H 34/50 break.'
        return base
    if not current_targets:
        base['reason']='Confirmed hourly break, but no valid daily magnet ahead of price.'
        base['setup']='Cloud Break — No Target'
        return base
    first=current_targets[0]
    # Only call it a classic MTF magnet if D20/21 is first.
    is_classic=first['name']=='D20/21'
    double_mtf=(first['name']=='D50/55' and detect_double_mtf(m10,daily,event,source))
    base['setup']='Double MTF' if double_mtf else ('MTF Magnet' if is_classic else 'Cloud Break — Nonclassic')
    base['double_mtf']=double_mtf
    base['target']=float(first['target'])
    base['gap_left']=float(first['distance'])
    base['gap_dollars']=float(abs(first['target']-event['price_at_break']))
    base['gap_atr']=(base['gap_dollars']/d_atr_last) if d_atr_last and d_atr_last>0 else None
    impulse=breakout_impulse(m10,event)
    base['velocity']=impulse['velocity'];base['rvol']=impulse['rvol']
    spy_agrees=(spy_bias==event['direction'])
    score,grade,checks=safe_qualify_score(base['gap_atr'],base['velocity'],base['rvol'],spy_agrees)
    base['score']=score;base['grade']=grade;base['checks']=checks
    # Stop at far edge of broken hourly cloud, with a modest ATR buffer.
    m10atr=atr(m10).iloc[-1] if len(m10)>=14 else np.nan
    buffer=float(m10atr)*0.1 if finite(m10atr) else (d_atr_last*0.015 if d_atr_last else 0)
    stop=event['cloud_high']+buffer if direction=='BEAR' else event['cloud_low']-buffer
    base['entry']=price;base['stop']=stop
    risk=(stop-price) if direction=='BEAR' else (price-stop)
    reward=(price-base['target']) if direction=='BEAR' else (base['target']-price)
    base['rr']=(reward/risk) if risk>0 else None
    aligned_hourly=clouds['1H']['slow']['state'] == ('BELOW' if direction=='BEAR' else 'ABOVE')
    daily_opposed=(clouds['1D']['slow']['state']==('ABOVE' if direction=='BEAR' else 'BELOW'))
    base['conflict']=bool(daily_opposed or (sector_bias not in ('UNKNOWN','MIXED',direction)))
    if not (is_classic or double_mtf):
        base['status']='WAIT';base['reason']='The nearer daily cloud is not D20/21 and no same-day Double MTF is confirmed.'
    elif base['conflict']:
        base['status']='CONFLICT';base['reason']='Daily/sector direction conflicts with the proposed intraday trade.'
    elif risk<=0:
        base['status']='WAIT';base['reason']='Price has crossed the cloud-side stop; wait for a new retest or break.'
    elif base['rr'] is not None and base['rr']<1.5:
        base['status']='EXTENDED';base['reason']='Too close to the next magnet versus the technical stop (R:R below 1.5).'
    elif not aligned_hourly:
        base['status']='WAIT';base['reason']='The confirmed hourly break has not held its directional cloud state.'
    elif grade=='B':
        base['status']='DEVELOPING';base['reason']='Confirmed break and target, but confluence is insufficient for A/A+.'
    else:
        base['status']='READY';base['reason']=('Confirmed same-day Double MTF with D50/55 ahead and acceptable checks.' if double_mtf else 'Confirmed hourly break with qualifying checks and remaining reward/risk.')
    return base


def summarize_row(result:dict):
    """Flat dataframe-safe record, no promises of win probabilities."""
    event=result.get('event') or {}
    return {'Symbol':result['symbol'],'Price':result['price'],
            'Direction':result.get('direction') or '—','Setup':result['setup'],
            'Status':result['status'],'Grade':result['grade'],'Checks':f"{result['score']}/4",
            'Gap × ATR':result['gap_atr'],'Gap left $':result['gap_left'],
            'Next Magnet':result['target'],'Stop reference':result['stop'],
            'R:R':result['rr'],'Market':result['market_bias'],
            '1H':result['clouds']['1H']['slow']['state'],
            'Daily':result['clouds']['1D']['slow']['state'],
            '10m':result['clouds']['10m']['fast']['state'],
            'RVOL':result['rvol'],'Velocity':result['velocity'],
            'Trigger time':str(event.get('time','—')),
            'Reason':result['reason']}
