from dataclasses import replace
import pandas as pd
from liquid_uptrend import LiquidFilters,screen_history,apply_exclusions


def history():
    close=pd.Series([100+i*.5 for i in range(210)],index=pd.bdate_range(end='2026-11-03',periods=210))
    return pd.DataFrame({'Open':close,'High':close*1.05,'Low':close*.95,'Close':close,'Volume':2_000_000})


def test_standard_preset_requires_all_checks_and_computes_adr():
    f=history()
    result,_=screen_history({'TEST':f})
    assert len(result)==1
    assert result.iloc[0]['ADR 1D %']==10
    assert result.iloc[0]['ADR 20D %']==round((f.High.tail(20).mean()-f.Low.tail(20).mean())/f.Close.iloc[-1]*100,2)
    result,_=screen_history({'TEST':f},replace(LiquidFilters(),volume20=2_000_000))
    assert result.empty  # Strict greater-than, not greater-than-or-equal.


def test_default_pharma_exclusion_and_unknown_industries():
    matches,_=screen_history({'TEST':history()})
    included,excluded=apply_exclusions(matches,{'TEST':{'industry':'Biotechnology','key':'biotechnology'}})
    assert included.empty and len(excluded)==1
    included,excluded=apply_exclusions(matches,{})
    assert included.empty and 'unverified' in excluded.iloc[0]['Exclusion']
    included,_=apply_exclusions(matches,{},exclude_pharma=False)
    assert len(included)==1


def test_incomplete_volume_is_not_accepted_as_a_full_average():
    f=history();f.iloc[-1,f.columns.get_loc('Volume')]=float('nan')
    result,missing=screen_history({'TEST':f})
    assert result.empty and 'volume' in missing['TEST']


def test_tradingview_classification_fallback_preserves_pharma_exclusion(monkeypatch):
    import yfinance
    import tradingview_screener
    from liquid_uptrend import fetch_industries
    class MissingYahoo:
        def __init__(self,*args):pass
        def get_info(self):raise RuntimeError('Provider unavailable')
    class AvailableTradingView:
        def set_markets(self,*args):return self
        def select(self,*args):return self
        def where(self,*args):return self
        def limit(self,*args):return self
        def get_scanner_data(self,**kwargs):
            return 2,pd.DataFrame([{'name':'MPC','industry':'Oil Refining/Marketing'},{'name':'BIO','industry':'Biotechnology'}])
    monkeypatch.setattr(yfinance,'Ticker',MissingYahoo)
    monkeypatch.setattr(tradingview_screener,'Query',AvailableTradingView)
    industries=fetch_industries(('MPC','BIO'))
    matches,_=screen_history({'MPC':history(),'BIO':history()})
    included,excluded=apply_exclusions(matches,industries)
    assert included.Symbol.tolist()==['MPC']
    assert excluded.Symbol.tolist()==['BIO']
    assert included.iloc[0]['Classification source']=='TradingView'
