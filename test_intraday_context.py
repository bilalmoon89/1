from datetime import datetime
import pandas as pd
import pytest
from crescent_engine import ET
from intraday_context import session_rows


def bars(values):
    index=pd.DatetimeIndex(['2026-11-03 09:25','2026-11-03 09:30','2026-11-03 09:35','2026-11-03 09:40'],tz=ET)
    return pd.DataFrame({'Open':values,'High':values,'Low':values,'Close':values,'Volume':[100]*4},index=index)


def histories():
    daily=pd.DataFrame({'Open':[100],'High':[100],'Low':[100],'Close':[100],'Volume':[100]},index=pd.DatetimeIndex(['2026-11-02'],tz=ET))
    return {'SPY':daily,'XLK':daily}


def test_intraday_uses_completed_rth_bars_and_previous_close():
    result=session_rows({'SPY':bars([500,100,102,1000]),'XLK':bars([900,100,104,2000])},histories(),datetime(2026,11,3,9,42,tzinfo=ET))
    row=result['rows'].set_index('Symbol').loc['XLK']
    assert row['Last']==104
    assert row['Today %']==pytest.approx(4)
    assert row['Vs SPY pp']==pytest.approx(2)
    assert row['VWAP']==pytest.approx(102)
    assert row['From open %']==pytest.approx(4)
    assert result['status']=='CURRENT'


def test_old_session_bars_are_labelled_stale():
    result=session_rows({'SPY':bars([100]*4)},histories(),datetime(2026,11,3,11,0,tzinfo=ET))
    assert result['status']=='STALE'


def test_missing_intraday_has_no_daily_substitution():
    result=session_rows({},histories(),datetime(2026,11,3,10,0,tzinfo=ET))
    assert result['status']=='UNAVAILABLE'
    assert result['rows'].empty


def test_missing_previous_close_does_not_invent_today_return():
    result=session_rows({'SPY':bars([100]*4),'XLK':bars([100]*4)},{},datetime(2026,11,3,9,42,tzinfo=ET))
    assert result['rows']['Today %'].isna().all()
    assert result['rows']['Vs SPY pp'].isna().all()
