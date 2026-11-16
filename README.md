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

## VCP & Power Earnings Gap setups

Open `?view=setups` from the **↗ VCP & PEG** header link. The page scans completed daily candles for accumulation: a run of small candles whose closes sit tightly together on, or just above, the 8 EMA while volume dries up.

- **VCP**: stage-2 uptrend (price > 50 > 150 > 200 SMA, 200 SMA rising, within 25% of the 52-week high). The base must show 2–4 pullbacks, each smaller than the last, with the final pullback at most 12%. Price must be just under the pivot (not already broken out), and the tight 8 EMA area must be present.
- **PEG (Power Earnings Gap)**: a gap of at least 5% on at least 2.5× the 50-day volume, closing in the upper half of the day, within the last 40 sessions. The stock must never undercut the gap-day low and must then tighten on the 8 or 21 EMA. Yahoo earnings dates label each gap Confirmed / Not earnings / Unverified.
- **Tight-candle rule (Standard preset)**: 3 of the last 5 days have a range under 60% of the 20-day average range. The last 3 closes are within 1.5% of each other and within 1 ATR of the EMA. Volume is under 80% of the 50-day average. Very strict and Loose presets are included, and every value is editable.

Each row shows trigger, stop, risk %, the pullback sequence or gap details, and RS vs SPY. Rows are candidates, not signals. Your own tickers get a "why not matched" explanation.

## Changes in 7.8.0

- `stocks.csv`: 413 of 415 "US Large/Mid Cap" rows now carry GICS sectors, so they can reach ARMED. Remaining or unknown names (including TradingView discoveries and your own list) get their sector from TradingView at scan time.
- One shared sector→ETF map (`sector_map.py`) for scanning and live checks. GLD/GDX/TLT/IBIT are measured against their own asset class.
- Short scores are signed (weaker stocks score higher as shorts).
- Breakouts in open space get a clearly labelled projected 2R target, instead of being stuck at WATCH. The base breakout no longer accepts price already above the pivot. Ticker Check high tight flags get a projected 3R target.
- Live check: any session bar through the stop makes the plan INVALID. Staleness counts real NYSE sessions, and half days/holidays close the live window. The same calendar governs the Watchtower and the live check button.
- A built-in NYSE holiday/half-day calendar is used if `exchange_calendars` is unavailable.
- Provider calls no longer share a 2-thread pool, so a hung request cannot freeze other requests. Failed daily downloads are not cached on the terminal.
- The 60-second intraday refresh only runs while the market is open. Theme metrics are computed once per scan.
- BRK.B / BF.B are requested from Yahoo as BRK-B / BF-B. Your own list is always scanned, with a warning for any ticker that could not be.
- Ticker Check uses the same Wilder ATR as the scanner. Demo-mode leftovers and unused imports were removed, and `use_container_width` was replaced.

## Ticker Check and Liquid Uptrend (7.9.0)

**Ticker Check** is one screen: name and price, the verdict, a gate checklist, key numbers, then trade plan, trend, fundamentals and valuation, with the daily candlestick chart below.

- The gate checklist shows each rule as passed, failed, caution or not present: 200 SMA, stage 2, 8 / 21 / 50 EMA, weekly 8 EMA, distance from the 52-week high, strength vs SPY, VCP, PEG, high tight flag, fundamentals, and earnings within 7 days.
- The VCP and PEG rules from the scanner (Standard preset) now run on the ticker. When the trend passes but no entry was defined, the plan uses the scanner's trigger and stop and names its basis. A NO GO is never overridden.
- Key numbers: vs 200 SMA, off 52-week high, 63-session strength vs SPY, distance from the 8 EMA in ATR, ATR and ADR, average dollar volume, next earnings date.
- Daily averages are 8 / 21 / 50 EMA (was 9 / 21 / 50), matching the scanner. The chart is a candlestick with the entry, stop and target drawn, and is no longer hidden in an expander.
- Fundamentals add EPS YoY (blank when the year-earlier EPS is zero or negative) and scale revenue to billions or millions. ETFs, futures and indexes skip the fundamentals gate.
- Chart averages on every page are now computed on the full history before the window is cut, so their first values are correct.

**Liquid Uptrend**

- RS rank (1–99): percentile of the 63-session return across every history loaded in the scan (20 or more needed). Completed-daily results are sorted by it.
- Off 52W high, and a Setup label: `TIGHT · 8 EMA` when the Standard tight-candle rule passes, `EXTENDED` when price is more than 2.5 ATR above the 21 EMA.
- Leading groups: the industries with the most leaders. Feed details that are the same on every row are shown once above the table instead of as six columns. The CSV export keeps every column.
- The explanatory text moved into a "How this scan works" expander.

## Scan tiers (7.8.2)

The VCP & PEG page has three scan sizes. Each one scans the commodities and ETFs first, then US stocks ranked by average daily dollar volume (price × 90-day average volume) behind a $10 price and $20M/day floor.

- **Core**: the 500 most liquid US stocks, the ETFs in `etfs.csv`, and 19 commodities.
- **Medium**: the 1,500 most liquid US stocks, plus the same ETFs and commodities.
- **Full**: every US primary-listed stock that passes the floor (capped at 4,000), plus the same ETFs and commodities.
- **Commodities**: gold, silver, copper, platinum, palladium, WTI, Brent, natural gas, gasoline, heating oil, corn, wheat, soybeans, coffee, sugar, cocoa, cotton and live cattle come from Yahoo front-month futures. SHFE hot-rolled coil (`HC1!`) comes from Sina's main-contract series `HC0`, because Yahoo does not carry SHFE. The main contract is the most active month, which is not always the front month.
- There is no 200 SMA rule, so gaps out of a downtrend are included. Stocks more than 3% under their 50-day average are skipped before download, because neither setup can match them.
- For ETFs and commodities a PEG row is a power gap; the earnings column reads "Not applicable".
- If TradingView's liquidity ranking is unavailable, the stock part falls back to the 574-stock list and the page says so. "Stock list · 574" and "My list only" remain.

## Design (7.8.0)

- Brand from crescentinsights.net: the crescent mark (SVG), a Cormorant Garamond wordmark, Inter body text, brand gold `#B8922A` / `#D4A840` on navy `#0A101A`. Primary buttons are gold with navy text, as on the site.
- One header with page navigation (Terminal · VCP & PEG · Liquid Uptrend · Ticker Check). The links open in the same tab, the current page is highlighted, and the version is read from `VERSION.json`.
- Session-status pills are neutral. Green and red are only used for direction, or for above/below VWAP. Flat sparklines are grey.
- Muted text lifted to at least 4.5:1 contrast. Notices are compact. Panels grow with their content instead of clipping rows.
- Mobile: a stacked header with scrollable nav chips, a two-column market strip, a sticky symbol column in wide tables, and readable 12.5–14px text.

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

Ticker Check uses a compact desktop dashboard: decision and summary cards, side-by-side fundamentals/support and valuation/trade-plan panels, with charts and detailed methodology collapsed below. Panels stack on smaller screens. The shared accent palette uses dark gold buttons with light text; analytical and trading rules are unchanged.

The compact ticker table omits net-income currency amounts while retaining EPS and net margin. Revenue YoY matches year-earlier fiscal quarters from the full statement plus separately requested historical revenue, before selecting five rows. Unavailable comparisons stay blank and the table shows YoY coverage. Rule of 40 uses the latest reported TTM revenue growth plus the same four quarters of FCF divided by TTM revenue. It is labelled with the TTM end date and requires an exact year-earlier TTM revenue comparator; it does not change trade gates.

Where exactly one fiscal revenue quarter is absent and the other three quarters plus the corresponding reported annual total are available, the comparison quarter is reconciled as annual revenue minus those three quarters. Derived comparison dates are disclosed under Analysis detail; the five display quarters remain reported figures. Remaining missing prior-year quarters are not estimated.

Rule of 40 never rolls back to an older common financial period when the latest quarter lacks cash flow or comparison revenue. An annual revenue total can supply the prior TTM comparator only when its period end exactly aligns with that required TTM window. No fiscal-year score is substituted for a missing latest-TTM score.
