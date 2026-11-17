"""Pure HTML for the market brief (no Streamlit)."""
from html import escape

CSS = '''<style>
.brief{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(0,1fr);gap:12px;margin:4px 0 12px}
.brief-col{border:1px solid #253244;border-radius:6px;background:#0E1622;min-width:0}
.brief-col h4{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin:0!important;padding:8px 11px!important;border-bottom:1px solid #253244;
  font:600 11.5px var(--sans,sans-serif)!important;letter-spacing:.08em;text-transform:uppercase;color:#D4A840!important}
.brief-col h4 small{font:400 11px var(--sans,sans-serif);letter-spacing:0;text-transform:none;color:#A9B6C6}
.brief-news{list-style:none;margin:0;padding:2px 0}
.brief-news li{display:grid;grid-template-columns:96px minmax(0,1fr);gap:8px;align-items:start;padding:6px 11px;border-bottom:1px solid #182333}
.brief-news li:last-child{border-bottom:0}
.brief-cat{font:600 9.5px var(--sans,sans-serif);letter-spacing:.06em;text-transform:uppercase;border-radius:3px;padding:3px 5px;text-align:center;margin-top:1px}
.brief-news a{font:500 13px/1.35 var(--sans,sans-serif);color:#F0EDE6!important;text-decoration:none!important}
.brief-news a:hover{color:#D4A840!important}
.brief-news small{display:block;margin-top:2px;font-size:11px;color:#A9B6C6}
.brief-tbl{width:100%;border-collapse:collapse;font-size:12px}
.brief-tbl td{padding:5px 9px;border-bottom:1px solid #182333;vertical-align:top;color:#DCE5F1}
.brief-tbl tr:last-child td{border-bottom:0}
.brief-tbl td.d{white-space:nowrap;color:#A9B6C6;font-family:var(--mono,monospace);font-size:11.5px;width:1%}
.brief-tbl td.n{text-align:right;white-space:nowrap;font-family:var(--mono,monospace);font-size:11.5px;color:#C9D3DF}
.brief-tbl b{color:#F0EDE6;font-weight:600}.brief-tbl small{color:#A9B6C6;font-size:11px}
.brief-tbl tr.today td{background:#1B1810}.brief-tbl tr.done td{opacity:.62}
.brief-tbl .sym{color:#D4A840;font-weight:700;font-family:var(--mono,monospace)}
.brief-empty{padding:10px 11px;font-size:12px;color:#A9B6C6}
.brief-foot{font-size:11px;color:#8F9EAF;margin:-6px 0 10px}
@media(max-width:900px){.brief{grid-template-columns:1fr}.brief-news li{grid-template-columns:1fr;gap:3px}.brief-cat{justify-self:start}}
</style>'''

CATEGORY_COLOURS = {'Fed & rates': ('#2B3E5C', '#9CC3F5'), 'Macro data': ('#2B3E5C', '#9CC3F5'),
    'Geopolitics': ('#4A2330', '#F6A3AE'), 'Trade & policy': ('#3A3020', '#E3C77E'), 'Markets': ('#173A30', '#8FE6C3'),
    'Energy': ('#3D2A17', '#F2B880'), 'Companies': ('#262F3D', '#C9D3DF'), 'Crypto': ('#2E2440', '#C9B3F2')}
FLAGS = {'US': 'US', 'EU': 'EU', 'GB': 'UK', 'JP': 'JP'}


def _age(hours):
    if hours is None:return ''
    return 'just now' if hours < 1 else f'{int(hours)}h ago' if hours < 24 else f'{int(hours // 24)}d ago'


def _money(v):
    try:v = float(v)
    except (TypeError, ValueError):return ''
    return f'${v / 1e12:.2f}T' if v >= 1e12 else f'${v / 1e9:.0f}B'


def _day(when, now):
    d = (when.date() - now.date()).days
    return 'Today' if d == 0 else 'Tomorrow' if d == 1 else when.strftime('%a %d %b')


def headlines_html(stories):
    if not stories:return '<div class="brief-empty">Headlines are unavailable right now.</div>'
    rows = []
    for s in stories:
        bg, fg = CATEGORY_COLOURS.get(s['category'], ('#262F3D', '#C9D3DF'))
        meta = ' · '.join(x for x in (s['source'], _age(s['age_hours']), f"{s['outlets']} outlets" if s['outlets'] > 1 else '') if x)
        rows.append(f'<li><span class="brief-cat" style="background:{bg};color:{fg}">{escape(s["category"])}</span>'
                    f'<div><a href="{escape(s["link"])}" target="_blank" rel="noopener noreferrer">{escape(s["title"])}</a>'
                    f'<small>{escape(meta)}</small></div></li>')
    return '<ul class="brief-news">' + ''.join(rows) + '</ul>'


def events_html(events, now):
    if not events:return '<div class="brief-empty">No major release in the next two weeks, or the calendar is unavailable.</div>'
    rows = []
    for ev in events:
        when = ev['when']
        time = 'All day' if when.hour == 0 and when.minute == 0 else when.strftime('%H:%M')
        if ev['released'] and ev['actual']:
            numbers = f'<b>{escape(ev["actual"])}</b> <small>vs {escape(ev["forecast"] or "—")}</small>'
        else:
            numbers = (f'<small>F</small> {escape(ev["forecast"])} ' if ev['forecast'] else '') + \
                      (f'<small>P</small> {escape(ev["previous"])}' if ev['previous'] else '')
        cls = 'done' if ev['released'] else 'today' if when.date() == now.date() else ''
        flag = '' if ev['country'] == 'US' else f'<small>{FLAGS.get(ev["country"], ev["country"])} · </small>'
        rows.append(f'<tr class="{cls}"><td class="d">{escape(_day(when, now))}<br>{time}</td>'
                    f'<td>{flag}<b>{escape(ev["label"])}</b><br><small>{escape(ev["indicator"])}</small></td><td class="n">{numbers}</td></tr>')
    return '<table class="brief-tbl"><tbody>' + ''.join(rows) + '</tbody></table>'


def earnings_html(earnings, now):
    if not earnings:return '<div class="brief-empty">No large-cap report in the next ten days, or earnings dates are unavailable.</div>'
    rows = []
    for r in earnings:
        cls = 'today' if r['when'].date() == now.date() else ''
        eps = f'<small>EPS est</small> {float(r["eps"]):.2f}' if r['eps'] is not None and r['eps'] == r['eps'] else ''
        rows.append(f'<tr class="{cls}"><td class="d">{escape(_day(r["when"], now))}<br>{escape(r["timing"] or "time n/a")}</td>'
                    f'<td><span class="sym">{escape(r["symbol"])}</span> <small>{escape(r["company"][:28])}</small></td>'
                    f'<td class="n">{_money(r["market_cap"])}<br>{eps}</td></tr>')
    return '<table class="brief-tbl"><tbody>' + ''.join(rows) + '</tbody></table>'


def brief_html(stories, events, earnings, now, notes=''):
    left = f'<div class="brief-col"><h4>Top headlines<small>Ranked by topic, outlets covering it and recency</small></h4>{headlines_html(stories)}</div>'
    right = (f'<div style="display:grid;gap:12px;align-content:start"><div class="brief-col"><h4>Key data<small>Next 2 weeks · ET</small></h4>{events_html(events, now)}</div>'
             f'<div class="brief-col"><h4>Earnings<small>Largest reporting · next 10 days</small></h4>{earnings_html(earnings, now)}</div></div>')
    foot = f'<div class="brief-foot">{escape(notes)}</div>' if notes else ''
    return CSS + '<div class="brief">' + left + right + '</div>' + foot
