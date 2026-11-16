import numpy as np
import pandas as pd
from setup_scanner import (zigzag, contractions, tight_area, scan_vcp, scan_peg, scan,
    VCPRules, PRESETS)


def frame_from_path(closes, vol=1_000_000, spread=0.012, dates=None):
    c = np.asarray(closes, float)
    o = np.r_[c[0], c[:-1]]
    hi = np.maximum(o, c) * (1 + spread / 2); lo = np.minimum(o, c) * (1 - spread / 2)
    v = np.full(len(c), float(vol)) if np.isscalar(vol) else np.asarray(vol, float)
    idx = dates if dates is not None else pd.bdate_range('2025-01-02', periods=len(c))
    return pd.DataFrame({'Open': o, 'High': hi, 'Low': lo, 'Close': c, 'Volume': v}, index=idx)


def leg(a, b, n):
    return list(np.linspace(a, b, n + 1)[1:])


def vcp_path(depths=(25, 12, 5)):
    path = list(np.linspace(40, 100, 230))           # long stage-2 advance
    top = 100.0
    for i, d in enumerate(depths):
        low = top * (1 - d / 100)
        path += leg(path[-1], low, 8)
        top = top * (0.995 - 0.002 * i)                # each rally stops just under the base high
        path += leg(low, top, 10)
    return path, top


def tight_tail(frame, days=5, drift=0.001, spread=0.003, vol=450_000):
    """Append small, low-volume candles that hug the last close."""
    last = float(frame.Close.iloc[-1])
    closes = last * (1 + drift * np.sin(np.arange(1, days + 1)))
    tail = frame_from_path(closes, vol=vol, spread=spread,
                           dates=pd.bdate_range(frame.index[-1] + pd.Timedelta(days=1), periods=days))
    tail.iloc[0, tail.columns.get_loc('Open')] = last
    return pd.concat([frame, tail])


def test_zigzag_finds_alternating_swings():
    path = [10, 11, 12, 11, 10, 11, 12.5, 12, 11.5]
    pts = zigzag(np.array(path) * 1.0, np.array(path) * 1.0, 5)
    kinds = [k for _, _, k in pts]
    assert kinds[:3] == ['H', 'L', 'H'] or kinds[:3] == ['L', 'H', 'L']
    assert all(a != b for a, b in zip(kinds, kinds[1:]))


def test_vcp_detected_with_shrinking_pullbacks_and_tight_8ema_area():
    path, _ = vcp_path((25, 12, 5))
    f = tight_tail(frame_from_path(path))
    depths, pivot, _ = contractions(f, VCPRules())
    assert len(depths) == 3 and depths[0] > depths[1] > depths[2]
    row, why = scan_vcp('TEST', f)
    assert row is not None, why
    assert row['Setup'] == 'VCP' and row['Contractions'] == 3
    assert row['Trigger'] > row['Close'] > row['Stop']
    assert row['EMA'] == '8 EMA'


def test_vcp_rejected_when_pullbacks_get_deeper():
    path, _ = vcp_path((8, 14, 22))
    row, why = scan_vcp('TEST', tight_tail(frame_from_path(path)))
    assert row is None


def test_vcp_rejected_without_tight_candles():
    path, _ = vcp_path((25, 12, 5))
    f = frame_from_path(path + leg(path[-1], path[-1] * 0.97, 2) + leg(path[-1] * 0.97, path[-1], 2), spread=0.04)
    row, why = scan_vcp('TEST', f)
    assert row is None


def test_vcp_rejected_after_breakout():
    path, top = vcp_path((25, 12, 5))
    path += leg(path[-1], 104, 4)
    row, why = scan_vcp('TEST', frame_from_path(path))
    assert row is None


def test_tight_area_presets_change_strictness():
    path, _ = vcp_path((25, 12, 5))
    f = tight_tail(frame_from_path(path), drift=0.006, spread=0.008, vol=700_000)
    loose, _ = tight_area(f, PRESETS['Loose'])
    strict, _ = tight_area(f, PRESETS['Very strict'])
    assert loose and not strict


def peg_frame(undercut=False, gap=8.0, vol_mult=4.0):
    path = list(np.linspace(50, 60, 150))
    f = frame_from_path(path)
    gap_open = path[-1] * (1 + gap / 100)
    day = pd.DataFrame({'Open': [gap_open], 'High': [gap_open * 1.04], 'Low': [gap_open * 0.99],
                        'Close': [gap_open * 1.035], 'Volume': [1_000_000 * vol_mult]},
                       index=[f.index[-1] + pd.offsets.BDay(1)])
    f = pd.concat([f, day])
    hold = float(day.Close.iloc[0])
    drift = list(np.linspace(hold, hold * 1.02, 10))
    if undercut: drift[4] = float(day.Low.iloc[0]) * 0.97
    nxt = frame_from_path(drift, vol=900_000, spread=0.01,
                          dates=pd.bdate_range(f.index[-1] + pd.Timedelta(days=1), periods=len(drift)))
    nxt.iloc[0, nxt.columns.get_loc('Open')] = hold
    return tight_tail(pd.concat([f, nxt]), days=5, vol=450_000)


def test_power_earnings_gap_detected_and_labelled():
    f = peg_frame()
    gap_day = f.index[150].date()
    row, why = scan_peg('GAP', f, earnings_dates=[gap_day])
    assert row is not None, why
    assert row['Setup'] == 'PEG' and row['Earnings'] == 'Confirmed'
    assert row['Gap %'] >= 5 and row['Gap volume x'] >= 2.5
    assert row['Gap-day low'] - 2 < row['Stop'] < row['Close']


def test_peg_unverified_without_earnings_dates_and_rejects_undercut():
    row, _ = scan_peg('GAP', peg_frame())
    assert row is not None and row['Earnings'] == 'Unverified'
    row, why = scan_peg('GAP', peg_frame(undercut=True))
    assert row is None and 'Undercut' in why


def test_peg_needs_heavy_volume():
    row, why = scan_peg('GAP', peg_frame(vol_mult=1.2))
    assert row is None


def test_scan_combines_setups_and_reports_reasons():
    path, _ = vcp_path((25, 12, 5))
    history = {'VCPX': tight_tail(frame_from_path(path)), 'GAPX': peg_frame(),
               'FLAT': frame_from_path(np.full(260, 50.0))}
    out, reasons = scan(history)
    assert set(out.Symbol) == {'VCPX', 'GAPX'}
    assert 'FLAT' in reasons
