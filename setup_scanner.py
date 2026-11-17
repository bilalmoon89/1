"""VCP and Power Earnings Gap (PEG) detection on completed daily bars.

Pure functions, no IO or Streamlit. Both setups share one idea: accumulation
shows up as a run of small candles whose closes sit tightly together on or
just above the 8 EMA while volume dries up.

VCP  (volatility contraction pattern)
    Stage-2 uptrend, then 2-4 pullbacks inside a base, each shallower than the
    one before, finishing with the tight 8 EMA area just under the pivot.
PEG  (power earnings gap)
    A large gap up on very heavy volume (earnings when confirmed), after which
    the stock never undercuts the gap-day low and tightens near the 8/21 EMA.

These are research candidates, not signals: every row carries the exact
measurements so the chart can be checked.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict, replace
import numpy as np
import pandas as pd
from crescent_engine import normalise, atr14, finite


@dataclass(frozen=True)
class Tightness:
    """The 'small candles hugging the 8 EMA' rule."""
    window: int = 5                 # recent sessions inspected
    tight_days: int = 3             # how many of them must be small-range
    range_ratio: float = 0.60       # small = range < ratio x 20-day average range
    close_cluster: int = 3          # last N closes must cluster...
    close_spread_pct: float = 1.5   # ...within this % of each other
    ema_atr: float = 1.0            # each of those closes within this many ATR of the 8 EMA
    below_ema_atr: float = 0.5      # last close no more than this many ATR under the 8 EMA
    volume_ratio: float = 0.80      # avg volume of the cluster < ratio x 50-day avg volume


PRESETS = {
    'Standard': Tightness(),
    'Very strict': Tightness(range_ratio=0.50, close_spread_pct=1.0, volume_ratio=0.60, ema_atr=0.75,
                             below_ema_atr=0.25),
    'Loose': Tightness(range_ratio=0.75, close_spread_pct=2.5, volume_ratio=1.00, ema_atr=1.5, tight_days=2),
}


@dataclass(frozen=True)
class VCPRules:
    base_lookback: int = 120        # sessions searched for the base high
    min_contractions: int = 2
    max_contractions: int = 4
    first_max_depth: float = 35.0   # % depth allowed for the first pullback
    last_max_depth: float = 12.0    # % depth allowed for the final pullback
    shrink_tolerance: float = 1.10  # each depth must be < previous x tolerance... and smaller overall
    zigzag_pct: float = 3.0         # swing size used to find pullbacks
    max_below_pivot_pct: float = 8.0
    max_above_pivot_pct: float = 1.0  # beyond this it has already broken out
    near_high_pct: float = 25.0     # within 25% of the 52-week high
    above_low_pct: float = 25.0     # at least 25% above the 52-week low


@dataclass(frozen=True)
class PEGRules:
    lookback: int = 40              # gap must be within this many sessions
    min_days_after: int = 3         # need some consolidation after the gap
    gap_pct: float = 5.0            # open vs prior close
    volume_mult: float = 2.5        # gap-day volume vs 50-day average before it
    close_in_range: float = 0.50    # gap-day close in the upper half of its range
    ema_choices: tuple = (8, 21)    # tight area may hug the 8 or the 21 EMA


# ---------------------------------------------------------------- helpers

def zigzag(high, low, pct):
    """Alternating swing points [(index, price, 'H'|'L')] that reverse by >= pct %.

    The final point is the still-open extreme of the current swing.
    """
    h = np.asarray(high, float); l = np.asarray(low, float); n = len(h)
    if n < 2: return []
    pts = []; trend = 0; hi_i = lo_i = 0
    for i in range(1, n):
        if trend == 0:
            if h[i] > h[hi_i]: hi_i = i
            if l[i] < l[lo_i]: lo_i = i
            if hi_i < i and (h[hi_i] - l[i]) / h[hi_i] * 100 >= pct:
                pts.append((hi_i, h[hi_i], 'H')); trend = -1; lo_i = i
            elif lo_i < i and (h[i] - l[lo_i]) / l[lo_i] * 100 >= pct:
                pts.append((lo_i, l[lo_i], 'L')); trend = 1; hi_i = i
        elif trend == 1:
            if h[i] >= h[hi_i]: hi_i = i
            elif (h[hi_i] - l[i]) / h[hi_i] * 100 >= pct:
                pts.append((hi_i, h[hi_i], 'H')); trend = -1; lo_i = i
        else:
            if l[i] <= l[lo_i]: lo_i = i
            elif (h[i] - l[lo_i]) / l[lo_i] * 100 >= pct:
                pts.append((lo_i, l[lo_i], 'L')); trend = 1; hi_i = i
    if trend == 1: pts.append((hi_i, h[hi_i], 'H'))
    elif trend == -1: pts.append((lo_i, l[lo_i], 'L'))
    return pts


def _ema(series, span):
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def tight_area(f, rules: Tightness, ema_spans=(8,)):
    """Measure the tight-candle cluster. Returns (passed, details)."""
    if len(f) < 60: return False, {'why': 'Fewer than 60 sessions'}
    atr = atr14(f)
    if not atr: return False, {'why': 'ATR unavailable'}
    rng = f.High - f.Low
    avg_rng = float(rng.iloc[-21:-1].mean())
    recent = f.iloc[-rules.window:]
    small = int((rng.iloc[-rules.window:] < rules.range_ratio * avg_rng).sum())
    closes = f.Close.iloc[-rules.close_cluster:]
    spread = float((closes.max() - closes.min()) / closes.min() * 100)
    vol50 = float(f.Volume.iloc[-51:-1].mean())
    vol_recent = float(f.Volume.iloc[-rules.close_cluster:].mean())
    vol_ratio = vol_recent / vol50 if vol50 > 0 else np.nan
    best = None
    for span in ema_spans:
        ema = _ema(f.Close, span)
        dist = ((closes - ema.iloc[-rules.close_cluster:]) / atr)
        last = float(dist.iloc[-1])
        ok = bool((dist.abs() <= rules.ema_atr).all()) and last >= -rules.below_ema_atr
        cand = {'span': span, 'ok': ok, 'dist_atr': last, 'ema': float(ema.iloc[-1])}
        if best is None or (ok and not best['ok']) or (ok == best['ok'] and abs(last) < abs(best['dist_atr'])):
            best = cand
    details = {
        'small_days': small, 'close_spread_pct': spread, 'volume_ratio': vol_ratio,
        'ema_span': best['span'], 'ema': best['ema'], 'ema_dist_atr': best['dist_atr'],
        'tight_low': float(recent.Low.min()), 'tight_high': float(recent.High.max()), 'atr': atr,
    }
    checks = [
        (small >= rules.tight_days, f'{small}/{rules.window} small-range days (need {rules.tight_days})'),
        (spread <= rules.close_spread_pct, f'closes spread {spread:.2f}% (max {rules.close_spread_pct}%)'),
        (best['ok'], f"closes {best['dist_atr']:+.2f} ATR from {best['span']} EMA (max {rules.ema_atr})"),
        (finite(vol_ratio) and vol_ratio < rules.volume_ratio, f'volume {vol_ratio:.2f}x 50D avg (max {rules.volume_ratio})'),
    ]
    failed = [msg for ok, msg in checks if not ok]
    details['why'] = '; '.join(failed) if failed else 'Tight closes on the EMA with volume drying up'
    return not failed, details


def trend_template(f):
    """Simplified stage-2 template. Returns (passed, details)."""
    if len(f) < 220: return False, {'why': 'Fewer than 220 sessions for the 200-day trend'}
    c = f.Close
    s50 = c.rolling(50).mean(); s150 = c.rolling(150).mean(); s200 = c.rolling(200).mean()
    last = float(c.iloc[-1])
    hi52 = float(f.High.iloc[-252:].max()); lo52 = float(f.Low.iloc[-252:].min())
    d = {'sma50': float(s50.iloc[-1]), 'sma150': float(s150.iloc[-1]), 'sma200': float(s200.iloc[-1]),
         'high52': hi52, 'low52': lo52}
    checks = [
        (last > s50.iloc[-1] > s150.iloc[-1] > s200.iloc[-1], 'price > 50 > 150 > 200 SMA'),
        (s200.iloc[-1] > s200.iloc[-21], '200 SMA rising over a month'),
    ]
    failed = [m for ok, m in checks if not ok]
    d['why'] = 'Stage 2 uptrend' if not failed else 'Not in stage 2: ' + '; '.join(failed)
    return not failed, d


def contractions(f, rules: VCPRules):
    """Pullback depths (%) inside the current base, oldest first, and the pivot.

    The base starts at the highest high of the lookback. Each contraction is a
    swing high followed by a swing low (the last low may still be forming). The
    pivot is the high of the most recent contraction; a still-rising swing that
    has not pulled back yet is not counted as a contraction.
    """
    window = f.iloc[-rules.base_lookback:]
    base_i = int(np.argmax(window.High.values))
    base = window.iloc[base_i:]
    if len(base) < 10: return [], None, base
    pts = zigzag(base.High.values, base.Low.values, rules.zigzag_pct)
    if not pts or pts[0][2] != 'H':
        pts = [(0, float(base.High.iloc[0]), 'H')] + pts  # the base high starts the first contraction
    depths = []; pivot = None
    for k, (i, price, kind) in enumerate(pts):
        if kind != 'H': continue
        low = next((p for p in pts[k + 1:] if p[2] == 'L'), None)
        if low is None: continue
        depths.append((price - low[1]) / price * 100)
        pivot = float(price)
    return depths, pivot, base


def scan_vcp(symbol, raw, spy=None, tight: Tightness = Tightness(), rules: VCPRules = VCPRules()):
    f = normalise(raw)
    ok, trend = trend_template(f)
    if not ok: return None, trend['why']
    last = float(f.Close.iloc[-1])
    if last < trend['high52'] * (1 - rules.near_high_pct / 100): return None, 'More than 25% below the 52-week high'
    if last < trend['low52'] * (1 + rules.above_low_pct / 100): return None, 'Not far enough above the 52-week low'
    depths, pivot, base = contractions(f, rules)
    if pivot is None: return None, 'No base yet (price is at its high)'
    n = len(depths)
    if not (rules.min_contractions <= n <= rules.max_contractions):
        return None, f'{n} pullbacks in the base (need {rules.min_contractions}-{rules.max_contractions})'
    if depths[0] > rules.first_max_depth: return None, f'First pullback {depths[0]:.1f}% is too deep'
    if depths[-1] > rules.last_max_depth: return None, f'Last pullback {depths[-1]:.1f}% is not tight'
    shrinking = all(b < a * rules.shrink_tolerance for a, b in zip(depths, depths[1:])) and depths[-1] < depths[0]
    if not shrinking: return None, 'Pullbacks are not getting smaller'
    gap = (last / pivot - 1) * 100
    if gap > rules.max_above_pivot_pct: return None, 'Already broken out above the pivot'
    if gap < -rules.max_below_pivot_pct: return None, f'{-gap:.1f}% below the pivot'
    tight_ok, t = tight_area(f, tight, (8,))
    if not tight_ok: return None, 'Tight area: ' + t['why']
    first_leg_vol = float(base.Volume.iloc[:max(5, len(base) // 3)].mean())
    last_leg_vol = float(base.Volume.iloc[-5:].mean())
    stop = min(t['tight_low'], float(base.Low.iloc[-max(5, len(base) // 4):].min())) - 0.1 * t['atr']
    trigger = pivot + 0.03 * t['atr']
    row = _row(symbol, 'VCP', f, spy, t, trigger, stop)
    row.update({
        'Pullbacks': ' → '.join(f'{d:.0f}%' for d in depths), 'Contractions': n,
        'Base days': len(base), 'Pivot': round(pivot, 2), 'Vs pivot %': round(gap, 2),
        'Base vol dry-up': round(last_leg_vol / first_leg_vol, 2) if first_leg_vol > 0 else None,
    })
    return row, 'VCP'


def scan_peg(symbol, raw, spy=None, tight: Tightness = Tightness(), rules: PEGRules = PEGRules(),
             earnings_dates=None):
    """`earnings_dates`: optional iterable of dates; when given, the gap is labelled confirmed."""
    f = normalise(raw)
    if len(f) < 80: return None, 'Fewer than 80 sessions'
    prev_close = f.Close.shift(1)
    vol50 = f.Volume.shift(1).rolling(50, min_periods=40).mean()
    gap = (f.Open / prev_close - 1) * 100
    rng = (f.High - f.Low).replace(0, np.nan)
    pos = (f.Close - f.Low) / rng
    n = len(f)
    start = max(1, n - rules.lookback); end = n - rules.min_days_after
    found = None
    for i in range(end - 1, start - 1, -1):          # most recent qualifying gap first
        if gap.iloc[i] >= rules.gap_pct and f.Volume.iloc[i] >= rules.volume_mult * vol50.iloc[i] \
                and pos.iloc[i] >= rules.close_in_range:
            found = i; break
    if found is None: return None, 'No power gap in the lookback'
    day = f.iloc[found]; after = f.iloc[found + 1:]
    if float(after.Low.min()) < float(day.Low): return None, 'Undercut the gap-day low'
    last = float(f.Close.iloc[-1])
    if last < float(f.Close.rolling(50).mean().iloc[-1]): return None, 'Below the 50-day average'
    tight_ok, t = tight_area(f, tight, rules.ema_choices)
    if not tight_ok: return None, 'Tight area: ' + t['why']
    gap_date = f.index[found].date()
    confirmed = None
    if earnings_dates is not None:
        dates = {pd.Timestamp(d).date() for d in earnings_dates}
        confirmed = any(abs((pd.Timestamp(gap_date) - pd.Timestamp(d)).days) <= 3 for d in dates)
    trigger = float(after.High.iloc[-5:].max()) + 0.03 * t['atr']
    stop = max(float(day.Low), t['tight_low']) - 0.1 * t['atr']
    row = _row(symbol, 'PEG', f, spy, t, trigger, stop)
    row.update({
        'Gap date': str(gap_date), 'Gap %': round(float(gap.iloc[found]), 1),
        'Gap volume x': round(float(f.Volume.iloc[found] / vol50.iloc[found]), 1),
        'Gap-day low': round(float(day.Low), 2), 'Days since gap': int(n - 1 - found),
        'Earnings': 'Unverified' if confirmed is None else 'Confirmed' if confirmed else 'Not earnings',
    })
    return row, 'PEG'


def leadership(f):
    """Momentum leadership from the original scanner's Weekly Leaders, computed from daily history.

    A timeframe counts when the return clears its bar (1W 20%, 1M 30%, 3M 70%, 6M 100%)
    while price is at least 50% above the 52-week low and holds above a 10-day average
    that is within 20% of it. Three or more timeframes = CORE LEADER, two = LEADER, one
    with a 3M gain over 30% or a 6M gain over 50% = EMERGING.
    """
    c = f.Close
    if len(c) < 130: return ''
    last = float(c.iloc[-1]); sma10 = float(c.tail(10).mean())
    if last < float(f.Low.tail(252).min()) * 1.5 or not (last * 0.80 <= sma10 <= last): return ''
    gain = {n: (last / float(c.iloc[-n - 1]) - 1) * 100 for n in (5, 21, 63, 126)}
    hits = sum(gain[n] > bar for n, bar in ((5, 20), (21, 30), (63, 70), (126, 100)))
    if hits >= 3: return 'CORE LEADER'
    if hits == 2: return 'LEADER'
    if hits == 1 and (gain[63] > 30 or gain[126] > 50): return 'EMERGING'
    return ''


def _row(symbol, setup, f, spy, t, trigger, stop):
    last = float(f.Close.iloc[-1])
    rs = None
    if spy is not None and len(spy) > 63 and len(f) > 63:
        s = normalise(spy)
        if len(s) > 63 and s.index[-1] == f.index[-1]:
            rs = ((last / float(f.Close.iloc[-64])) - (float(s.Close.iloc[-1]) / float(s.Close.iloc[-64]))) * 100
    risk = trigger - stop
    return {
        'Symbol': symbol, 'Setup': setup, 'Close': round(last, 2),
        'Trigger': round(trigger, 2), 'Stop': round(stop, 2),
        'Risk %': round(risk / trigger * 100, 2) if trigger > 0 and risk > 0 else None,
        'Tight days': t['small_days'], 'Close spread %': round(t['close_spread_pct'], 2),
        'EMA': f"{t['ema_span']} EMA", 'Vs EMA ATR': round(t['ema_dist_atr'], 2),
        'Volume vs 50D': round(t['volume_ratio'], 2), 'RS 63D vs SPY pp': round(rs, 1) if rs is not None else None,
        'Leadership': leadership(f),
        'Day vol vs 20D %': round((float(f.Volume.iloc[-1]) / float(f.Volume.iloc[-21:-1].mean()) - 1) * 100, 1)
            if len(f) > 21 and float(f.Volume.iloc[-21:-1].mean()) > 0 else None,
        'As of': str(f.index[-1].date()),
    }


def scan(history, spy=None, setups=('VCP', 'PEG'), tight: Tightness = Tightness(),
         vcp: VCPRules = VCPRules(), peg: PEGRules = PEGRules(), earnings=None):
    """Run the chosen setups over {symbol: daily frame}. Returns (matches, reasons)."""
    rows = []; reasons = {}
    earnings = earnings or {}
    for symbol, raw in history.items():
        if symbol == 'SPY': continue
        why = []
        try:
            if 'VCP' in setups:
                row, msg = scan_vcp(symbol, raw, spy, tight, vcp)
                if row: rows.append(row)
                else: why.append('VCP: ' + msg)
            if 'PEG' in setups:
                row, msg = scan_peg(symbol, raw, spy, tight, peg, earnings.get(symbol))
                if row: rows.append(row)
                else: why.append('PEG: ' + msg)
        except Exception as exc:  # one bad series must not stop the scan
            why.append(f'{type(exc).__name__}: {str(exc)[:80]}')
        if why and not any(r['Symbol'] == symbol for r in rows): reasons[symbol] = ' | '.join(why)
    out = pd.DataFrame(rows)
    if not out.empty:
        out['_rs'] = out['RS 63D vs SPY pp'].fillna(-999)
        out = out.sort_values(['Setup', '_rs', 'Close spread %'], ascending=[False, False, True]).drop(columns='_rs')
        out = out.reset_index(drop=True)
    return out, reasons


def annotate(matches, names):
    """Add names for ETFs / commodities and mark earnings as not applicable for them."""
    if matches.empty:return matches
    out=matches.copy()
    label=out['Symbol'].map(names)
    if label.notna().any():out.insert(1,'Name',label.fillna(''))
    if 'Earnings' in out:out.loc[out['Symbol'].isin(names)&out['Earnings'].notna(),'Earnings']='Not applicable'
    return out


def with_overrides(preset, **values):
    """Copy a Tightness preset with user-edited values."""
    return replace(preset, **{k: v for k, v in values.items() if v is not None})


def as_dict(obj):
    return asdict(obj)
