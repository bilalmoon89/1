# Useful features from the earlier Crescent Scanner

Production files were inspected as references only. This terminal remains a separate application and does not import or modify the production app.

## Included in this update

- **Theme lifecycle and participation**: adapted the earlier Theme Intelligence approach: SPY-relative returns, participation, comparable dates, and explicit minimum-member/coverage rules. Daily lifecycle and current-session rotation are displayed separately.
- **Broader discovery, smaller focus**: the terminal now exposes more existing candidates and supports 12 followed setups while preserving three focused plans and all entry gates.
- **Same-universe reuse**: theme intraday requests use only already-loaded members. No increase to the default 60-stock selection or the underlying universe files.

## Best additions next

| Feature | Earlier source | Terminal use |
| --- | --- | --- |
| Smart shortlist | `smart_scan.py`: daily prescreen then detailed intraday checks | Prioritize followed names, leaders and near-trigger candidates for deeper refreshes, without downloading every interval for every stock. |
| Weekly leadership and compression | Weekly Leaders, Weekly 8 Compression and Daily VCP | Add compact higher-timeframe context badges to setup cards using existing history. Keep these distinct from intraday confirmation. |
| Confluence explanation | Crescent Confluence and the weekly/daily structure labels | Show which independent conditions agree, which are missing, and why a candidate remains WATCH. Avoid presenting counts as win probabilities. |
| Changes since the last scan | Daily Snapshot exports and coverage metadata | Highlight newly appearing setups, deterioration and invalidations, with source timestamps and missing-data flags. |

These are proposed follow-ons, not implemented signals. The terminal does not recreate the previous tab collection.
