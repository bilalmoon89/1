"""Independent, fast startup for the liquid scan route."""
import streamlit as st
from startup_imports import import_local


def daily_batch(symbols):
    return import_local('liquid_data').fetch_batch(symbols)


@st.cache_data(ttl=3600,show_spinner=False)
def classifications(symbols):
    return import_local('liquid_data').fetch_classification(symbols)


def universe(scope):
    from crescent_feeds import symbols_from_file,seed_universe
    from crescent_engine import DEFAULT_WATCH
    stocks=symbols_from_file('stocks.csv')
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
    st.markdown(view.header(),unsafe_allow_html=True)
    import_local('liquid_view').render_liquid_page(daily_batch,classifications,universe,
        datetime.now(ZoneInfo('America/New_York')))
