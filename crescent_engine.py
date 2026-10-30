"""Crescent V7 standalone decision engine. Deterministic, no IO or Streamlit.
Research hypotheses, not validated prediction probabilities or broker signals.
All daily trade plans use COMPLETED sessions and freeze immutable levels.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, time
from zoneinfo import ZoneInfo
from typing import Optional
import math
import numpy as np
import pandas as pd

ET = ZoneInfo('America/New_York')
SECTORS = {
    'XLV':'Healthcare','XLP':'Consumer Staples','XLU':'Utilities','XLE':'Energy',
    'XLK':'Technology','XLY':'Consumer Discretionary','XLF':'Financials',
    'XLI':'Industrials','XLB':'Materials','XLC':'Communication Services','XLRE':'Real Estate',
}
BENCHMARKS=('SPY','QQQ','RSP','IWM')
DEFENSIVE=('XLV','XLP','XLU')
CROSS_ASSETS={
 '^VIX':'VIX','^TNX':'US 10-year yield*','DX-Y.NYB':'DXY',
 'GC=F':'Gold futures','CL=F':'WTI futures','HG=F':'Copper futures',
 'BTC-USD':'Bitcoin','JPY=X':'USD/JPY','^N225':'Nikkei 225',
 '^KS11':'KOSPI'
}
# Yield index units and Yahoo quote conventions vary; display raw rather than invent basis points.
DEFAULT_WATCH=('STX','MRVL','U','ANF')
ETF_TRADE_CANDIDATES=('XBI','IHI','KRE','XRT','SMH','GDX','GLD','TLT','IBIT')
LEVERAGED_ETFS=('TQQQ','SQQQ','SOXL','SOXS','LABU','LABD','SPXL','SPXS')


def money(v):
    return f'${float(v):,.2f}' if finite(v) else '—'


def finite(v):
    try: return math.isfinite(float(v))
    except (TypeError,ValueError): return False


def normalise(raw):
    """Require strictly ordered OHLCV with consistent, session-indexed daily bars."""
    if raw is None or len(raw)==0:return pd.DataFrame()
    df=raw.copy()
    if isinstance(df.columns,pd.MultiIndex):df.columns=df.columns.get_level_values(0)
    df.columns=[str(c).strip().title() for c in df.columns]
    must=['Open','High','Low','Close','Volume']
    if any(c not in df for c in must):return pd.DataFrame()
    df=df[must].apply(pd.to_numeric,errors='coerce')
    df=df.replace([np.inf,-np.inf],np.nan).dropna(subset=['Open','High','Low','Close'])
    df=df[(df['Close']>0)&(df['High']>=df['Low'])]
    if not isinstance(df.index,pd.DatetimeIndex):return pd.DataFrame()
    if df.index.tz is not None:df.index=df.index.tz_convert(ET).tz_localize(None)
    df.index=df.index.normalize()
    df=df[~df.index.duplicated(keep='last')].sort_index()
    return df


def complete_daily(raw,now=None):
    """Remove possibly forming US session from daily histories before 16:15 ET.
    A 15-min buffer cannot certify a provider's bar; provider freshness is also shown.
    """
    frame=normalise(raw)
    now=now or datetime.now(ET)
    if now.tzinfo is None:now=now.replace(tzinfo=ET)
    here=now.astimezone(ET)
    if len(frame) and frame.index[-1].date()==here.date() and here.time()<time(16,15):
        return frame.iloc[:-1]
    return frame


def ret(close,n):
    if len(close)<n+1 or not finite(close.iloc[-1]) or not finite(close.iloc[-n-1]) or close.iloc[-n-1]<=0:return None
    return (float(close.iloc[-1]/close.iloc[-n-1])-1)*100


def atr14(df):
    if len(df)<15:return None
    prev=df.Close.shift(1)
    tr=pd.concat([df.High-df.Low,(df.High-prev).abs(),(df.Low-prev).abs()],axis=1).max(axis=1)
    val=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean().iloc[-1]
    return float(val) if finite(val) and val>0 else None


def snapshot(frame):
    f=normalise(frame)
    if len(f)<65:return None
    c=f.Close; a=atr14(f)
    if not a:return None
    e9=c.ewm(span=9,adjust=False,min_periods=9).mean()
    e21=c.ewm(span=21,adjust=False,min_periods=21).mean()
    e50=c.ewm(span=50,adjust=False,min_periods=50).mean()
    last=float(c.iloc[-1]);
    dayrange=(f.High-f.Low).replace(0,np.nan)
    recent=dayrange.iloc[-5:].mean(); old=dayrange.iloc[-20:-5].mean()
    vol=(c*f.Volume).iloc[-21:-1].mean()
    price_span=float(f.High.iloc[-1]-f.Low.iloc[-1])
    return dict(price=last,asof=str(f.index[-1].date()),asof_date=f.index[-1],
        ema9=float(e9.iloc[-1]),ema21=float(e21.iloc[-1]),ema50=float(e50.iloc[-1]),
        ema21_slope=float(e21.iloc[-1]-e21.iloc[-6]),atr=a,
        r5=ret(c,5),r10=ret(c,10),r21=ret(c,21),r60=ret(c,60),
        dvol=float(vol) if finite(vol) else None,
        dryup=float(recent/old) if finite(recent) and finite(old) and old>0 else None,
        high20=float(f.High.iloc[-21:-1].max()),high60=float(f.High.iloc[-61:-1].max()),
        low20=float(f.Low.iloc[-21:-1].min()),
        range_pos=float((last-f.Low.iloc[-1])/price_span) if price_span>0 else 0.5,
        last_high=float(f.High.iloc[-1]),last_low=float(f.Low.iloc[-1]),
        prev3low=float(f.Low.iloc[-4:].min()),prev3high=float(f.High.iloc[-4:].max()),
        trend_up=last>e21.iloc[-1]>e50.iloc[-1] and e21.iloc[-1]>e21.iloc[-6],
        trend_down=last<e21.iloc[-1]<e50.iloc[-1] and e21.iloc[-1]<e21.iloc[-6],
        distance21_atr=(last-e21.iloc[-1])/a,
        candle_vol=float(f.Volume.iloc[-1]),
        volume20=float(f.Volume.iloc[-21:-1].mean()),
    )


def regime(history,now=None):
    """Descriptive regime and sector rotation using ETF proxies, never fabricated breadth."""
    prepared={s:complete_daily(f,now) for s,f in history.items()}
    spy=prepared.get('SPY',pd.DataFrame())
    anchor=snapshot(spy)
    if not anchor:return {'posture':'UNKNOWN','rotation':'UNKNOWN','reason':'SPY completed daily history unavailable',
        'sectors':pd.DataFrame(), 'benchmarks':pd.DataFrame(),'asof':None,'cross':pd.DataFrame(), 'coverage':0}
    anchor_day=anchor['asof_date']
    rows=[]; b_rows=[];x_rows=[]
    for s in list(SECTORS)+list(BENCHMARKS)+list(CROSS_ASSETS):
        f=prepared.get(s,pd.DataFrame());m=snapshot(f)
        if not m:continue
        if s not in CROSS_ASSETS and m['asof_date']!=anchor_day:continue
        # Global exchanges/24h assets may close on different calendar dates.
        # Show them with their own As of instead of pretending they align to SPY.
        if s in CROSS_ASSETS and abs((m['asof_date']-anchor_day).days)>2:continue
        row={'Symbol':s,'Name':SECTORS.get(s,s),'Close':m['price'],'5D %':m['r5'],
             '10D %':m['r10'],'21D %':m['r21'],'60D %':m['r60'],
             'Vs SPY 5D pp':m['r5']-anchor['r5'], 'Vs SPY 21D pp':m['r21']-anchor['r21'],
             'Above 21':m['price']>m['ema21'],'Above 50':m['price']>m['ema50'],
             'Trend':'UP' if m['trend_up'] else 'DOWN' if m['trend_down'] else 'MIXED',
             'Accel pp': (m['r5']-((1+m['r10']/100)/(1+m['r5']/100)-1)*100) if m['r5'] is not None and m['r10'] is not None and 1+m['r5']/100>0 else np.nan,
             'As of':m['asof']}
        if s in SECTORS: rows.append(row)
        elif s in BENCHMARKS:b_rows.append(row)
        else:
            row['Name']=CROSS_ASSETS[s];x_rows.append(row)
    sectors=pd.DataFrame(rows)
    bench=pd.DataFrame(b_rows)
    cross=pd.DataFrame(x_rows)
    if not sectors.empty:
        sectors['Rotation']=np.select([
            (sectors['Vs SPY 21D pp']>0)&(sectors['Vs SPY 5D pp']>0)&sectors['Above 21'],
            (sectors['Vs SPY 21D pp']>0)&(sectors['Vs SPY 5D pp']<0),
            (sectors['Vs SPY 5D pp']>0)&(sectors['Vs SPY 21D pp']<=0),
            (sectors['Vs SPY 21D pp']<0)&(sectors['Vs SPY 5D pp']<0)],
            ['LEADING','COOLING','EMERGING','LAGGING'],default='MIXED')
        sectors=sectors.sort_values(['Vs SPY 21D pp','Vs SPY 5D pp'],ascending=False)
    upward=sum(bool(m.get('Above 21',False)) for m in b_rows)
    if len(b_rows)<3:posture='UNKNOWN';reason='Fewer than three benchmark series are current.'
    elif upward>=3:posture='BROADLY SUPPORTIVE';reason=f'{upward}/{len(b_rows)} major benchmarks above daily 21 EMA.'
    elif upward==0:posture='DEFENSIVE / RISK-OFF';reason='Major benchmarks below daily 21 EMA.'
    else:posture='SELECTIVE / MIXED';reason=f'{upward}/{len(b_rows)} major benchmarks above daily 21 EMA.'
    rotation='INSUFFICIENT COVERAGE'
    if not sectors.empty and len(sectors)>=8:
        rs=sectors.set_index('Symbol')
        if all(s in rs.index for s in DEFENSIVE+('XLK',)):
            defensive_rs=float(rs.loc[list(DEFENSIVE),'Vs SPY 21D pp'].mean())
            tech_rs=float(rs.loc['XLK','Vs SPY 21D pp'])
            count=sum(bool(rs.loc[s,'Vs SPY 21D pp']>0) for s in DEFENSIVE)
            if defensive_rs>=2 and tech_rs<0 and count>=2:rotation='DEFENSIVE LEADERSHIP'
            elif defensive_rs>0 and tech_rs<defensive_rs:rotation='DEFENSIVE TILT'
            else:rotation='MIXED / CYCLICAL'
        leaders=', '.join(sectors['Name'].head(3))
        reason+=f' ETF relative leaders: {leaders}.'
    return {'posture':posture,'rotation':rotation,'reason':reason,'sectors':sectors,
            'benchmarks':bench,'cross':cross,'asof':anchor['asof'],'coverage':len(sectors),
            'market_atr':anchor['atr'],'spy':anchor}


@dataclass
class Plan:
    id:str
    symbol:str
    sector:str
    setup:str
    horizon:str
    direction:str
    status:str
    trigger:float
    stop:float
    target:Optional[float]
    rr:Optional[float]
    score:float
    reason:str
    blocker:str
    asof:str
    source:str
    created_at:str
    max_entry:float
    distance_atr:float
    sector_rotation:str
    state_note:str=''
    def to_dict(self):return asdict(self)


def _rr(entry,stop,target,sign):
    risk=sign*(entry-stop)
    reward=sign*(target-entry) if finite(target) else None
    if not risk or risk<=0 or reward is None or reward<=0:return None
    return float(reward/risk)


def _target_from_past(f,trigger,sign,atr_value):
    """Next confirmed swing pivot (two bars on each side) on earlier daily bars.
    Nearby single-bar noise is not called a meaningful resistance/support target.
    If none exists, report UNKNOWN rather than manufacture an ATR projection.
    """
    prior=f.iloc[-90:-1]
    if len(prior)<8 or not finite(atr_value):return None
    levels=[]
    for i in range(2,len(prior)-2):
        if sign==1:
            v=float(prior.High.iloc[i])
            pivot=v>float(prior.High.iloc[i-2:i].max()) and v>=float(prior.High.iloc[i+1:i+3].max())
            if pivot and v>trigger+0.45*atr_value:levels.append(v)
        else:
            v=float(prior.Low.iloc[i])
            pivot=v<float(prior.Low.iloc[i-2:i].min()) and v<=float(prior.Low.iloc[i+1:i+3].min())
            if pivot and v<trigger-0.45*atr_value:levels.append(v)
    if not levels:return None
    return float(min(levels) if sign==1 else max(levels))


def make_plans(symbol,frame,spy_metrics,sector,sector_rs,regime_label,now=None,source='Yahoo delayed'):
    """Completed EOD bars: sets ARMED/WATCH/BLOCKED, never LIVE READY.

    The frozen levels are hypotheses requiring intraday confirmation. No same-day high
    can be used to claim the entry was known earlier.
    """
    f=complete_daily(frame,now)
    m=snapshot(f)
    if not m or not spy_metrics or m['asof']!=spy_metrics['asof']:return []
    if not m['dvol'] or m['dvol']<8_000_000 or m['price']<5:return []
    if not finite(m['r5']) or not finite(m['r21']):return []
    rel5=m['r5']-spy_metrics['r5'];rel21=m['r21']-spy_metrics['r21']
    sector_available=finite(sector_rs)
    sector_rs=float(sector_rs) if sector_available else 0.0
    plans=[]
    for mode in ('TREND PULLBACK','BASE BREAKOUT','FAILED BOUNCE'):
        direction='SHORT' if mode=='FAILED BOUNCE' else 'LONG';sign=-1 if direction=='SHORT' else 1
        if direction=='LONG':
            if not m['trend_up'] or rel21<=0:continue
            if mode=='TREND PULLBACK':
                near=abs(m['distance21_atr'])<=1.05 and m['range_pos']>=0.48
                if not near:continue
                trigger=m['last_high']+0.03*m['atr']
                stop=m['prev3low']-0.1*m['atr']
                desc='Daily uptrend; pullback near 21 EMA with improving close.'
            else:
                near= abs(m['price']-m['high20'])/m['atr']<=1.25 and m['dryup'] is not None and m['dryup']<1.15
                if not near:continue
                trigger=max(m['last_high'],m['high20'])+0.03*m['atr']
                stop=m['prev3low']-0.1*m['atr']
                desc='Daily uptrend; near 20-day pivot after contraction.'
        else:
            # SHORT is independent thesis; not a reversal of a missed long.
            if not m['trend_down'] or rel21>=0:continue
            near=abs(m['distance21_atr'])<=1.1 and m['range_pos']<=.48
            if not near:continue
            trigger=m['last_low']-0.03*m['atr']
            stop=m['prev3high']+0.1*m['atr']
            desc='Confirmed daily downtrend with weak bounce; independent short watch.'
        risk=sign*(trigger-stop)
        if risk<=0 or risk>3*m['atr']:continue
        target=_target_from_past(f,trigger,sign,m['atr'])
        rr=_rr(trigger,stop,target,sign)
        extension=abs(trigger-m['ema21'])/m['atr']
        score=40+min(16,max(-10,rel21))*1.0 + min(13,max(-8,sign*rel5))*1.2
        score+=8 if sign*sector_rs>0 else -6
        score+=10 if m['dryup'] is not None and m['dryup']<.85 else 0
        score+=5 if extension<=1.4 else -5
        score+=min(10,rr*4) if rr is not None else 0
        score=float(round(min(100,max(0,score)),1))
        if extension>2.5:
            status='EXTENDED';blocker='Trigger too far from daily 21 EMA.'
        elif not sector_available:
            status='WATCH';blocker='Sector ETF context unavailable; verify leadership before promotion.'
        elif rr is None:
            status='WATCH';blocker='Next structural obstacle / reward-risk not established.'
        elif rr<1.5:
            status='WATCH';blocker='Reward-to-risk below 1.5 at planned trigger.'
        elif direction=='LONG' and regime_label=='DEFENSIVE / RISK-OFF' and sector_rs<=0:
            status='BLOCKED';blocker='Weak market and no positive sector-relative evidence.'
        elif direction=='SHORT' and sign*sector_rs<=0:
            status='BLOCKED';blocker='Short thesis lacks sector-relative confirmation.'
        else:status='ARMED';blocker='Await completed intraday trigger and VWAP confirmation.'
        maxentry=trigger+sign*min(.25*m['atr'],.25*risk)
        plans.append(Plan(
            id=f"{m['asof']}:{symbol}:{mode.replace(' ','_')}",symbol=symbol,sector=sector,
            setup=mode,horizon='SWING',direction=direction,status=status,trigger=round(trigger,2),
            stop=round(stop,2),target=round(target,2) if finite(target) else None,
            rr=round(rr,2) if rr is not None else None,score=score,reason=desc,
            blocker=blocker,asof=m['asof'],source=source,created_at=(now or datetime.now(ET)).isoformat(),
            max_entry=round(maxentry,2),distance_atr=round(extension,2),sector_rotation=('UNKNOWN' if not sector_available else 'OUTPERFORMING' if sector_rs>0 else 'LAGGING'),
            state_note='Paper plan — not a live order. Confirm earnings and catalyst status.'
        ))
    return plans


def rank_plans(plans,max_per_sector=2):
    """Favor ARMED and diverse sectors; do not claim a rank proves expectancy."""
    order={'ARMED':0,'WATCH':1,'BLOCKED':2,'EXTENDED':3,'INVALID':4,'STALE':5}
    uniq={}
    for p in sorted(plans,key=lambda x:(order.get(x.status,9),-x.score,x.symbol)):
        # Avoid displaying two competing trade families for the same ticker by default
        uniq.setdefault(p.symbol,p)
    result=[]; counts={}
    for p in uniq.values():
        if counts.get(p.sector,0)>=max_per_sector:continue
        result.append(p);counts[p.sector]=counts.get(p.sector,0)+1
    return result


def intraday_vwap(frame):
    """Regular session VWAP resets each day; timestamped 5m candles. Does not
    assume that a later cumulative VWAP value was available before that bar.
    """
    if frame is None or len(frame)==0:return pd.DataFrame()
    f=frame.copy()
    if f.index.tz is None: f.index=f.index.tz_localize(ET)
    else:f.index=f.index.tz_convert(ET)
    f.columns=[str(c).title() for c in f.columns]
    f=f.between_time('09:30','15:59').copy()
    if f.empty:return f
    f=f.sort_index(); f['Volume']=pd.to_numeric(f['Volume'],errors='coerce').fillna(0)
    typical=(f.High+f.Low+f.Close)/3
    day=pd.Index(f.index.date)
    vol=f.Volume.groupby(day).cumsum()
    dollars=(typical*f.Volume).groupby(day).cumsum()
    f['VWAP']=dollars/vol.replace(0,np.nan)
    return f


def ten_minute_bars(five,now=None):
    """Two exact 5m bars per RTH 10m bucket; drops missing or incomplete bars."""
    if five is None or len(five)==0:return pd.DataFrame()
    f=five.copy();f.columns=[str(c).title() for c in f.columns]
    if f.index.tz is None:f.index=f.index.tz_localize(ET)
    else:f.index=f.index.tz_convert(ET)
    f=f.between_time('09:30','15:59').sort_index()
    now=now or datetime.now(ET)
    if now.tzinfo is None:now=now.replace(tzinfo=ET)
    now=now.astimezone(ET)
    output=[]
    for _,g in f.groupby(f.index.date):
        key=((g.index.hour*60+g.index.minute-570)//10)
        for bucket,pair in g.groupby(key):
            if bucket<0 or len(pair)!=2:continue
            expected=pd.Timestamp(pair.index[0].date(),tz=ET)+pd.Timedelta(minutes=570+10*int(bucket))
            if pair.index[0]!=expected or pair.index[1]!=expected+pd.Timedelta(minutes=5):continue
            if expected+pd.Timedelta(minutes=10)>now:continue
            output.append((expected,float(pair.Open.iloc[0]),float(pair.High.max()),float(pair.Low.min()),float(pair.Close.iloc[-1]),float(pair.Volume.sum())))
    if not output:return pd.DataFrame(columns=['Open','High','Low','Close','Volume'])
    return pd.DataFrame(output,columns=['Time','Open','High','Low','Close','Volume']).set_index('Time')


def live_check(plan,five,now=None,opening_cutoff=time(9,50),max_age_minutes=20,manual_event_block=False,
               sector_five=None,require_sector=False,market_five=None):
    """Research confirmation on completed 10m bars. Never automatic broker order.
    Requires actual RTH live data, and respects frozen overnight plan.
    """
    p=plan.to_dict() if hasattr(plan,'to_dict') else dict(plan)
    now=now or datetime.now(ET)
    if now.tzinfo is None:now=now.replace(tzinfo=ET)
    now=now.astimezone(ET)
    if manual_event_block:return {'status':'BLOCKED','why':'Manual macro/earnings event restriction active.','vwap':None,'price':None}
    if p.get('status')!='ARMED':
        return {'status':'BLOCKED','why':'Only a frozen ARMED plan is eligible for live confirmation; revalidate this watch in the Night Plan.','vwap':None,'price':None}
    try:
        plan_date=pd.Timestamp(p['asof']).date()
        elapsed_sessions=len(pd.bdate_range(start=plan_date+pd.Timedelta(days=1),end=now.date()))
        if elapsed_sessions>1:
            return {'status':'STALE','why':'The frozen overnight plan predates the previous trading session; rebuild the levels.','vwap':None,'price':None}
    except (ValueError,TypeError,KeyError):
        return {'status':'STALE','why':'Plan date invalid or unknown.','vwap':None,'price':None}
    if now.weekday()>=5 or now.time()<time(9,30) or now.time()>=time(16,0):
        return {'status':'MARKET CLOSED','why':'No live entry confirmation outside regular US cash hours.','vwap':None,'price':None}
    if now.time()<opening_cutoff:
        return {'status':'WAIT','why':f'Observe until {opening_cutoff.strftime("%I:%M %p")} ET; no opening entries.','vwap':None,'price':None}
    tf=ten_minute_bars(five,now)
    if tf.empty:return {'status':'STALE','why':'No completed, valid 10-minute bars.','vwap':None,'price':None}
    latest=tf.index[-1]
    if latest.date()!=now.date() or (now-latest).total_seconds()/60>max_age_minutes+10:
        return {'status':'STALE','why':'Last completed 10-minute bar is too old for live confirmation.','vwap':None,'price':None}
    vf=intraday_vwap(five)
    vf=vf[(vf.index.date==now.date()) & (vf.index<latest+pd.Timedelta(minutes=10))]
    if vf.empty or not finite(vf.VWAP.iloc[-1]):return {'status':'STALE','why':'Session VWAP unavailable.','vwap':None,'price':None}
    price=float(tf.Close.iloc[-1]);vw=float(vf.VWAP.iloc[-1]);sign=1 if p['direction']=='LONG' else -1
    info={'price':round(price,2),'vwap':round(vw,2),'bar_time':str(latest),'status':'WAIT','why':''}
    if sign*(price-p['stop'])<=0:
        info.update(status='INVALID',why='Underlying breached the frozen structural invalidation.');return info
    if sign*(price-p['trigger'])<=0:
        info.update(status='WAIT',why='Price has not closed beyond the planned trigger.');return info
    if sign*(price-p['max_entry'])>0:
        info.update(status='EXTENDED',why='Price beyond the maximum planned entry; do not chase.');return info
    if sign*(price-vw)<=0:
        info.update(status='WAIT',why='VWAP does not confirm the planned direction.');return info
    if require_sector:
        sector10=ten_minute_bars(sector_five,now)
        sector_v=intraday_vwap(sector_five)
        sector_v=sector_v[(sector_v.index.date==now.date()) & (sector_v.index<latest+pd.Timedelta(minutes=10))] if not sector_v.empty else sector_v
        if sector10.empty or sector_v.empty or sector10.index[-1]<latest-pd.Timedelta(minutes=10):
            info.update(status='STALE',why='Matching fresh sector confirmation is unavailable.');return info
        s_close=float(sector10.Close.iloc[-1]);s_vwap=float(sector_v.VWAP.iloc[-1])
        info['sector_price']=round(s_close,2);info['sector_vwap']=round(s_vwap,2)
        if not finite(s_vwap) or sign*(s_close-s_vwap)<=0:
            info.update(status='CONFLICT',why='Sector ETF is not confirming the planned direction.');return info
    if market_five is not None:
        m10=ten_minute_bars(market_five,now)
        mv=intraday_vwap(market_five)
        mv=mv[(mv.index.date==now.date()) & (mv.index<latest+pd.Timedelta(minutes=10))] if not mv.empty else mv
        if len(m10) and len(mv) and finite(mv.VWAP.iloc[-1]):
            # Diagnostic only: relative sector leadership can remain viable with weak SPY.
            info['market_agrees']=sign*(float(m10.Close.iloc[-1])-float(mv.VWAP.iloc[-1]))>0
    if not finite(p.get('target')):
        info.update(status='WAIT',why='Structural target not established; risk/reward unverified.');return info
    rr=_rr(price,p['stop'],p['target'],sign)
    info['remaining_rr']=round(rr,2) if rr is not None else None
    if rr is None or rr<1.5:
        info.update(status='EXTENDED',why='Remaining reward/risk below 1.5.');return info
    # Confirm that the latest RTH 10m candle is not going against the thesis
    if sign*(float(tf.Close.iloc[-1])-float(tf.Open.iloc[-1]))<0:
        info.update(status='WAIT',why='Latest completed 10m candle did not close with the planned direction.');return info
    info.update(status='READY',why='Completed 10m close beyond frozen trigger, VWAP aligned, entry zone and remaining R:R valid. Review manually.')
    return info


def mock_regime_note(rotation):
    return 'Defensive leadership detected from sector ETF proxies; confirm breadth and catalysts.' if rotation=='DEFENSIVE LEADERSHIP' else 'Sector leadership remains mixed; examine relative strength before selecting trades.'


def preopen_assessment(plan,quote_price,previous_close,quote_timestamp,now=None,max_age_minutes=25):
    """Pre-market price is scenario context; it can NEVER turn a plan READY."""
    p=plan.to_dict() if hasattr(plan,'to_dict') else dict(plan)
    now=now or datetime.now(ET)
    if now.tzinfo is None:now=now.replace(tzinfo=ET)
    now=now.astimezone(ET)
    if now.weekday()>=5 or now.time()<time(4,0) or now.time()>=time(9,30):
        return {'status':'NO PRE-OPEN SESSION','reason':'This review only applies between 04:00 and 09:30 ET on weekdays.'}
    if quote_timestamp is None or not finite(quote_price) or not finite(previous_close) or previous_close<=0:
        return {'status':'UNKNOWN','reason':'Pre-market quotes or previous close unavailable.'}
    ts=pd.Timestamp(quote_timestamp)
    if ts.tzinfo is None:return {'status':'UNKNOWN','reason':'Quote timezone unavailable.'}
    ts=ts.tz_convert(ET)
    age=(now-ts.to_pydatetime()).total_seconds()/60
    if ts.date()!=now.date() or age>max_age_minutes or age<0:
        return {'status':'STALE','reason':'Pre-market data is stale or outside this session.'}
    change=(float(quote_price)/float(previous_close)-1)*100
    sign=1 if p['direction']=='LONG' else -1
    status='RECHECK PLAN';message='Pre-open price does not invalidate the plan; no entry permission until RTH confirmation.'
    if sign*(float(quote_price)-float(p['stop']))<=0:
        status='SUPPORT AT RISK';message='Pre-open price beyond planned invalidation. Reassess the setup after the open.'
    elif sign*(float(quote_price)-float(p['max_entry']))>0:
        status='EXTENDED';message='Pre-open price beyond the maximum entry zone. Do not chase the gap.'
    return {'status':status,'reason':message,'price':float(quote_price),
            'gap_pct':float(change),'asof':ts.isoformat()}
