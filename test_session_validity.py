from datetime import datetime
import pandas as pd
from crescent_engine import ET
from session_validity import regular_status,session_clock
from intraday_context import session_rows


def at(day,hour,minute=0):return datetime.fromisoformat(f'{day}T{hour:02}:{minute:02}').replace(tzinfo=ET)


def test_yesterdays_bars_are_stale_after_close():
    assert regular_status(at('2026-11-04',16),at('2026-11-05',18))=='STALE'


def test_same_day_full_close_and_missing_close_are_distinguished():
    assert regular_status(at('2026-11-05',16),at('2026-11-05',18))=='REGULAR SESSION CLOSE'
    assert regular_status(at('2026-11-05',10),at('2026-11-05',18))=='STALE'
    assert regular_status(at('2026-11-05',15,50),at('2026-11-05',16,10))=='CLOSE PENDING'
    assert regular_status(at('2026-11-05',15,59),at('2026-11-05',18),close_tolerance_seconds=60)=='REGULAR SESSION SNAPSHOT'


def test_weekend_holiday_premarket_and_early_close():
    assert session_clock(at('2026-11-07',12))['date'].isoformat()=='2026-11-06'
    assert session_clock(at('2026-11-26',12))['date'].isoformat()=='2026-11-25'
    assert session_clock(at('2026-11-06',8))['date'].isoformat()=='2026-11-05'
    assert regular_status(at('2026-11-27',13),at('2026-11-27',15))=='REGULAR SESSION CLOSE'
    assert not session_clock(at('2026-11-27',15))['open']


def test_terminal_no_longer_calls_old_afterhours_bars_closed():
    index=pd.date_range('2026-11-04 09:30',periods=78,freq='5min',tz=ET)
    f=pd.DataFrame({'Open':100,'High':100,'Low':100,'Close':100,'Volume':100},index=index)
    result=session_rows({'SPY':f},{},at('2026-11-05',18))
    assert result['status']=='STALE'
    assert result['session']=='2026-11-04'
    assert result['rows'].iloc[0]['Status']=='STALE'


def test_terminal_accepts_actual_completed_session_after_hours():
    index=pd.date_range('2026-11-05 09:30',periods=78,freq='5min',tz=ET)
    f=pd.DataFrame({'Open':100,'High':100,'Low':100,'Close':100,'Volume':100},index=index)
    assert session_rows({'SPY':f},{},at('2026-11-05',18))['status']=='REGULAR SESSION CLOSE'


def test_daily_completion_uses_actual_early_close_plus_buffer():
    from crescent_engine import complete_daily
    f=pd.DataFrame({'Open':[100,101],'High':[100,101],'Low':[100,101],
        'Close':[100,101],'Volume':[100,100]},index=pd.DatetimeIndex(['2026-11-25','2026-11-27'],tz=ET))
    assert len(complete_daily(f,at('2026-11-27',13,10)))==1
    assert len(complete_daily(f,at('2026-11-27',13,16)))==2
