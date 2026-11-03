"""Offline fixtures are isolated to tests; the application has no synthetic feed."""
from pathlib import Path
import streamlit as st
from streamlit.testing.v1 import AppTest
import crescent_feeds
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


def test_terminal_saves_candidate_and_opens_monitor(monkeypatch):
    st.cache_data.clear()
    frames,_=crescent_feeds.generate_demo()  # Deterministic offline test fixture only.
    monkeypatch.setattr(crescent_feeds,'yahoo_daily',lambda *a,**k:(frames,{}))
    source=Path('app.py').read_text(encoding='utf-8').replace('NOW=lambda:datetime.now(ET)',
        'NOW=lambda:datetime(2026,10,30,17,0,tzinfo=ET)')
    app=AppTest.from_string(source,default_timeout=60).run()
    assert not app.exception
    choices=[x for x in app.button if x.label=='＋ Watch setup' and not x.disabled]
    assert choices
    choices[0].click().run()
    assert not app.exception
    assert len(app.session_state['frozen']) == 1
    assert 'Focused setup review' in [x.value for x in app.subheader]
    assert not app.dataframe


def test_dark_table_escapes_provider_strings():
    html=table(pd.DataFrame([{'Symbol':'<script>alert(1)</script>'}]))
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
    assert 'terminal-table' in html
