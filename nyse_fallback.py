"""Rule-based NYSE calendar used only when `exchange_calendars` is unavailable.

Implements the small subset of the exchange_calendars API this app uses:
is_session, session_open, session_close, previous_session, date_to_session
and sessions_in_range. Holidays follow NYSE rules (weekend observance,
Good Friday, Juneteenth from 2022). Early closes at 13:00 ET: the day before
Independence Day, the day after Thanksgiving and Christmas Eve (weekdays only).
Ad-hoc closures (national days of mourning, weather) are NOT known here.
"""
from datetime import date, timedelta
from functools import lru_cache
import pandas as pd

ET = 'America/New_York'


def _easter(year):
    a = year % 19; b = year // 100; c = year % 100
    d = (19 * a + b - b // 4 - ((b - (b + 8) // 25 + 1) // 3) + 15) % 30
    e = (32 + 2 * (b % 4) + 2 * (c // 4) - d - (c % 4)) % 7
    f = d + e - 7 * ((a + 11 * d + 22 * e) // 451) + 114
    return date(year, f // 31, f % 31 + 1)


def _nth_weekday(year, month, weekday, n):
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(year, month, weekday):
    d = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d):
    if d.weekday() == 5: return d - timedelta(days=1)
    if d.weekday() == 6: return d + timedelta(days=1)
    return d


@lru_cache(maxsize=64)
def _holidays(year):
    days = {
        _nth_weekday(year, 1, 0, 3),            # MLK Day
        _nth_weekday(year, 2, 0, 3),            # Presidents' Day
        _easter(year) - timedelta(days=2),       # Good Friday
        _last_weekday(year, 5, 0),               # Memorial Day
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),             # Labor Day
        _nth_weekday(year, 11, 3, 4),            # Thanksgiving
        _observed(date(year, 12, 25)),
    }
    ny = date(year, 1, 1)
    if ny.weekday() != 5: days.add(_observed(ny))  # Saturday New Year is not observed on Friday
    if year >= 2022: days.add(_observed(date(year, 6, 19)))
    return days


@lru_cache(maxsize=64)
def _early_closes(year):
    out = set()
    jul3 = date(year, 7, 3)
    if jul3.weekday() < 5 and jul3 not in _holidays(year): out.add(jul3)
    out.add(_nth_weekday(year, 11, 3, 4) + timedelta(days=1))
    dec24 = date(year, 12, 24)
    if dec24.weekday() < 5 and dec24 not in _holidays(year): out.add(dec24)
    return out


def _day(value):
    return pd.Timestamp(value).tz_localize(None).normalize() if pd.Timestamp(value).tzinfo else pd.Timestamp(value).normalize()


class FallbackNYSE:
    name = 'XNYS (built-in fallback)'

    def is_session(self, value):
        d = _day(value).date()
        return d.weekday() < 5 and d not in _holidays(d.year)

    def session_open(self, value):
        d = _day(value)
        return pd.Timestamp(d.date().isoformat() + ' 09:30', tz=ET).tz_convert('UTC')

    def session_close(self, value):
        d = _day(value)
        hour = '13:00' if d.date() in _early_closes(d.year) else '16:00'
        return pd.Timestamp(d.date().isoformat() + ' ' + hour, tz=ET).tz_convert('UTC')

    def previous_session(self, value):
        d = _day(value) - pd.Timedelta(days=1)
        while not self.is_session(d): d -= pd.Timedelta(days=1)
        return d

    def date_to_session(self, value, direction='previous'):
        d = _day(value)
        step = pd.Timedelta(days=-1 if direction == 'previous' else 1)
        while not self.is_session(d): d += step
        return d

    def sessions_in_range(self, start, end):
        days = pd.date_range(_day(start), _day(end), freq='D')
        return pd.DatetimeIndex([d for d in days if self.is_session(d)])
