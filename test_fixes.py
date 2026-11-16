"""Regression tests for the fixes in v7.8.0 (see CHANGES in README)."""
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from crescent_engine import live_check, plan_target, make_plans, snapshot
from sector_map import SECTOR_PROXY, ETF_SECTORS, proxy_for, yahoo_symbol
from test_crescent_v7 import sample_plan, five_minute

ET = ZoneInfo('America/New_York')


def test_every_stock_sector_has_a_proxy():
    stocks = pd.read_csv('stocks.csv')
    unmapped = stocks[~stocks.Sector.isin(SECTOR_PROXY)]
    # A handful may be resolved at scan time from TradingView; the bulk must map.
    assert len(unmapped) <= 5, unmapped.Symbol.tolist()
    assert 'US Large/Mid Cap' not in set(stocks.Sector)


def test_etf_candidates_have_proxies():
    assert all(proxy_for(s) for s in ETF_SECTORS.values())


def test_share_class_symbols_use_yahoo_form_only_for_stocks():
    assert yahoo_symbol('BRK.B') == 'BRK-B' and yahoo_symbol('BF.B') == 'BF-B'
    for s in ('DX-Y.NYB', '^VIX', 'GC=F', 'BTC-USD', 'AAPL'):
        assert yahoo_symbol(s) == s


def _daily(path, spread=0.01):
    c = np.asarray(path, float)
    return pd.DataFrame({'Open': c, 'High': c * (1 + spread), 'Low': c * (1 - spread), 'Close': c,
                         'Volume': 1e6}, index=pd.bdate_range('2026-01-02', periods=len(c)))


def test_projected_target_only_in_open_space():
    rising = _daily(np.linspace(50, 100, 120))
    target, kind = plan_target(rising, 101.5, 97.5, 1, 1.5)
    assert kind == 'PROJECTED' and abs(target - (101.5 + 2 * 4.0)) < 1e-9
    # Overhead supply close above the trigger: no projection.
    capped = _daily(list(np.linspace(50, 105, 60)) + list(np.linspace(105, 95, 60)))
    target, kind = plan_target(capped, 96, 93, 1, 1.5)
    assert kind in ('STRUCTURAL', 'UNKNOWN') and kind != 'PROJECTED'


def test_short_score_rewards_weaker_stocks():
    import crescent_engine as ce
    base = dict(price=50.0, asof='2026-06-01', atr=1.0, ema21=51.0, ema50=53.0, r5=-3.0, r21=-6.0,
                dvol=9e7, dryup=0.9, high20=56.0, low20=49.0, range_pos=0.3, last_high=50.5, last_low=49.6,
                prev3low=49.0, prev3high=51.2, trend_up=False, trend_down=True, distance21_atr=-1.0)
    spy = dict(asof='2026-06-01', r5=0.0, r21=1.0)
    frame = _daily(np.linspace(60, 50, 120))
    scores = []
    for r21 in (-2.0, -12.0):
        m = dict(base, r21=r21)
        orig = ce.snapshot
        ce.snapshot = lambda f, m=m: m
        try:
            plans = ce.make_plans('W', frame, spy, 'Energy', -4.0, 'MIXED',
                                  now=datetime(2026, 6, 2, 18, tzinfo=ET))
        finally:
            ce.snapshot = orig
        scores.append(next(p.score for p in plans if p.direction == 'SHORT'))
    assert scores[1] > scores[0], scores


def test_live_check_invalid_after_earlier_stop_breach():
    p = sample_plan(); f = five_minute()
    f.iloc[2, f.columns.get_loc('Low')] = 97.5  # traded through the 98 stop at 09:40, then recovered
    out = live_check(p, f, datetime(2026, 10, 29, 10, 43, tzinfo=ET))
    assert out['status'] == 'INVALID', out


def test_live_check_survives_market_holiday():
    # Plan from Wed 2026-11-25; Thanksgiving Thu 26th is closed, so Fri 27th is the next session.
    p = sample_plan(); p.asof = '2026-11-25'
    f = five_minute('2026-11-27')
    out = live_check(p, f, datetime(2026, 11, 27, 10, 43, tzinfo=ET))
    assert out['status'] != 'STALE', out


def test_live_check_closed_after_half_day_close():
    p = sample_plan(); p.asof = '2026-11-25'
    out = live_check(p, five_minute('2026-11-27'), datetime(2026, 11, 27, 13, 30, tzinfo=ET))
    assert out['status'] == 'MARKET CLOSED'


def test_bounded_call_is_not_starved_by_hung_calls():
    from liquid_data import bounded_call
    for _ in range(3):
        try: bounded_call(lambda: time.sleep(5), timeout=0.2)
        except TimeoutError: pass
    started = time.time()
    assert bounded_call(lambda: 'ok', timeout=2) == 'ok'
    assert time.time() - started < 1


def test_breakout_not_armed_when_already_extended_above_pivot():
    path = list(np.linspace(40, 100, 140)) + [99, 98.5, 98.8, 99.2, 99.0, 98.9, 99.1, 99.3, 99.0, 103.5]
    f = _daily(path, spread=0.004)
    spy = snapshot(_daily(np.linspace(100, 101, len(path))))
    plans = make_plans('X', f, spy, 'Industrials', 1.0, 'MIXED', now=datetime(2026, 12, 31, 18, tzinfo=ET))
    assert not any(p.setup == 'BASE BREAKOUT' for p in plans)
