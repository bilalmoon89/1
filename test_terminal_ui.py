"""Offline fixtures are isolated to tests; the application has no synthetic feed."""
from pathlib import Path
import streamlit as st
from streamlit.testing.v1 import AppTest
import crescent_feeds
import intraday_context
from terminal_view import table
import pandas as pd


def test_terminal_feed_failure_has_no_generated_fallback(monkeypatch):
    st.cache_data.clear()
    monkeypatch.setattr(crescent_feeds,'yahoo_daily',lambda *a,**k:({}, {'SPY':'Provider unavailable'}))
    app=AppTest.from_file('app.py',default_timeout=60).run()
    assert not app.exception
    assert not app.tabs
    assert not app.session_state['plans']
    assert app.session_state['market_snapshot']['loaded']==0
    assert any('No generated prices' in x.value for x in app.warning)
    assert 'generate_demo' not in Path('app.py').read_text(encoding='utf-8')


def test_terminal_saves_candidate_and_opens_monitor(monkeypatch,tmp_path):
    st.cache_data.clear()
    frames,_=crescent_feeds.generate_demo()  # Deterministic offline test fixture only.
    monkeypatch.setattr(crescent_feeds,'yahoo_daily',lambda *a,**k:(frames,{}))
    monkeypatch.setattr(intraday_context,'fetch_intraday',lambda *a,**k:({},{}))
    source=Path('app.py').read_text(encoding='utf-8').replace('NOW=lambda:datetime.now(ET)',
        'NOW=lambda:datetime(2026,10,30,17,0,tzinfo=ET)')
    test_app=tmp_path/'app.py'
    test_app.write_text(source,encoding='utf-8')
    app=AppTest.from_file(str(test_app),default_timeout=60).run()
    assert not app.exception
    choices=[x for x in app.button if x.label=='＋ Follow setup' and not x.disabled]
    assert len(choices)==6
    choices[0].click().run()
    assert not app.exception
    assert len(app.session_state['following']) == 1
    assert not app.session_state['frozen']
    next(x for x in app.button if x.label=='Move to focus').click().run()
    assert not app.exception
    assert len(app.session_state['frozen']) == 1
    assert 'Focused setup review' in [x.value for x in app.subheader]
    assert not app.dataframe


def test_dark_table_escapes_provider_strings():
    html=table(pd.DataFrame([{'Symbol':'<script>alert(1)</script>'}]))
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
    assert 'terminal-table' in html


def test_liquid_page_uses_standard_filters_and_real_feed_adapter(monkeypatch):
    from test_liquid_uptrend import history
    import liquid_uptrend, liquid_data, liquid_app
    st.cache_data.clear()
    monkeypatch.setattr(liquid_app,'universe',lambda scope:['AAPL'])
    calls=[]
    monkeypatch.setattr(liquid_data,'fetch_batch',lambda symbols:(calls.append(symbols) or {'AAPL':history()},{}))
    monkeypatch.setattr(liquid_uptrend,'fetch_industries',lambda *a,**k:{'AAPL':{'industry':'Consumer Electronics','key':'consumer-electronics'}})
    app=AppTest.from_file('app.py',default_timeout=60)
    app.query_params['view']='liquid'
    app.run()
    assert not app.exception
    assert len(app.number_input)==6
    assert next(x for x in app.checkbox if x.label.startswith('Exclude Pharmaceuticals')).value
    assert not calls
    next(x for x in app.radio if x.label=='Data view').set_value('Completed daily').run()
    next(x for x in app.button if x.label=='Run Liquid Uptrend').click().run()
    assert not app.exception
    assert calls==[('AAPL',)]
    assert any('AAPL' in x.value for x in app.markdown)


def test_liquid_failed_refresh_retains_last_good_results(monkeypatch):
    from test_liquid_uptrend import history
    import liquid_app, liquid_data
    st.cache_data.clear()
    monkeypatch.setattr(liquid_app,'universe',lambda scope:['AAPL'])
    monkeypatch.setattr(liquid_data,'fetch_batch',lambda symbols:({'AAPL':history()},{}))
    monkeypatch.setattr(liquid_data,'fetch_classification',lambda symbols:{'AAPL':{'industry':'Consumer Electronics'}})
    app=AppTest.from_file('app.py',default_timeout=30)
    app.query_params['view']='liquid'
    app.run()
    next(x for x in app.radio if x.label=='Data view').set_value('Completed daily').run()
    next(x for x in app.button if x.label=='Run Liquid Uptrend').click().run()
    stamp=app.session_state['liquid_updated']
    liquid_app.successful_daily_batch.clear()
    monkeypatch.setattr(liquid_data,'fetch_batch',lambda symbols:({}, {'AAPL':'Timeout'}))
    next(x for x in app.button if x.label=='Run Liquid Uptrend').click().run()
    assert not app.exception
    assert app.session_state['liquid_updated']==stamp
    assert 'AAPL' in app.session_state['liquid_history']
    assert any('retained' in x.value for x in app.error)

def test_liquid_intraday_default_and_custom_tickers(monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from test_liquid_uptrend import history
    from test_liquid_intraday import quote
    import liquid_app,liquid_data
    st.cache_data.clear()
    monkeypatch.setattr(liquid_app,'universe',lambda scope:['AAPL'])
    calls=[]
    def load(symbols):
        calls.append(symbols)
        return {s:history() for s in symbols},{}
    def quotes(symbols):
        now=datetime.now(ZoneInfo('America/New_York'))
        q=quote(time=now.replace(hour=9,minute=30).timestamp(),last_bar_update_time=now.timestamp(),industry='Technology')
        return {s:q for s in symbols}
    monkeypatch.setattr(liquid_data,'fetch_batch',load)
    monkeypatch.setattr(liquid_data,'fetch_session_quotes',quotes)
    app=AppTest.from_file('app.py',default_timeout=30)
    app.query_params['view']='liquid';app.run()
    assert app.selectbox[0].value=='Full 574'
    assert app.radio[0].value.startswith('Intraday')
    next(x for x in app.text_input if x.label=='Additional tickers').set_value('COHR, AAPL, LITE').run()
    next(x for x in app.button if x.label=='Run Liquid Uptrend').click().run()
    assert not app.exception
    assert calls==[('AAPL','COHR','LITE')]
    assert any('Today %' in x.value and '15 min delayed' in x.value and '#55e1a5' in x.value for x in app.markdown)
