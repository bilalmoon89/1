import pandas as pd
import pytest
from ticker_check_view import day_change


def test_validated_quote_change_uses_its_own_previous_close():
    delta,pct,label=day_change({'valid':True,'price':105,'day_change_pct':5},
        {'frame':pd.DataFrame({'Close':[80,90]})})
    assert delta==pytest.approx(5)
    assert pct==5 and label=='Today'


def test_missing_quote_change_does_not_mix_in_daily_change():
    delta,pct,_=day_change({'valid':True,'price':105},{'frame':pd.DataFrame({'Close':[80,90]})})
    assert delta is None and pct is None


def test_unavailable_quote_uses_explicitly_labelled_completed_session():
    delta,pct,label=day_change({'valid':False,'price':999,'day_change_pct':50},
        {'frame':pd.DataFrame({'Close':[100,98]})})
    assert delta==-2 and pct==pytest.approx(-2) and label=='Last session'
