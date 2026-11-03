from crescent_feeds import generate_demo
from theme_rotation import analyze_rotation, theme_symbols


def test_theme_symbols_never_expand_the_loaded_universe():
    loaded={'NVDA','AMD','SPY','UNKNOWN'}
    assert set(theme_symbols(loaded)).issubset(loaded)


def test_partial_basket_is_labelled_and_has_no_invented_session_return():
    frames,_=generate_demo()
    members=[s for s in frames if s!='SPY'][:2]
    assert len(members)==2
    themes=[{'name':'Test basket','group':'Test','symbols':members+['MISSING1','MISSING2']}]
    result=analyze_rotation(frames,{},themes)
    assert len(result)==1
    row=result.iloc[0]
    assert row['Coverage']=='2/4'
    assert row['Basket']=='PARTIAL BASKET'
    assert row['Session coverage']=='UNAVAILABLE'
    assert row['Today %'] is None
    assert row['Lifecycle'].startswith('PARTIAL /')
