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
