"""Standalone VCP / Power Earnings Gap scanner page (?view=setups)."""
import streamlit as st
from startup_imports import import_local


@st.cache_data(ttl=86400,show_spinner=False)
def _earnings_dates(symbol):
    """Past/upcoming earnings dates from Yahoo (best effort). Raises on failure so it is not cached."""
    import yfinance as yf
    from sector_map import yahoo_symbol
    from liquid_data import bounded_call
    frame=bounded_call(lambda:yf.Ticker(yahoo_symbol(symbol)).get_earnings_dates(limit=12),timeout=10)
    if frame is None or len(frame)==0:raise ValueError('No earnings dates returned')
    return [d.date().isoformat() for d in frame.index]


def earnings_dates(symbol):
    try:return _earnings_dates(symbol)
    except Exception:return None


def main():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    st.set_page_config(page_title='VCP & PEG Setups | Crescent Trade Terminal — BETA',
        page_icon='🌙',layout='wide',initial_sidebar_state='collapsed')
    view=import_local('terminal_view')
    st.markdown(view.CSS,unsafe_allow_html=True)
    st.markdown(view.header(source='Yahoo Finance · completed daily candles'),unsafe_allow_html=True)
    liquid=import_local('liquid_app')
    import_local('setups_view').render_setups_page(liquid.daily_batch,liquid.universe,earnings_dates,
        datetime.now(ZoneInfo('America/New_York')))
