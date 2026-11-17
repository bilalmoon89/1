"""Independent, fast startup for the liquid scan route."""
import streamlit as st
from startup_imports import import_local


class PartialDaily(Exception):
    pass


@st.cache_data(ttl=1200,show_spinner=False)
def successful_daily_batch(symbols):
    frames,failures=import_local('liquid_data').fetch_batch(symbols)
    if failures:raise PartialDaily((frames,failures))
    return frames,failures


@st.cache_data(ttl=64800,show_spinner=False)
def _session_batch(symbols,session):
    """Kept until the next session closes. Completed daily candles change once per trading
    day, so a batch that already contains `session` does not need downloading again."""
    frames,failures=successful_daily_batch(symbols)
    latest=max((f.index[-1].date() for f in frames.values() if len(f)),default=None)
    if latest is None or str(latest)<session:raise PartialDaily((frames,failures))
    return frames,failures


def daily_batch(symbols):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from session_validity import completed_session
    try:return _session_batch(symbols,str(completed_session(datetime.now(ZoneInfo('America/New_York')))))
    except PartialDaily as exc:return exc.args[0]


@st.cache_data(ttl=3600,show_spinner=False)
def classifications(symbols):
    return import_local('liquid_data').fetch_classification(symbols)


@st.cache_data(ttl=60,show_spinner=False)
def session_quotes(symbols):
    return import_local('liquid_data').fetch_session_quotes(symbols)


def universe(scope):
    from crescent_feeds import symbols_from_file,seed_universe
    from crescent_engine import DEFAULT_WATCH
    stocks=symbols_from_file('stocks.csv')
    if scope=='TradingView US · top 1,500':return import_local('liquid_data').discover_symbols()
    if scope=='Full 574':return list(stocks)
    return seed_universe(stocks,DEFAULT_WATCH,per_sector=12 if scope=='Balanced 120' else 6,
        limit=120 if scope=='Balanced 120' else 60)


def main():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    st.set_page_config(page_title='Liquid Uptrend | Crescent Trade Terminal — BETA',
        page_icon='🌙',layout='wide',initial_sidebar_state='collapsed')
    view=import_local('terminal_view')
    st.markdown(view.CSS,unsafe_allow_html=True)
    st.markdown(view.header(active='liquid',source="TradingView + Yahoo"),unsafe_allow_html=True)
    import_local('liquid_view').render_liquid_page(daily_batch,classifications,universe,
        datetime.now(ZoneInfo('America/New_York')),session_quotes)
