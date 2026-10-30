CRESCENT INSIGHTS — V7 STANDALONE DECISION & EXECUTION DESK
=========================================================
Version: 7.0 beta | 30 October 2026

THIS IS A NEW STREAMLIT APP. IT DOES NOT MODIFY cresinstv.streamlit.app.
The original Crescent V5/V6 scanner remains separate and should not be replaced.

QUICK START (NEW GITHUB REPOSITORY)
1. Create a NEW GitHub repository, for example crescent-execution-v7.
2. Unzip Crescent_V7_STANDALONE_NEW_APP_FLAT.zip.
3. For best compatibility, choose Python 3.12 for the new Streamlit app.
4. Upload the extracted contents directly to the ROOT of the NEW repository:
   app.py, crescent_engine.py, crescent_feeds.py, crescent_ui.py,
   crescent_charts.py, cloud_engine.py, rotation_themes.py,
   stocks.csv, etfs.csv, requirements.txt, and the documentation files.
5. On share.streamlit.io choose Create app / Deploy, select the NEW repository,
   choose branch main, main file app.py, and a NEW app URL.
6. Do NOT deploy this into the repository for cresinstv.streamlit.app.
7. Initial screen is clearly marked DEMO / SIMULATED. Switch to Yahoo Finance
   in the sidebar and press Run overnight research to request real daily data.
8. Remember to export your journal's session JSON; Streamlit Community Cloud
   restarts can erase session state.

GitHub does NOT deploy code from a ZIP stored as one repository file. Files must
be extracted to the repository root. This package intentionally has NO folders.

ALTERNATIVE LOCAL RUN (after installing Python)
  python -m pip install -r requirements.txt
  python -m streamlit run app.py

WHAT THE NEW APP DOES
- Night Plan: sector-neutral completed-daily screening, regime context, at most
  three precommitted plans, explicit triggers, invalidation, next obstacle/R:R.
- Pre-open: optional extended-hours quote revalidation, no READY state.
- Live Desk: checks only frozen plans from completed 10m RTH bars + VWAP,
  stale-data, opening restriction, no chase, structural stop and event gates.
- Regime & Rotation: eleven sector ETFs, index context, 5D/21D SPY-relative
  leadership, defensive leadership changes, cross-assets, and read-only
  optional news headlines. A sector ETF is a proxy, NOT fund-flow data.
- Research: candidate ranking, 90 original theme baskets with honest coverage
  warnings, and per-symbol Air Gap research using the existing pure cloud engine.
- Journal: manual entry/exit/skip record (session-only) with import/export JSON.
- Settings: earliest entry time, cooldown, manual event blocker, upload of
  self-verified macro/earnings CSV. There is no position-sizing calculator.

DATA SOURCES / GAPS
- Demo is SIMULATED using deterministic synthetic candles for illustration;
  e.g. LLY / PG demo prices DO NOT match real-world quotes.
- Yahoo is an unofficial, delayed, best-effort provider and may fail/rate-limit.
  This is NOT a low-latency execution feed. Missing data yields no signal.
- TradingView public Screener is optional, unofficial, may fail, and is NOT the
  same thing as a ChatGPT-connected or authenticated TradingView account.
  Yahoo provides actual OHLCV for V7, even when TradingView helps discovery.
- Political / war / tariff headlines: OPTIONAL Google News RSS headline feed;
  headline text is NOT verification and never triggers a trade automatically.
- Economic / corporate event calendar: USER-SUPPLIED CSV. Without an uploaded
  and verified calendar the system explicitly says EVENTS NOT VERIFIED.
- No broker connection, position syncing, automatic orders, options spread
  checks, win-rate forecasts, or risk enforcement.
- Technical thresholds, multi-timeframe rules and sector thresholds are
  hypotheses requiring forward testing against the user's actual execution.
- If data is stale, a valid overnight plan CANNOT turn into READY.

QUALITY ASSURANCE
- All 24 offline unit tests passed in this environment (calculation/logic).
- All Python files compile; a mock-UI smoke test exercised each major screen.
- Static visual preview was tested in Chromium at desktop and 412px mobile
  (no horizontal overflow). The HTML is a visual prototype, NOT the Streamlit UI.
- Full Streamlit browser runtime and Yahoo/TradingView network performance could
  NOT be tested here because Streamlit / data dependencies and internet access
  were unavailable. Test the new deployment before relying on live decisions.

FILES
  app.py                 new standalone Streamlit UI
  crescent_engine.py     pure completed-bar, rotation, plan and execution logic
  crescent_feeds.py      optional Yahoo/TradingView, news/events, demo
  crescent_ui.py         original Crescent logo geometry + UI styling
  crescent_charts.py     focused interactive Plotly OHLC/EMA/volume chart
  cloud_engine.py        preserved technical MTF/Air Gap pure functions
  rotation_themes.py     preserved 90 analyst-curated theme baskets
  stocks.csv             preserved original 574-stock universe
  etfs.csv               preserved original 96-ETF reference universe
  requirements.txt       Streamlit runtime dependencies
  events_template.csv    import schema for user-verified events
  test_crescent_v7.py    24 offline regression tests
  Crescent_V7_Visual_Preview.html, PNGs   simulated preview only

FOR YOUR FIRST TEST
1. Open NEW Streamlit app in Demo mode.
2. Open Regime & Rotation; verify you see a labelled SIMULATED defensive shift.
3. Open Night Plan; inspect LLY and PG SIMULATED candidates. Freeze at most 3.
4. Open Live Desk; see that synthetic prices cannot trigger READY.
5. Switch to Yahoo beta; run Balanced 60; inspect coverage and as-of.
6. Verify macro-event restrictions and check earnings in your trusted sources.
7. Open live desk only in a real cash session, with a frozen plan.
8. Export Journal JSON before closing the browser.

Keep the original trading app untouched until this standalone beta passes
several real market sessions and is reviewed alongside actual TradingView charts.
