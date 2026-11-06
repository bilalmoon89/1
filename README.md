# Crescent Trade Terminal — BETA

A standalone research terminal with Crescent's deep-navy and gold visual direction. This repository is separate from the production Crescent Scanner.

The previous workspace tabs have been replaced by one screen:

- Market regime and benchmark context.
- Sector leadership from completed daily ETF history.
- Ranked opportunities with direction and symbol filters.
- Six ranked setup cards by default, with options to display 12 or 24 from the same loaded universe. All qualifying candidates and sector-balanced views share the existing entry criteria.
- **The Watchtower**: follow up to 12 setups and promote up to three into focus for trigger checks, focused charts, and manual position management. Following never grants entry permission.
- **Theme rotation**: intraday return, SPY-relative movement, session VWAP participation and daily lifecycle for observed members of the existing 90 curated baskets. Partial coverage is labelled on every basket.
- Expandable session journal, JSON backups, event calendar and terminal controls.
- A highlighted **Liquid Uptrend** header link opens a dedicated scan page with the user's standard ALL preset and editable exclusions.

## Run

Use Python 3.12 or newer, install `requirements.txt`, then run:

```sh
python -m streamlit run app.py
```

The terminal automatically requests real Yahoo Finance market history on first load. There is no demo mode or generated-price fallback. Use Scan now to refresh or change the balanced universe. Yahoo is best effort and delayed; failed instruments are excluded and listed under Data connection / coverage. Intraday monitoring checks run on request, with no automatic orders.

The market strip shows VIX, SPY, QQQ, IWM, RSP, DIA and TLT. Sector and ETF readings use completed **5-minute regular-session bars**, refreshed every 60 seconds: Today %, same-session relative strength versus SPY, and session VWAP. Partial bars and premarket bars are excluded. VIX uses its own delayed index timestamp, rather than being discarded for failing exact SPY alignment; delayed, stale, closed or last-daily-close readings are labelled explicitly. Daily setup ranking and the separate daily backdrop retain the existing calculation rules.

TradingView stock quote comparison is available in its own expandable panel. Public screener requests returned stock quotes marked 15 minutes delayed in testing, while the tested sector ETFs returned no rows. TradingView quotes do not replace Yahoo candles or authorize entries, and the hosted app does not inherit a ChatGPT TradingView connection or subscription.

Fonts and contrast have been increased. The interface stacks into one column on phones, with two-column benchmark cards, wrapped sector names and 44-pixel action buttons. Dark tables scroll within their own panels where needed.

The interface follows the supplied TapeReader reference: a compact masthead, market strip with real-history sparklines, four context panels, scan controls, three ranked setup cards and The Watchtower. Every table uses the terminal's dark palette. The Streamlit version is pinned so deployments do not silently change frontend versions.

## Behavior preserved

The existing calculation engine, feeds, universe files, event checks, three-plan focus limit and live-entry gates are retained. The broader candidate view removes only the presentation cap of two names per sector. Research candidates are never treated as confirmed entries. Session JSON adds an optional `following` field; valid older backups restore into both the followed list and focus list.

Related themes are selected when at least two members occur in the loaded universe. The terminal then loads the remaining members of those baskets into a separate theme-history layer. Those extra names improve breadth coverage but do not enter the stock candidate universe automatically. The colourful detail table shows the entire defined member list: green/red chips have session readings, blue chips have daily history only, and dim chips are unavailable. Themes need at least three members and 70% basket coverage for a broad-coverage label; partial readings are explicitly averages of observed members.

## Liquid Uptrend preset

Open `?view=liquid` from the highlighted header link. All six numerical checks must pass. Intraday (default) uses TradingView session price, daily SMA50/SMA200 and active session range, with Yahoo completed-session liquidity baselines. Completed daily mode remains available:

- Average volume over 20 sessions > 1,000,000.
- Average close × volume over 50 sessions > $100,000,000.
- Price relative to both SMA200 and SMA50 > 0.01%.
- ADR over one session and 20 sessions > 3%. ADR N = (mean high N − mean low N) / latest close × 100.

The standard exclusion removes Pharmaceuticals, Biotechnology & Life Sciences using a bounded TradingView industry-classification request. This includes drug manufacturers and diagnostics/research where identified. The classification source is displayed; unverified industries are held out while the exclusion is enabled. The page supports additional ticker/industry-keyword exclusions and a one-click restoration of the standard preset. The selected 60/120/574-stock scope is labelled; this is not a claim of scanning every US listing. Passing this discovery screen does not authorize an entry.

The former Night Plan, Pre-open, Live Desk, Regime & Rotation, and Research screens are no longer navigation destinations. This rework does not add new Air Gap detection rules or data services. Legacy screenshots and release documents are retained under `docs/legacy` for historical reference only.

## Verify

```sh
python -m pytest -q
```

Deploy only this repository to its separate test Streamlit application using `app.py`. Do not replace the production scanner deployment.

Liquid Uptrend opens without provider requests. Run explicitly to process 12 stocks per batch with progress and a stop control. Daily requests have a 12-second outer deadline; classification has an 8-second deadline. Failed daily requests are retried on the next explicit scan, and a wholly failed refresh retains the last successful results. Partial coverage is displayed.


Liquid Leaders updates quotes while scanning (at most once per 60 seconds). Once the scan completes, its timer stops and the table stays still; Refresh quotes requests an update manually (provider feed delays still apply). It shows today %, from-open %, distance from VWAP, session volume, relative volume, quote/bar update time, feed mode, and retrieval time in a colored, horizontally scrollable table. Quotes from a previous session, future timestamps, and quotes older than 30 minutes during regular hours are held out. Missing quotes never fall back silently to yesterday's close. Historical 20D volume and 50D dollar volume stay based on completed sessions; intraday ADR20 combines 19 completed daily ranges with the active session range.

The default universe is now the full 574-stock list. A TradingView US discovery option scans up to 1,500 primary stocks above SMA50/SMA200, ranked by 90D average volume. This is a capped discovery selection, not all US listings. Additional tickers can be appended to either universe. Every ticker still passes all exact technical/liquidity conditions and exclusions. Partial results appear while bounded 12-stock batches load; successful historical batches are cached for 20 minutes and failed batches remain retryable. This public screener adapter does not inherit the user's authenticated TradingView market-data entitlements.

Industry and curated Theme membership appear immediately after RVOL. Quote ET and Retrieved ET show HH:MM:SS in Eastern Time; baseline dates are omitted from the displayed/exported leaders table. Full timestamps and baseline dates remain available internally for freshness checks and calculations.


After-hours validity: the terminal market strip and Liquid Leaders use regular-session data, not an extended-hours feed. The XNYS exchange calendar determines the latest expected session, including holidays, weekends, premarket and early closes. Old/missing closing bars are marked STALE or CLOSE PENDING rather than CLOSED. Benchmark cards retain full session dates; Liquid Leaders shows Session and Session status separately from shortened ET timestamps. Daily research completion uses the actual exchange close plus the existing 15-minute provider buffer, and an old saved daily snapshot prompts a rescan after that buffer. A completed regular-session close is never labelled as a current extended-hours quote.


## Ticker Check

Open the highlighted Ticker Check link (`?view=ticker`). It loads only when Check ticker is pressed. The report combines five reported revenue quarters, gross/operating/net margins, net income, diluted EPS and matching-period revenue YoY growth with current valuation multiples and completed daily/weekly technicals. It uses Yahoo Finance financials/history plus a separately timestamped TradingView session quote; missing fields remain unavailable. Provider failures are not cached as successful reports.

Daily EMA9/21/50, daily SMA200 and weekly EMA8 are displayed. Daily holding requires three closes above and a recent test within 0.25 daily ATR. Weekly support is separately labelled tested/held, above/untested or below, using completed weeks. A completed daily close below SMA200 or a valid current TradingView price below its daily SMA200 is a hard NO GO. Weekly stage estimates use the completed 30-week SMA and disclosed four-week slope rules; ambiguous cases remain unclear.

High tight flag is a preferred candidate: 100%+ advance within 40 sessions, followed by 10–25 sessions consolidating within 25% of the pole high on lower average volume. It does not bypass trend/risk checks. Conditional breakout and pullback stops use observed structural lows with a 0.15 ATR buffer. Targets use observed historical resistance; unknown targets stay blank. At least 2R and risk no greater than 3 ATR are required for a conditional plan. No automatic entries or orders are created, and live confirmation remains required.

Historical valuation is explicitly an annual fiscal-year-end P/E snapshot reference, not a daily historical trading-average P/E. Currency mismatch, unreconciled splits, missing EPS and nonpositive earnings withhold affected historical comparisons. Full point-in-time historical multiples require a richer fundamental data source. This independent review does not change the scanner's existing detection/ranking rules.
