"""Session freshness, unchanged liquidity baselines and colored output."""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from dataclasses import replace
import pandas as pd
from liquid_uptrend import screen_intraday,LiquidFilters
from liquid_table import leaders_table
from test_liquid_uptrend import history

NOW=datetime(2026,11,4,12,0,tzinfo=ZoneInfo('America/New_York'))


def quote(**changes):
    item={'close':220.,'high':230.,'low':210.,'SMA50':190.,'SMA200':160.,
        'change':5.,'change_from_open':2.,'VWAP':215.,'volume':100_000,
        'relative_volume_10d_calc':1.5,'time':NOW.replace(hour=9,minute=30).timestamp(),
        'last_bar_update_time':(NOW-timedelta(minutes=15)).timestamp(),
        'update_mode':'delayed_streaming_900','retrieved':NOW.isoformat()}
    item.update(changes);return item


def test_intraday_uses_session_prices_with_completed_liquidity():
    h=history()
    rows,missing=screen_intraday({'TEST':h},{'TEST':quote()},NOW)
    assert not missing and len(rows)==1
    row=rows.iloc[0]
    assert row.Last==220 and row['Avg volume 20D']==2_000_000
    assert row['Session volume']==100_000  # Partial-session volume doesn't replace the 20D baseline.
    assert row['ADR 1D %']==(230-210)/220*100
    assert row['ADR 20D %']==((h.High.tail(19).sum()+230)-(h.Low.tail(19).sum()+210))/20/220*100
    assert row.Feed=='15 min delayed'
    assert row['Baseline through']=='2026-11-03'


def test_current_price_can_disqualify_yesterdays_match():
    rows,missing=screen_intraday({'TEST':history()},{'TEST':quote(close=150)},NOW)
    assert rows.empty and not missing


def test_stale_missing_previous_and_future_quotes_are_held_out():
    for q in ({},quote(last_bar_update_time=(NOW-timedelta(minutes=31)).timestamp()),
        quote(time=(NOW-timedelta(days=1)).timestamp()),
        quote(last_bar_update_time=(NOW+timedelta(minutes=10)).timestamp())):
        rows,missing=screen_intraday({'TEST':history()},{'TEST':q},NOW)
        assert rows.empty and 'TEST' in missing


def test_intraday_preserves_strict_liquidity_threshold_and_invalid_volume():
    rows,_=screen_intraday({'TEST':history()},{'TEST':quote()},NOW,replace(LiquidFilters(),volume20=2_000_000))
    assert rows.empty
    h=history();h.iloc[-1,h.columns.get_loc('Volume')]=float('nan')
    rows,missing=screen_intraday({'TEST':h},{'TEST':quote()},NOW)
    assert rows.empty and 'volume' in missing['TEST']


def test_color_table_escapes_and_colors_both_directions():
    html=leaders_table(pd.DataFrame([{'Symbol':'<script>','Today %':2,'Vs VWAP %':-1,'RVOL':2}]))
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert '#55e1a5' in html and '#ff7b87' in html and '#d7acff' in html


def test_unknown_industry_from_quote_remains_excluded():
    from liquid_uptrend import apply_exclusions
    rows,_=screen_intraday({'TEST':history()},{'TEST':quote()},NOW)
    for industry in (None,float('nan')):
        included,excluded=apply_exclusions(rows,{'TEST':{'industry':industry}})
        assert included.empty and 'unverified' in excluded.iloc[0]['Exclusion']
