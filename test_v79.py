"""Tests for the 7.9.0 Ticker Check and Liquid Uptrend analysis additions."""
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from test_setup_scanner import vcp_path, tight_tail, frame_from_path
from ticker_check import (technical_review, market_context, setup_status, apply_setup_plan, checklist,
    financial_quarters)

ET = ZoneInfo('America/New_York')
NOW = datetime(2026, 11, 13, 18, 0, tzinfo=ET)


def vcp_frame():
    path, _ = vcp_path((25, 12, 5))
    f = tight_tail(frame_from_path(path))
    f.index = pd.bdate_range(end='2026-11-13', periods=len(f))
    return f


def test_ticker_uses_scanner_setup_for_plan_and_checklist():
    f = vcp_frame()
    spy = frame_from_path(np.linspace(400, 470, len(f))); spy.index = f.index
    tech = technical_review(f, NOW)
    assert tech['decision'] == 'WAIT · NO DEFINED SETUP'
    assert 'Daily EMA 8' in set(tech['averages'].Average)
    context = market_context(tech['frame'], spy)
    assert context['vs200'] > 0 and -25 < context['off_high'] <= 0 and context['rs63'] is not None
    setups = setup_status(tech['frame'], spy)
    assert setups['VCP']['found'] and not setups['PEG']['found'] and setups['PEG']['reason']
    assert apply_setup_plan(tech, setups) == 'VCP pivot'
    assert tech['entry'] > tech['stop'] and tech['decision'] != 'WAIT · NO DEFINED SETUP'
    checks = {label: state for label, state, _ in checklist(tech, 'SUPPORTIVE', setups, context, 3)}
    assert checks['Above 200 SMA'] == 'pass' and checks['VCP'] == 'pass' and checks['PEG'] == 'na'
    assert checks['Earnings in 3d'] == 'warn'


def test_setup_plan_never_overrides_a_no_go():
    f = vcp_frame()
    tech = technical_review(f, NOW)
    tech['decision'] = 'NO GO · BELOW 200 SMA'
    assert apply_setup_plan(tech, setup_status(tech['frame'])) == '' and tech['entry'] is None


def test_eps_growth_needs_a_positive_year_earlier_base():
    dates = pd.to_datetime(['2026-09-30', '2026-06-30', '2026-03-31', '2025-12-31', '2025-09-30'])
    statement = pd.DataFrame({d: {'TotalRevenue': 100.0, 'DilutedEPS': eps}
                              for d, eps in zip(dates, (3.0, 2.0, 2.0, 2.0, 2.0))})
    assert financial_quarters(statement).iloc[0]['EPS YoY %'] == 50
    statement.loc['DilutedEPS', dates[-1]] = -1.0
    assert financial_quarters(statement).iloc[0]['EPS YoY %'] is None


def test_liquid_rank_distance_from_high_and_tight_label():
    from liquid_uptrend import screen_history, LiquidFilters
    from liquid_table import leaders_frame, leaders_summary
    history = {f'S{i:02d}': frame_from_path(np.linspace(40, 40 * (1.3 + i * 0.04), 260), vol=4_000_000, spread=0.05)
               for i in range(24)}
    path, _ = vcp_path((25, 12, 5))
    history['VCPX'] = tight_tail(frame_from_path(path, vol=5_000_000), vol=1_500_000)
    result, _ = screen_history(history, LiquidFilters(adr1=0, adr20=0))
    assert result['RS rank'].iloc[0] == result['RS rank'].max() and result['RS rank'].between(1, 99).all()
    assert (result['Off 52W high'] <= 0).all()
    assert result.set_index('Symbol').loc['VCPX', 'Setup'] == 'TIGHT · 8 EMA'
    result['Industry'] = 'Semiconductors'
    assert leaders_frame(result).columns[:3].tolist() == ['Symbol', 'RS rank', 'Setup']
    assert 'Leading groups' in leaders_summary(result) and 'Semiconductors' in leaders_summary(result)
    # Too few histories for a meaningful percentile: no rank, sorted by liquidity as before.
    small, _ = screen_history({k: history[k] for k in list(history)[:3]}, LiquidFilters(adr1=0, adr20=0))
    assert small['RS rank'].isna().all() and 'RS rank' not in leaders_frame(small)


def _walk(drift, n=260, seed=0, last=0.0):
    rng = np.random.default_rng(seed)
    steps = np.full(n, drift) + rng.normal(0, 0.002, n); steps[-2:] += last
    c = 50 * np.exp(np.cumsum(steps))
    return pd.DataFrame({'Open': c, 'High': c * 1.01, 'Low': c * 0.99, 'Close': c, 'Volume': 3e6},
                        index=pd.bdate_range(end='2026-11-13', periods=n))


def test_rotation_states_cards_and_tables():
    from rotation_engine import stock_metrics, theme_metrics, leader_table
    from rotation_cards import theme_panels, theme_table, group_returns, strip, leaders_view
    themes = [{'name': 'Strong', 'group': 'G1', 'symbols': ['A1', 'A2', 'A3'], 'proxy': ''},
              {'name': 'Fading', 'group': 'G2', 'symbols': ['B1', 'B2', 'B3'], 'proxy': ''},
              {'name': 'Thin', 'group': 'G2', 'symbols': ['C1', 'C2', 'C3', 'C4'], 'proxy': ''}]
    history = {'SPY': _walk(0.0004)}
    history.update({s: _walk(0.004, seed=i + 1, last=0.01) for i, s in enumerate(['A1', 'A2', 'A3'])})
    history.update({s: _walk(0.005, seed=i + 9, last=-0.012) for i, s in enumerate(['B1', 'B2', 'B3'])})
    history['C1'] = _walk(0.001, seed=20)          # 1 of 4 members: below the coverage rule
    stocks, asof = stock_metrics(history, 'SPY')
    table = theme_metrics(stocks, themes).set_index('Theme')
    assert str(asof.date()) == '2026-11-13'
    assert table.loc['Strong', 'State'] in ('Leading', 'Leading + heating')
    assert table.loc['Fading', 'State'] == 'Cooling' and table.loc['Thin', 'State'] == 'Low coverage'
    html = theme_panels(table.reset_index(), stocks, {t['name']: t for t in themes}, 5)
    assert 'Strong' in html and 'Fading' in html and 'Thin' not in html and html.count('rot-card"') == 2
    ranking = theme_table(table.reset_index(), 5)
    assert ranking.Theme.iloc[0] == 'Strong' and ranking.Theme.iloc[-1] == 'Thin'
    assert dict(group_returns(table.reset_index(), 5))['G1'] > 0 and 'rot-pill' in strip('Groups', [('G1', 1.2)])
    assert leaders_view(leader_table(stocks, ['A1', 'A2', 'A3'])).columns[0] == 'Symbol'


def test_leadership_label_from_daily_history():
    from setup_scanner import leadership
    assert leadership(_walk(0.014)) == 'CORE LEADER'    # clears the 1M, 3M and 6M bars
    assert leadership(_walk(0.008)) == 'EMERGING'       # only the 6M bar
    assert leadership(_walk(0.0002)) == '' and leadership(_walk(0.014, n=100)) == ''
    path, _ = vcp_path((25, 12, 5))
    from setup_scanner import scan_vcp
    row, _ = scan_vcp('TEST', tight_tail(frame_from_path(path)))
    assert 'Leadership' in row and row['Day vol vs 20D %'] < 0
