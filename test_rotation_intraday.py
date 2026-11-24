from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import pytest
from rotation_intraday import intraday_metrics
from session_validity import market_is_open

ET=ZoneInfo('America/New_York')
NOW=datetime(2026,11,24,12,tzinfo=ET)


def fixtures():
    index=pd.bdate_range(end='2026-11-23',periods=100)
    f=pd.DataFrame({'Open':100.,'High':101.,'Low':99.,'Close':100.,'Volume':1e6},index=index)
    history={s:f.copy() for s in ['SPY','AAA','BBB']}
    stamp=pd.Timestamp(NOW).timestamp()
    quotes={s:{'close':p,'change':p-100,'time':stamp,'last_bar_update_time':stamp} for s,p in [('SPY',101),('AAA',103),('BBB',98)]}
    return history,quotes


def test_intraday_replaces_returns_and_recomputes_rs_without_mutating_history():
    history,quotes=fixtures()
    stocks,asof=intraday_metrics(history,quotes,'SPY',NOW)
    rows=stocks.set_index('Symbol')
    assert rows.loc['AAA','1D %']==3
    assert rows.loc['AAA','RS 1D pp']==2
    assert rows.loc['AAA','5D %']==pytest.approx(3)
    assert asof.date()==NOW.date()
    assert history['AAA'].Close.iloc[-1]==100


def test_missing_or_old_quotes_do_not_reuse_yesterday_returns():
    history,quotes=fixtures()
    quotes['AAA']['last_bar_update_time']-=3600
    stocks,_=intraday_metrics(history,quotes,'SPY',NOW)
    row=stocks.set_index('Symbol').loc['AAA']
    assert pd.isna(row['1D %']) and not row['Complete 10D']
    del quotes['SPY']
    stocks,asof=intraday_metrics(history,quotes,'SPY',NOW)
    assert stocks.empty and asof is None


def test_old_daily_baseline_and_unsynchronized_quotes_are_excluded():
    history,quotes=fixtures()
    history['AAA']=history['AAA'].iloc[:-1]
    quotes['BBB']['last_bar_update_time']-=600
    stocks,_=intraday_metrics(history,quotes,'SPY',NOW)
    assert stocks.set_index('Symbol').loc[['AAA','BBB'],'Complete 10D'].eq(False).all()


def test_close_and_early_close_stop_intraday():
    assert market_is_open(datetime(2026,11,24,15,59,tzinfo=ET))
    assert not market_is_open(datetime(2026,11,24,16,0,tzinfo=ET))
    assert market_is_open(datetime(2026,11,27,12,59,tzinfo=ET))
    assert not market_is_open(datetime(2026,11,27,13,0,tzinfo=ET))
    h,q=fixtures()
    assert intraday_metrics(h,q,'SPY',datetime(2026,11,24,16,0,tzinfo=ET))[0].empty
