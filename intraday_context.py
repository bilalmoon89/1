"""Read-only intraday context, independent of the existing entry/ranking engine."""
from datetime import datetime, time, timedelta
import pandas as pd
from crescent_engine import ET, SECTORS, finite, normalise

from market_symbols import DISPLAY_BENCHMARKS
from session_validity import regular_status


def intraday_bars(raw):
    """Preserve individual bar timestamps; the daily normalizer collapses them."""
    if raw is None or raw.empty:return pd.DataFrame()
    frame=raw.copy()
    frame.columns=[str(c).strip().title() for c in frame.columns]
    columns=['Open','High','Low','Close','Volume']
    if not set(columns).issubset(frame.columns) or not isinstance(frame.index,pd.DatetimeIndex):return pd.DataFrame()
    frame=frame[columns].apply(pd.to_numeric,errors='coerce').dropna(subset=['Open','High','Low','Close'])
    frame=frame[(frame.Close>0)&(frame.High>=frame.Low)]
    return frame[~frame.index.duplicated(keep='last')].sort_index()


def fetch_intraday(symbols):
    import yfinance as yf
    raw=yf.download(list(symbols),period='5d',interval='5m',auto_adjust=False,
        group_by='ticker',threads=True,progress=False,prepost=False,timeout=15)
    frames={}; failures={}
    for symbol in symbols:
        try:
            if isinstance(raw.columns,pd.MultiIndex):
                selected=raw[symbol] if symbol in raw.columns.get_level_values(0) else raw.xs(symbol,level=1,axis=1)
            else:selected=raw if len(symbols)==1 else pd.DataFrame()
            frame=intraday_bars(selected)
        except KeyError:frame=pd.DataFrame()
        if frame.empty or frame.index.tz is None:
            failures[symbol]='No timezone-aware 5-minute bars'
        else:frames[symbol]=frame
    if '^VIX' in symbols and '^VIX' not in frames:
        try:
            frame=intraday_bars(yf.Ticker('^VIX').history(period='5d',interval='5m',prepost=False,auto_adjust=False,actions=False))
            if not frame.empty and frame.index.tz is not None:
                frames['^VIX']=frame;failures.pop('^VIX',None)
        except Exception:pass
    return frames,failures


def vix_reading(prepared,daily,now):
    """VIX has its own delayed index clock; it is never aligned as an ETF."""
    frame=prepared.get('^VIX')
    prior=normalise(daily.get('^VIX',pd.DataFrame()))
    if frame is not None and not frame.empty:
        stamp=frame.index[-1]+pd.Timedelta(minutes=5)
        frame=frame[frame.index.date==frame.index[-1].date()]
        previous=prior[prior.index.date<stamp.date()] if not prior.empty else prior
        close=float(frame.Close.iloc[-1])
        previous_close=float(previous.Close.iloc[-1]) if not previous.empty else None
        age=max(0,(now-stamp.to_pydatetime()).total_seconds())
        opened=now.weekday()<5 and time(9,30)<=now.time()<time(16)
        status=regular_status(stamp,now,max_age_seconds=1800)
        if status=='CURRENT' and age>600:status='DELAYED'
        return {'Symbol':'^VIX','Name':'VIX','Last':close,
            'Today %':(close/previous_close-1)*100 if previous_close else None,
            'From open %':None,'VWAP':None,'Vs VWAP %':None,'Vs SPY pp':None,
            'Bar close':stamp.isoformat(),'Status':status,'Source':'Yahoo VIX index · separate timestamp'},frame
    if not prior.empty:
        stamp=prior.index[-1]
        close=float(prior.Close.iloc[-1])
        return {'Symbol':'^VIX','Name':'VIX','Last':close,'Today %':None,'From open %':None,
            'VWAP':None,'Vs VWAP %':None,'Vs SPY pp':None,'Bar close':str(stamp.date()),
            'Status':'LAST DAILY CLOSE','Source':'Yahoo completed daily close'},pd.DataFrame()
    return None,pd.DataFrame()


def session_rows(frames,daily,now=None):
    """Compare completed RTH bars at the SPY timestamp, never daily substitutes."""
    now=now or datetime.now(ET)
    if now.tzinfo is None:raise ValueError('Timezone-aware clock required')
    now=now.astimezone(ET)
    prepared={}
    for symbol,raw in frames.items():
        f=intraday_bars(raw)
        if f.empty or f.index.tz is None:continue
        f.index=f.index.tz_convert(ET)
        f=f[(f.index.time>=time(9,30))&(f.index.time<time(16))&(f.index+pd.Timedelta(minutes=5)<=now)]
        if not f.empty:prepared[symbol]=f
    spy=prepared.get('SPY')
    if spy is None:
        vix,series=vix_reading(prepared,daily,now)
        return {'rows':pd.DataFrame([vix]) if vix else pd.DataFrame(),'frames':{'^VIX':series} if vix else {},'asof':None,'session':None,'status':'UNAVAILABLE'}
    anchor=spy.index[-1];day=anchor.date()
    market_open=now.weekday()<5 and time(9,30)<=now.time()<time(16)
    status=regular_status(anchor+pd.Timedelta(minutes=5),now)
    rows=[];series={}
    for symbol,f in prepared.items():
        if symbol=='^VIX':continue
        f=f[(f.index.date==day)&(f.index<=anchor)]
        if f.empty or f.index[-1]!=anchor:continue
        prior=normalise(daily.get(symbol,pd.DataFrame()))
        if not prior.empty:prior=prior[prior.index.date<day]
        previous=float(prior.Close.iloc[-1]) if not prior.empty else None
        close=float(f.Close.iloc[-1]);volume=float(f.Volume.sum())
        expected=pd.date_range(pd.Timestamp(datetime.combine(day,time(9,30)),tz=ET),anchor,freq='5min')
        complete_session=len(f)==len(expected) and f.index.equals(expected)
        vwap=float((((f.High+f.Low+f.Close)/3)*f.Volume).sum()/volume) if volume>0 and complete_session else None
        opened=float(f.Open.iloc[0])
        # No from-open reading unless the actual 09:30 opening candle exists.
        from_open=(close/opened-1)*100 if f.index[0].time()==time(9,30) and opened>0 else None
        rows.append({'Symbol':symbol,'Name':SECTORS.get(symbol,symbol),'Last':close,
            'Today %':(close/previous-1)*100 if previous and previous>0 else None,
            'From open %':from_open,'VWAP':vwap,'Vs VWAP %':(close/vwap-1)*100 if vwap else None,
            'Bar close':(f.index[-1]+pd.Timedelta(minutes=5)).isoformat(),'Status':status})
        series[symbol]=f
    frame=pd.DataFrame(rows)
    if frame.empty:return {'rows':frame,'frames':{},'asof':None,'session':str(day),'status':'UNAVAILABLE'}
    spy_today=next((r['Today %'] for r in rows if r['Symbol']=='SPY'),None)
    frame['Vs SPY pp']=[r-spy_today if finite(r) and finite(spy_today) else None for r in frame['Today %']]
    vix,vix_series=vix_reading(prepared,daily,now)
    if vix:
        frame=pd.concat([frame,pd.DataFrame([vix])],ignore_index=True)
        if not vix_series.empty:series['^VIX']=vix_series
    return {'rows':frame,'frames':series,'asof':(anchor+pd.Timedelta(minutes=5)).isoformat(),
        'session':str(day),'status':status}


def tradingview_quotes(symbols):
    """Public screener quote snapshots, never used to grant entry permission."""
    from tradingview_screener import Query,col
    _,frame=(Query().set_markets('america')
        .select('name','exchange','close','change','change_from_open','VWAP','update_mode')
        .where(col('name').isin(list(symbols))).limit(100).get_scanner_data(timeout=12))
    if frame is None or frame.empty:return pd.DataFrame()
    frame=frame.rename(columns={'name':'Symbol','exchange':'Exchange','close':'Last','change':'Today %',
        'change_from_open':'From open %','update_mode':'Feed mode'})
    def feed_label(value):
        text=str(value)
        if text.startswith('delayed_streaming_'):
            try:return f'{int(text.rsplit("_",1)[1])//60} min delayed'
            except ValueError:pass
        return text
    frame['Feed mode']=frame['Feed mode'].map(feed_label)
    for column in ['Last','Today %','From open %','VWAP']:
        frame[column]=pd.to_numeric(frame[column],errors='coerce').round(2)
    frame['Retrieved ET']=datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S ET')
    return frame[['Symbol','Exchange','Last','Today %','From open %','VWAP','Feed mode','Retrieved ET']]
