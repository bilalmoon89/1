"""Bounded, small-batch provider calls for the standalone liquid scan."""
import threading

BATCH_SIZE=12


def bounded_call(function,*args,timeout=12):
    """Run a provider call with a wall-clock limit.

    Each call gets its own daemon thread, so a provider request that hangs past its
    limit can never occupy a shared worker and block later requests (a shared
    2-worker pool did exactly that). The abandoned thread ends when the provider's
    own network timeout fires.
    """
    box={}
    def run():
        try:box['value']=function(*args)
        except BaseException as exc:box['error']=exc
    worker=threading.Thread(target=run,name='crescent-feed',daemon=True)
    worker.start();worker.join(timeout)
    if worker.is_alive():
        raise TimeoutError(f'Provider exceeded {timeout}s request limit')
    if 'error' in box:raise box['error']
    return box.get('value')


def _download(symbols):
    from crescent_feeds import _extract_symbol
    from sector_map import yahoo_symbol
    frames={};failures={}
    for symbol in symbols:
        if symbol not in SINA_FUTURES:continue
        try:
            frame=_sina_daily(SINA_FUTURES[symbol])
            if len(frame)>=200:frames[symbol]=frame
            else:failures[symbol]=f'{len(frame)} usable daily bars from Sina; 200 required'
        except Exception as exc:failures[symbol]=f'Sina futures feed: {type(exc).__name__}: {str(exc)[:80]}'
    wanted={yahoo_symbol(s):s for s in symbols if s not in SINA_FUTURES}
    if not wanted:return frames,failures
    import yfinance as yf
    request=list(wanted)
    raw=yf.download(request,period='1y',interval='1d',auto_adjust=False,
        group_by='ticker',threads=4,progress=False,actions=False,timeout=8)
    for ysym,symbol in wanted.items():
        frame=_extract_symbol(raw,ysym,request)
        if len(frame)>=200:frames[symbol]=frame
        else:failures[symbol]=f'{len(frame)} usable daily bars; 200 required'
    return frames,failures


def fetch_batch(symbols):
    try:return bounded_call(_download,tuple(symbols),timeout=12)
    except Exception as exc:
        return {},{s:f'{type(exc).__name__}: {str(exc)[:100]}' for s in symbols}


def fetch_classification(symbols):
    from liquid_uptrend import fetch_industries
    try:return bounded_call(fetch_industries,tuple(symbols),timeout=8)
    except Exception:return {s:{'industry':'','key':'','source':'Unavailable'} for s in symbols}


def _session_quotes(symbols):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from tradingview_screener import Query,col
    fields=('name','exchange','close','high','low','volume','change','change_from_open',
        'VWAP','relative_volume_10d_calc','SMA50','SMA200','time','last_bar_update_time','update_mode','industry')
    _,frame=(Query().set_markets('america').select(*fields)
        .where(col('name').isin(list(symbols))).limit(len(symbols)*2).get_scanner_data(timeout=8))
    retrieved=datetime.now(ZoneInfo('America/New_York')).isoformat(timespec='seconds')
    result={}
    for _,row in frame.iterrows():
        symbol=row['name']
        if symbol in symbols and symbol not in result:
            item=row.to_dict();item['retrieved']=retrieved;result[symbol]=item
    return result


def fetch_session_quotes(symbols):
    return bounded_call(_session_quotes,tuple(symbols),timeout=12)


def _discover_symbols():
    from tradingview_screener import Query,col
    _,frame=(Query().set_markets('america').select('name')
        .where(col('type')=='stock',col('is_primary')==True,
            col('close')>col('SMA50'),col('close')>col('SMA200'))
        .order_by('average_volume_90d_calc',ascending=False).limit(1500).get_scanner_data(timeout=8))
    return list(dict.fromkeys(frame['name'].dropna().astype(str)))


def discover_symbols():
    return bounded_call(_discover_symbols,timeout=12)


# ---- VCP / PEG scan tiers: liquid US stocks + ETFs + commodities ----
SETUP_MIN_PRICE=10.0
SETUP_MIN_DOLLAR_VOLUME=20_000_000
SETUP_SMA50_TOLERANCE=0.97
# Tier name -> how many of the most liquid US stocks it takes (ETFs and commodities are added to each).
SETUP_TIERS={'Core · 500 liquid + ETFs + commodities':500,
    'Medium · 1,500 liquid + ETFs + commodities':1500,
    'Full · US market + ETFs + commodities':4000}

# Front-month futures on Yahoo, plus SHFE hot-rolled coil from Sina (Yahoo does not carry SHFE).
COMMODITIES={'GC=F':'Gold','SI=F':'Silver','HG=F':'Copper','PL=F':'Platinum','PA=F':'Palladium',
    'CL=F':'WTI crude oil','BZ=F':'Brent crude oil','NG=F':'Natural gas','RB=F':'Gasoline','HO=F':'Heating oil',
    'ZC=F':'Corn','ZW=F':'Wheat','ZS=F':'Soybeans','KC=F':'Coffee','SB=F':'Sugar','CC=F':'Cocoa','CT=F':'Cotton',
    'LE=F':'Live cattle','HC1!':'SHFE hot-rolled coil · main contract'}
SINA_FUTURES={'HC1!':'HC0'}  # app symbol -> Sina main-contract code


def parse_sina_daily(text):
    """Daily OHLCV frame from Sina's futures JSONP: var _X=([{"d":..,"o":..,"h":..,"l":..,"c":..,"v":..}]);"""
    import json
    import pandas as pd
    rows=json.loads(text[text.index('['):text.rindex(']')+1])
    frame=pd.DataFrame(rows)
    if frame.empty or any(k not in frame for k in ('d','o','h','l','c','v')):return pd.DataFrame()
    out=pd.DataFrame({'Open':frame['o'],'High':frame['h'],'Low':frame['l'],'Close':frame['c'],'Volume':frame['v']})
    out=out.apply(pd.to_numeric,errors='coerce')
    out.index=pd.DatetimeIndex(pd.to_datetime(frame['d']))
    return out[~out.index.duplicated(keep='last')].sort_index().tail(300)


def complete_asia_daily(frame,now):
    """Drop a still-forming China session. The bar dated D (night session + day session)
    ends at 15:00 Shanghai, about 02:00-03:00 New York time on D."""
    import pandas as pd
    if frame is None or len(frame)==0:return frame
    here=pd.Timestamp(now).tz_convert('America/New_York')
    last=frame.index[-1].date()
    if last>here.date() or (last==here.date() and here.hour<3):return frame.iloc[:-1]
    return frame


def _sina_daily(code):
    import requests
    url=f'https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_{code}=/InnerFuturesNewService.getDailyKLine?symbol={code}'
    response=requests.get(url,timeout=8,headers={'Referer':'https://finance.sina.com.cn/','User-Agent':'Mozilla/5.0'})
    response.raise_for_status()
    return parse_sina_daily(response.text)


def filter_setup_universe(frame,limit,min_price=SETUP_MIN_PRICE,min_dollar_volume=SETUP_MIN_DOLLAR_VOLUME,
        sma50_tolerance=SETUP_SMA50_TOLERANCE):
    """The `limit` most liquid stocks behind the price / dollar-volume floor, most liquid first.

    Dollar volume = last price x 90-day average share volume. There is no 200 SMA
    rule, so a power earnings gap out of a downtrend is kept. Within the chosen
    names, those more than 3% under their 50-day average (or with fewer than 50
    sessions) are skipped before any history is downloaded: both setups need the
    completed close above the 50-day average, and the 3% allowance covers an
    intraday dip while the last completed close still qualifies.
    """
    import pandas as pd
    if frame is None or len(frame)==0:return []
    f=frame.copy()
    for column in ('close','SMA50','average_volume_90d_calc'):
        f[column]=pd.to_numeric(f[column],errors='coerce')
    f=f.dropna(subset=['name','close','average_volume_90d_calc'])
    f['name']=f['name'].astype(str).str.strip().str.upper()
    f['dollar']=f['close']*f['average_volume_90d_calc']
    f=f[(f['close']>min_price)&(f['dollar']>=min_dollar_volume)]
    f=f.sort_values('dollar',ascending=False,kind='stable').drop_duplicates('name').head(int(limit))
    f=f[f['close']>=sma50_tolerance*f['SMA50']]
    return list(f['name'])


def _discover_setup_symbols(limit):
    from tradingview_screener import Query,col
    _,frame=(Query().set_markets('america').select('name','close','SMA50','average_volume_90d_calc')
        .where(col('type')=='stock',col('is_primary')==True,col('close')>SETUP_MIN_PRICE)
        .order_by('average_volume_90d_calc',ascending=False).limit(8000).get_scanner_data(timeout=15))
    return filter_setup_universe(frame,limit)


def discover_setup_symbols(limit):
    return bounded_call(_discover_setup_symbols,limit,timeout=20)
