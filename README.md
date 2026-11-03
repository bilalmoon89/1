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

## Run

Use Python 3.12 or newer, install `requirements.txt`, then run:

```sh
python -m streamlit run app.py
```

The terminal automatically requests real Yahoo Finance market history on first load. There is no demo mode or generated-price fallback. Use Scan now to refresh or change the balanced universe. Yahoo is best effort and delayed; failed instruments are excluded and listed under Data connection / coverage. Intraday monitoring checks run on request, with no automatic orders.

The market strip and sector panels now use completed **5-minute regular-session bars**, refreshed every 60 seconds: Today %, same-session relative strength versus SPY, and session VWAP. Partial bars and premarket bars are excluded. Missing intraday data stays unavailable; older readings are marked stale or closed. Daily setup ranking and the separate daily backdrop retain the existing calculation rules.

TradingView stock quote comparison is available in its own expandable panel. Public screener requests returned stock quotes marked 15 minutes delayed in testing, while the tested sector ETFs returned no rows. TradingView quotes do not replace Yahoo candles or authorize entries, and the hosted app does not inherit a ChatGPT TradingView connection or subscription.

Fonts and contrast have been increased. The interface stacks into one column on phones, with two-column benchmark cards, wrapped sector names and 44-pixel action buttons. Dark tables scroll within their own panels where needed.

The interface follows the supplied TapeReader reference: a compact masthead, market strip with real-history sparklines, four context panels, scan controls, three ranked setup cards and The Watchtower. Every table uses the terminal's dark palette. The Streamlit version is pinned so deployments do not silently change frontend versions.

## Behavior preserved

The existing calculation engine, feeds, universe files, event checks, three-plan focus limit and live-entry gates are retained. The broader candidate view removes only the presentation cap of two names per sector. Research candidates are never treated as confirmed entries. Session JSON adds an optional `following` field; valid older backups restore into both the followed list and focus list.

Theme intraday requests are limited to already-loaded stocks in baskets with at least two observed members. Definitions alone never cause additional tickers to be added to the selected universe. Themes need at least three members and 70% basket coverage for a broad-coverage label; partial readings are explicitly averages of observed members.

The former Night Plan, Pre-open, Live Desk, Regime & Rotation, and Research screens are no longer navigation destinations. This rework does not add new Air Gap detection rules or data services. Legacy screenshots and release documents are retained under `docs/legacy` for historical reference only.

## Verify

```sh
python -m pytest -q
```

Deploy only this repository to its separate test Streamlit application using `app.py`. Do not replace the production scanner deployment.
