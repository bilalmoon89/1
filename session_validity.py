"""Validate regular-session data independently of research/trading rules."""
from functools import lru_cache
from datetime import timedelta
import pandas as pd
from zoneinfo import ZoneInfo

ET=ZoneInfo('America/New_York')


@lru_cache(maxsize=1)
def calendar():
    """Official XNYS calendar; falls back to built-in NYSE rules if the package is missing."""
    try:
        import exchange_calendars as xc
        return xc.get_calendar('XNYS')
    except Exception:
        from nyse_fallback import FallbackNYSE
        return FallbackNYSE()


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


def completed_session(now):
    """Date of the latest NYSE session that has finished (close + 15 minutes)."""
    clock=session_clock(now)
    if clock['now']<clock['close']+pd.Timedelta(minutes=15):
        return calendar().previous_session(pd.Timestamp(clock['date'])).date()
    return clock['date']


def market_is_open(now):
    """True only inside today's actual NYSE regular session (holidays and half days aware)."""
    return bool(session_clock(now)['open'])


def today_session(now):
    """(open, close) for today's NYSE session in ET, or None on a non-trading day."""
    now=pd.Timestamp(now).tz_convert(ET)
    cal=calendar();day=pd.Timestamp(now.date())
    if not cal.is_session(day):return None
    return cal.session_open(day).tz_convert(ET),cal.session_close(day).tz_convert(ET)


def sessions_between(start_date,now):
    """Number of NYSE sessions strictly after start_date up to and including now's date."""
    now=pd.Timestamp(now).tz_convert(ET)
    cal=calendar()
    first=pd.Timestamp(start_date)+pd.Timedelta(days=1)
    last=pd.Timestamp(now.date())
    if first>last:return 0
    return len(cal.sessions_in_range(first,last))


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
