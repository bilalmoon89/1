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
    import yfinance as yf
    from crescent_feeds import _extract_symbol
    from sector_map import yahoo_symbol
    wanted={yahoo_symbol(s):s for s in symbols}
    request=list(wanted)
    raw=yf.download(request,period='1y',interval='1d',auto_adjust=False,
        group_by='ticker',threads=4,progress=False,actions=False,timeout=8)
    frames={};failures={}
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
