"""Validate regular-session data independently of research/trading rules."""
from functools import lru_cache
from datetime import timedelta
import pandas as pd
from zoneinfo import ZoneInfo

ET=ZoneInfo('America/New_York')


@lru_cache(maxsize=1)
def calendar():
    import exchange_calendars as xc
    return xc.get_calendar('XNYS')


def session_clock(now):
    now=pd.Timestamp(now).tz_convert(ET)
    cal=calendar()
    session=cal.date_to_session(str(now.date()),direction='previous')
    opened=cal.session_open(session).tz_convert(ET)
    closed=cal.session_close(session).tz_convert(ET)
    active=opened<=now<closed
    if now<opened:
        session=cal.previous_session(session)
        closed=cal.session_close(session).tz_convert(ET)
    return {'date':session.date(),'close':closed,'open':active,'now':now}


def regular_status(stamp,now,max_age_seconds=900,close_tolerance_seconds=0):
    clock=session_clock(now)
    stamp=pd.Timestamp(stamp)
    if stamp.tzinfo is None:return 'UNVERIFIED'
    stamp=stamp.tz_convert(ET)
    if stamp>clock['now']+timedelta(seconds=5):return 'STALE'
    if stamp.date()!=clock['date']:return 'STALE'
    if clock['open']:
        return 'CURRENT' if (clock['now']-stamp).total_seconds()<=max_age_seconds else 'STALE'
    if stamp>=clock['close']:return 'REGULAR SESSION CLOSE'
    if close_tolerance_seconds and stamp>=clock['close']-timedelta(seconds=close_tolerance_seconds):return 'REGULAR SESSION SNAPSHOT'
    if clock['now']<=clock['close']+timedelta(minutes=30) and stamp>=clock['close']-timedelta(minutes=30):
        return 'CLOSE PENDING'
    return 'STALE'
