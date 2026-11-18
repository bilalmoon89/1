"""Market brief panel for the Terminal page: headlines, key data and earnings."""
from datetime import datetime, timezone
import streamlit as st
import market_brief as mb
from brief_cards import brief_html, brief_summary


# ------------------------------------------------------------------ cached data
@st.cache_data(ttl=600, show_spinner=False)
def _headlines():
    items, failed = mb.fetch_headlines()
    if not items:raise RuntimeError('No headline feed answered')
    return items, failed


@st.cache_data(ttl=3600, show_spinner=False)
def _calendar(hour_key):
    return mb.fetch_calendar()


@st.cache_data(ttl=7200, show_spinner=False)
def _earnings(bucket):
    return mb.fetch_earnings()


def render_market_brief(now):
    """Draw the brief. Each source fails on its own; a failure is retried on the next run, not cached."""
    notes = []
    try:
        items, failed = _headlines()
        stories = mb.rank_headlines(items, datetime.now(timezone.utc))
        if failed:notes.append('Some news feeds did not answer: ' + ', '.join(failed))
    except Exception:
        stories = []
    try:
        rows, source = _calendar(now.strftime('%Y-%m-%d %H'))
        events = mb.top_events(rows, now)
        if source != 'TradingView':notes.append(f'Economic calendar from {source}.')
    except Exception:
        events = []
    try:
        earnings = mb.top_earnings(_earnings(f"{now:%Y-%m-%d}-{now.hour // 2}"), now)  # refreshed every 2 hours
    except Exception:
        earnings = []
    notes.append('Headlines via Google News; calendar and earnings dates via TradingView. Dates can change; check before trading around them.')
    # Collapsed by default so the market strip stays at the top of the page.
    with st.expander(brief_summary(stories, events, earnings, now), expanded=False):
        st.markdown(brief_html(stories, events, earnings, now, ' '.join(notes)), unsafe_allow_html=True)
