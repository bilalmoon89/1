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


PHARMA_KEYS=('biotechnology','drug-manufacturers','diagnostics-research')


def screen_history(history,filters=None):
    filters=filters or LiquidFilters()
    rows=[];unavailable={}
    for symbol,raw in history.items():
        f=normalise(raw)
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
            'ADR 1D %':round(adr1,2),'ADR 20D %':round(adr20,2),'As of':str(f.index[-1].date())})
    result=pd.DataFrame(rows)
    if not result.empty:result=result.sort_values('Avg $ volume 50D',ascending=False).reset_index(drop=True)
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
        industry=str(meta.get('industry',''));key=str(meta.get('key','')).lower()
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
