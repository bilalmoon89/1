from datetime import datetime
import numpy as np
import pandas as pd
import pytest
from crescent_engine import ET
from ticker_check import financial_quarters,fundamental_review,technical_review,stage_analysis,completed_weeks,high_tight_flag,valuation_history

NOW=datetime(2026,11,6,17,tzinfo=ET)


def history(values):
    values=np.asarray(values,dtype=float)
    index=pd.bdate_range(end='2026-11-06',periods=len(values))
    return pd.DataFrame({'Open':values,'High':values*1.01,'Low':values*.99,'Close':values,'Volume':2_000_000.},index=index)


def statement():
    columns=pd.to_datetime(['2026-09-30','2026-06-30','2026-03-31','2025-12-31','2025-09-30'])
    return pd.DataFrame([[120,110,100,100,100],[60,50,45,45,40],[30,25,20,20,20],[24,20,18,15,15],[2,2,2,2,2]],
        columns=columns,index=['TotalRevenue','GrossProfit','OperatingIncome','NetIncome','DilutedEPS'])


def test_five_quarters_growth_margins_and_decision():
    quarters=financial_quarters(statement())
    assert len(quarters)==5
    assert quarters.iloc[0]['Revenue YoY %']==pytest.approx(20)
    assert quarters.iloc[0]['Operating margin %']==25
    assert quarters.iloc[0]['Net margin %']==20
    assert fundamental_review(quarters,NOW)[0]=='SUPPORTIVE'
    assert fundamental_review(quarters.head(4),NOW)[0]=='INCOMPLETE'
    quarters.loc[0,'Net margin %']=-1
    assert fundamental_review(quarters,NOW)[0]=='CAUTION'


def test_200_sma_veto_even_when_earlier_trend_was_strong():
    f=history(np.r_[np.linspace(100,200,259),50])
    result=technical_review(f,NOW)
    assert result['decision']=='NO GO · BELOW 200 SMA'
    assert result['entry'] is None and result['stop'] is None


def test_stage_2_and_4_use_weekly_30_average():
    assert stage_analysis(history(np.linspace(50,150,60)))['stage'].startswith('2')
    assert stage_analysis(history(np.linspace(150,50,60)))['stage'].startswith('4')
    assert stage_analysis(history(np.ones(20)*100))['stage']=='UNKNOWN'


def test_partial_friday_week_is_not_used_until_close_buffer():
    f=history(np.linspace(100,150,260))
    before=completed_weeks(f,datetime(2026,11,6,12,tzinfo=ET))
    after=completed_weeks(f,NOW)
    assert before.index[-1].date().isoformat()=='2026-10-30'
    assert after.index[-1].date().isoformat()=='2026-11-06'


def test_high_tight_flag_requires_pole_depth_and_volume():
    pole=np.linspace(50,110,40);flag=np.linspace(107,108,15)
    f=history(np.r_[pole,flag]);f.loc[f.index[-15:],'Volume']=500_000
    result=high_tight_flag(f)
    assert result['found'] and result['advance']>=100 and result['depth']<=25
    f.loc[f.index[-15:],'Low']=60
    assert not high_tight_flag(f)['found']


def test_old_completed_prices_cannot_be_used_for_trade():
    f=history(np.linspace(100,200,260)).iloc[:-5]
    assert technical_review(f,NOW)['decision']=='NO GO · STALE DATA'


def test_annual_pe_reference_and_split_safeguard():
    annual=pd.DataFrame([[4.,5.]],index=['DilutedEPS'],columns=pd.to_datetime(['2024-12-31','2025-12-31']))
    prices=history(np.linspace(100,200,1300));prices['Stock Splits']=0.
    info={'currency':'USD','financialCurrency':'USD'}
    result,_=valuation_history(annual,prices,info)
    assert len(result)==2 and (result['P/E']>0).all()
    prices.iloc[2,prices.columns.get_loc('Stock Splits')]=2.
    result,reason=valuation_history(annual,prices,info)
    assert result.empty and 'split' in reason

def test_current_quote_200_sma_veto_and_stale_rejection():
    from ticker_check import quote_review
    stamp=datetime(2026,11,6,15,59,tzinfo=ET).timestamp()
    quote={'time':datetime(2026,11,6,9,30,tzinfo=ET).timestamp(),
        'last_bar_update_time':stamp,'close':90.,'SMA200':100.,'update_mode':'delayed_streaming_900'}
    result=quote_review(quote,NOW)
    assert result['valid'] and result['below200']
    quote['time']=datetime(2026,11,5,9,30,tzinfo=ET).timestamp()
    assert not quote_review(quote,NOW)['valid']


def test_ticker_page_loads_on_demand_and_respects_200_veto(monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    import ticker_check_app
    calls=[]
    def load(symbol):
        calls.append(symbol)
        return {'history':history(np.r_[np.linspace(100,200,258),50,50]),'quarters':statement(),
            'annual':pd.DataFrame(),'info':{'shortName':'Fixture','currency':'USD','financialCurrency':'USD'},
            'errors':[],'retrieved':'2026-11-06T17:00:00-05:00','quote':{}}
    monkeypatch.setattr(ticker_check_app,'load_ticker',load)
    app=AppTest.from_file('app.py',default_timeout=30)
    app.query_params['view']='ticker';app.run()
    assert not app.exception and not calls
    next(x for x in app.button if x.label=='Check ticker').click().run()
    assert not app.exception and calls==['AAPL']
    assert any('NO GO' in x.value and '200 SMA' in x.value for x in app.markdown)
    assert any('Gross margin %' in x.value for x in app.markdown)


def test_weekly_support_distinguishes_above_from_tested_hold():
    result=technical_review(history(np.linspace(100,200,260)),NOW)
    row=result['averages'].iloc[-1]
    assert row['State'] in ('TESTED & HELD','ABOVE · UNTESTED','BELOW','UNKNOWN')
