"""Bounded, small-batch provider calls for the standalone liquid scan."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError

_pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='liquid-feed')
BATCH_SIZE=12


def bounded_call(function,*args,timeout=12):
    future=_pool.submit(function,*args)
    try:return future.result(timeout=timeout)
    except TimeoutError:
        future.cancel()
        raise TimeoutError(f'Provider exceeded {timeout}s request limit') from None


def _download(symbols):
    import yfinance as yf
    from crescent_feeds import _extract_symbol
    raw=yf.download(list(symbols),period='1y',interval='1d',auto_adjust=False,
        group_by='ticker',threads=4,progress=False,actions=False,timeout=8)
    frames={};failures={}
    for symbol in symbols:
        frame=_extract_symbol(raw,symbol,symbols)
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
