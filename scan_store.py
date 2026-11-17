"""Server-side store for finished scans, shared by every browser session.

Streamlit keeps session_state per browser tab, and following a header link starts a
new session, so a finished scan used to be lost on every page change. Completed
daily candles only change once per trading day, so a finished scan stays valid
until the next session closes.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st

ET=ZoneInfo('America/New_York')
STALE_REUSE_MINUTES=30


@st.cache_resource(show_spinner=False)
def _store():
    return {}


def data_through(history):
    """Latest bar date across the loaded histories, as an ISO string ('' when empty)."""
    dates=[f.index[-1].date() for f in history.values() if f is not None and len(f)]
    return str(max(dates)) if dates else ''


def save(key,job,expected,now=None):
    now=now or datetime.now(ET)
    _store()[key]=dict(job,active=False,session=expected,through=data_through(job.get('history',{})),loaded_at=now.isoformat())


def reusable(saved,expected,now=None):
    """A saved scan is reused for the whole session it covers. If the provider had not
    published that session yet when it was saved, it is reused for 30 minutes only."""
    if not saved or saved.get('session')!=expected:return False
    if saved.get('through','')>=expected:return True
    now=now or datetime.now(ET)
    try:age=(now-datetime.fromisoformat(saved['loaded_at'])).total_seconds()/60
    except (KeyError,ValueError,TypeError):return False
    return 0<=age<=STALE_REUSE_MINUTES


def load(key,expected,now=None):
    saved=_store().get(key)
    return dict(saved) if reusable(saved,expected,now) else None
