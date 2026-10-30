"""Offline regression tests; they do not certify Yahoo or Streamlit deployment."""
from datetime import datetime, time
from zoneinfo import ZoneInfo
import io
import numpy as np
import pandas as pd
import pytest
from crescent_engine import (complete_daily,normalise,snapshot,regime,Plan,make_plans,
    rank_plans,ten_minute_bars,intraday_vwap,live_check)
from crescent_feeds import generate_demo,symbols_from_file,seed_universe,read_events,risk_events
from rotation_themes import THEMES

ET=ZoneInfo('America/New_York')
D=datetime(2026,10,30,17,tzinfo=ET)


def sample_plan():
    return Plan(id='test-p',symbol='TEST',sector='Healthcare',setup='TREND PULLBACK',
        horizon='SWING',direction='LONG',status='ARMED',trigger=100,stop=98,target=106,
        rr=3.0,score=71,reason='Test case',blocker='Await confirmation',asof='2026-10-28',
        source='TEST',created_at=D.isoformat(),max_entry=101.5,distance_atr=.3,
        sector_rotation='OUTPERFORMING')


def five_minute(tick='2026-10-29'):
    idx=pd.date_range(tick+' 09:30',periods=15,freq='5min',tz=ET)
    # From 98.8 to 100.9 across the RTH morning
    close=np.linspace(98.8,101.0,len(idx))
    open_=close-.06
    f=pd.DataFrame({'Open':open_,'High':close+.04,'Low':open_-.04,'Close':close,
                    'Volume':np.ones(len(idx))*1000},index=idx)
    return f


def test_original_research_universe_and_themes_preserved():
    a=symbols_from_file('stocks.csv')
    assert len(a)==574
    assert len(pd.read_csv('etfs.csv'))==96
    assert len(THEMES)==90
    assert 'LLY' in a and 'PG' in a and 'NVDA' in a


def test_sector_sampling_is_not_semis_only():
    sectors=symbols_from_file('stocks.csv')
    names=seed_universe(sectors,['STX','LLY','PG'],per_sector=6,limit=60)
    assert 'STX' in names and 'LLY' in names and 'PG' in names
    groups=set(sectors[x] for x in names)
    assert len(groups)>=6


def test_demo_rotation_detects_defensive_transfer():
    hist,_=generate_demo()
    result=regime(hist,D)
    assert result['asof']=='2026-10-29'
    assert result['rotation']=='DEFENSIVE LEADERSHIP'
    assert set(['XLK','XLV','XLP','XLU']).issubset(set(result['sectors'].Symbol))
    assert 'UNKNOWN' not in result['posture']


def test_no_fake_regime_on_incomplete_benchmark():
    h,_=generate_demo();h.pop('SPY')
    r=regime(h,D)
    assert r['posture']=='UNKNOWN' and r['coverage']==0


def test_same_session_freshness_excludes_partial_daily():
    h,_=generate_demo()
    spy=h['SPY'].copy()
    future=spy.iloc[-1:].copy()
    future.index=[pd.Timestamp('2026-10-30')]
    # During the 10/30 session the last (unfinished) row is excluded.
    current=pd.concat([spy,future])
    result=complete_daily(current,datetime(2026,10,30,10,2,tzinfo=ET))
    assert result.index[-1].date().isoformat()=='2026-10-29'
    after=complete_daily(current,datetime(2026,10,30,16,20,tzinfo=ET))
    assert after.index[-1].date().isoformat()=='2026-10-30'


def test_overnight_plans_never_ready_and_have_frozen_levels():
    h,sectors=generate_demo()
    spy=snapshot(h['SPY'])
    r=regime(h,D)
    sector_rs=r['sectors'].set_index('Symbol')['Vs SPY 21D pp']
    ll=make_plans('LLY',h['LLY'],spy,sectors['LLY'],sector_rs['XLV'],r['posture'],D,'SIMULATED')
    pg=make_plans('PG',h['PG'],spy,sectors['PG'],sector_rs['XLP'],r['posture'],D,'SIMULATED')
    assert len(ll)==1 and ll[0].status=='ARMED'
    assert len(pg)==1 and pg[0].status=='ARMED'
    assert ll[0].trigger>ll[0].stop and ll[0].target>ll[0].trigger
    assert ll[0].rr>=1.5
    assert all(p.status!='READY' for p in ll+pg)
    selected=rank_plans(ll+pg)
    assert len(selected)==2 and len(set(p.sector for p in selected))==2


def test_insufficient_history_yields_no_plan():
    h,_=generate_demo();spy=snapshot(h['SPY'])
    assert make_plans('LLY',h['LLY'].tail(15),spy,'Healthcare',2,'SELECTIVE',D)==[]


def test_no_invented_magnet_target():
    # Valid plan can be WATCH because no historical confirmed swing high lies above trigger.
    h,_=generate_demo();spy=snapshot(h['SPY'])
    p=make_plans('HCA',h['HCA'],spy,'Health Care',3,'SELECTIVE',D)
    assert all(x.rr is None or x.rr>0 for x in p)
    assert all(x.target is not None or x.status!='ARMED' for x in p)


def test_rth_resampling_drops_unfinished_ten_minute_bucket():
    f=five_minute()
    now=datetime(2026,10,29,10,43,tzinfo=ET)
    bars=ten_minute_bars(f,now)
    assert not bars.empty
    assert len(bars)==7  # through the completed 10:30 bucket; 10:40 bucket incomplete
    assert (bars.index.minute % 10 == 0).all()


def test_live_check_no_after_hours_or_early_open():
    plan=sample_plan();f=five_minute()
    x=live_check(plan,f,datetime(2026,10,29,8,50,tzinfo=ET))
    assert x['status']=='MARKET CLOSED'
    early=live_check(plan,f,datetime(2026,10,29,9,45,tzinfo=ET))
    assert early['status']=='WAIT' and 'Observe' in early['why']
    night=live_check(plan,f,datetime(2026,10,29,20,2,tzinfo=ET))
    assert night['status']=='MARKET CLOSED'


def test_live_check_ready_with_completed_rth_reclaim():
    p=sample_plan();f=five_minute()
    x=live_check(p,f,datetime(2026,10,29,10,43,tzinfo=ET))
    assert x['status']=='READY',x
    assert x['price']>x['vwap']
    assert x['remaining_rr']>=1.5


def test_live_check_extended_does_not_chase():
    p=sample_plan();p.max_entry=100.3
    result=live_check(p,five_minute(),datetime(2026,10,29,10,43,tzinfo=ET))
    assert result['status']=='EXTENDED'


def test_live_check_stale_cannot_ready():
    p=sample_plan()
    out=live_check(p,five_minute('2026-10-28'),datetime(2026,10,29,10,43,tzinfo=ET))
    assert out['status']=='STALE'


def test_event_block_and_manual_restriction():
    data=b'Date,Time_ET,Title,Impact,Tickers,Source,Confirmed\n2026-10-29,10:30,Test Release,HIGH,ALL,example.org,true\n'
    ev=read_events(data)
    assert risk_events(ev,datetime(2026,10,29,10,30,tzinfo=ET),'LLY')==['Test Release']
    result=live_check(sample_plan(),five_minute(),datetime(2026,10,29,10,43,tzinfo=ET),manual_event_block=True)
    assert result['status']=='BLOCKED'


def test_unconfirmed_news_does_not_block():
    data=b'Date,Time_ET,Title,Impact,Tickers,Source,Confirmed\n2026-10-29,10:30,Rumor,HIGH,ALL,unknown,false\n'
    events=read_events(data)
    assert risk_events(events,datetime(2026,10,29,10,30,tzinfo=ET),'LLY')==[]


def test_missing_wide_data_not_fabricated():
    f=normalise(pd.DataFrame())
    assert f.empty
    assert snapshot(pd.DataFrame()) is None


def test_session_vwap_resets_each_day():
    a=five_minute('2026-10-28');b=five_minute('2026-10-29')
    a.loc[:,'Close']=90;a.loc[:,'High']=90.5;a.loc[:,'Low']=89.5;a.loc[:,'Open']=90
    combo=pd.concat([a,b]);vf=intraday_vwap(combo)
    first2=vf[vf.index.date==datetime(2026,10,29).date()].VWAP.iloc[0]
    assert first2>95 and first2<101


def test_preopen_gap_is_never_ready():
    from crescent_engine import preopen_assessment
    plan=sample_plan();now=datetime(2026,10,29,8,31,tzinfo=ET)
    quote=datetime(2026,10,29,8,30,tzinfo=ET)
    out=preopen_assessment(plan,102,99,quote,now)
    assert out['status']=='EXTENDED' and 'READY' not in out['status']
    out=preopen_assessment(plan,99.5,99,quote,now)
    assert out['status']=='RECHECK PLAN'
    assert preopen_assessment(plan,99.5,99,quote,datetime(2026,10,29,11,tzinfo=ET))['status']=='NO PRE-OPEN SESSION'


def test_stale_overnight_plan_cannot_be_live_ready():
    p=sample_plan();p.asof='2026-10-26'
    out=live_check(p,five_minute(),datetime(2026,10,29,10,43,tzinfo=ET))
    assert out['status']=='STALE'


def test_unarmed_plan_cannot_be_promoted_on_live_candle():
    p=sample_plan();p.status='WATCH'
    out=live_check(p,five_minute(),datetime(2026,10,29,10,43,tzinfo=ET))
    assert out['status']=='BLOCKED'


def test_unknown_sector_data_cannot_make_armed_plan():
    h,_=generate_demo();spy=snapshot(h['SPY'])
    p=make_plans('LLY',h['LLY'],spy,'Healthcare',None,'SELECTIVE / MIXED',D)
    assert p and all(x.status=='WATCH' for x in p)


def test_live_sector_confirmation_is_required_when_requested():
    plan=sample_plan();f=five_minute();now=datetime(2026,10,29,10,43,tzinfo=ET)
    missing=live_check(plan,f,now,require_sector=True)
    assert missing['status']=='STALE'
    supporting=live_check(plan,f,now,sector_five=f,require_sector=True)
    assert supporting['status']=='READY'
    opposing=f.copy()
    opposing['Open']=107.0;opposing['High']=107.1;opposing['Low']=106.8;opposing['Close']=106.9
    assert live_check(plan,f,now,sector_five=opposing,require_sector=True)['status']=='CONFLICT'


def test_event_only_impacts_matching_symbols():
    data=b'Date,Time_ET,Title,Impact,Tickers,Source,Confirmed\n2026-10-29,10:30,Test Earnings,HIGH,LLY,example.org,true\n'
    ev=read_events(data)
    assert risk_events(ev,datetime(2026,10,29,10,30,tzinfo=ET),'LLY')
    assert not risk_events(ev,datetime(2026,10,29,10,30,tzinfo=ET),'PG')


def test_yahoo_batch_parser_handles_both_multiindex_orders():
    from crescent_feeds import _extract_symbol
    a,_=generate_demo()
    one=a['SPY'].tail(70);two=a['XLV'].tail(70)
    top=pd.concat({'SPY':one,'XLV':two},axis=1)
    assert len(_extract_symbol(top,'SPY',['SPY','XLV']))==70
    inverted=top.swaplevel(0,1,axis=1)
    assert len(_extract_symbol(inverted,'XLV',['SPY','XLV']))==70
    assert _extract_symbol(top,'MISSING',['SPY','XLV']).empty
