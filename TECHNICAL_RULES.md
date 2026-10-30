# Crescent V7 — decision engine / audit notes

## Architecture
A **separate** Streamlit service. No imports from or modifications to the user's deployed Crescent Scanner. Research files copied from the recovered original September archive are `stocks.csv` (574), `etfs.csv` (96), `rotation_themes.py` (90 baskets), and the existing technical `cloud_engine.py`. The original Crescent logo geometry is reused in `crescent_ui.py`.

## Timeframe discipline
- Night research consumes *completed* daily candles only. Today's possibly unfinished daily bar is removed until 16:15 US Eastern. A provider can still be late or revise bars; all timestamps appear on screen.
- An overnight candidate is `ARMED`, `WATCH`, `BLOCKED`, or `EXTENDED` — **never** live `READY`.
- A plan freezes trigger, stop and target; new scans do not rewrite saved levels.
- Pre-open revaluation is read-only (`RECHECK`, `SUPPORT AT RISK`, `EXTENDED`, `STALE`); never READY.
- Live stage checks a frozen ARMED plan on completed RTH ten-minute bars constructed from exact pairs of 5-minute bars, after a configurable opening wait. Required: close beyond frozen trigger, same-direction VWAP, no extended entry, remaining reward/risk >=1.5, event check acknowledged, and no user event block. Live checks expire after 3 minutes in the UI.
- Live bars missing, old, or from another day => `STALE`. A plan older than the previous completed weekday session => `STALE` (conservative on holidays).
- Structural stop / first confirmed historical swing high or low selected from past bars only. No artificial ATR price target used to manufacture R:R.
- Positions are *manually recorded* in the browser session and are not verified against a broker. Underlying reference levels do not guarantee option fills.

## Current supported setup families
1. `TREND PULLBACK`: trend-aligned daily EMA21 proximity, constructive bar, then a frozen trigger above daily high. The app waits for a completed 10m/VWAP confirmation; do not infer a reversal because price is down intraday.
2. `BASE BREAKOUT`: uptrend, price near prior 20-session high, modest range contraction. This is a simplified discovery heuristic, **not** a complete Minervini/Qullamaggie VCP detector.
3. `FAILED BOUNCE`: independent confirmed downtrend and weak bounce, *never* a short created because the trader missed a long. Requires independent sector and market qualification.
4. `MTF Air Gap`: research-only single-symbol cloud study (1H 34/50, daily 20/21 & 50/55) under a separate research panel; its A+ grade is not an empirically calibrated win rate or an entry order.

We intentionally do **not** pretend this implementation contains the full original 30m Pivot, U&R, options, confluence, or nightly PDF features. Those remain available in the unchanged original Crescent scanner; adding them to the new decision engine requires exact backtested definitions and provider parity.

## Regime / sector philosophy
- Compute 5/10/21/60-day sector ETF returns and their percentage-point performance versus SPY; track relative pace, daily EMA21/50 structure, and leading / cooling / emerging / lagging states.
- A defensive leadership classification requires meaningful defensive ETF relative strength while technology lags. This is a research heuristic, not a binary ban on longs.
- Sector *ETF* performance is a proxy. True constituent breadth is only shown in theme tables when >=3 names and >=60% of an analyst basket were downloaded with comparable dates; otherwise `INSUFFICIENT COVERAGE`.
- Scan is not hardcoded to semiconductors. Balanced 60/120 default candidates sample every sector; optional TradingView Screener discovery can expand and prioritize stocks; full 574 daily request is optional and has rate-limit risk. Including ETFs adds a diversified, non-leveraged sleeve to the request.
- Missing benchmark/SPY coverage means **UNKNOWN** regime; missing a sector ETF means the setup is WATCH rather than ARMED.

## Risk / provider rules
- No automatic orders, no position size controls, no brokerage access. If a manual position is marked, its screen changes to management rather than another entry scanner.
- Macro and war headlines are non-authoritative until independently verified. A manually uploaded, *confirmed* high-impact event near the time blocks live entry review. The app does not pretend it knows today's complete earnings/economic schedule.
- Every data source is labelled. A failed Yahoo or TV request is displayed; the previous demo may remain visible but is explicitly labeled simulated.
- R:R is computed using the *frozen* planned trigger vs stop and next confirmed swing pivot; live R:R is recomputed from current 10-minute close. No win probabilities are invented.
- No persistent user data on a public shared server. Session JSON export/import is deliberate. Use secured private backend before storing sensitive trading data long term.

## Roadmap after first release
- Replace Yahoo with a licensed reliable SIP intraday provider for timely live verification.
- Add trustworthy earnings/economic calendars with timestamps, source lineage, and provisional/confirmed flags.
- Reconcile signal thresholds against TradingView, adjust for dividends/splits and holidays, and unit-test incomplete candles.
- Add time-frozen event database and outcome journal; test net expectancy, drawdowns, MFE/MAE, and decision adherence, out of sample.
- Add optional alert/webhook integration *only* after source parity and live invalidation logic is validated.
- Keep the existing app untouched while beta is forward-tested in a separate Streamlit deployment.
