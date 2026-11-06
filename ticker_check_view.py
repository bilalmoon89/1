"""Compact read-only presentation of ticker-check results."""
import pandas as pd
from terminal_view import e,table
from liquid_table import leaders_table
from ticker_check import number

CSS='''<style>
.tc-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:5px 0 8px}.tc-head b{font-size:18px}.tc-head small,.tc-note{color:#98aabd;font-size:12px;line-height:1.5}.tc-decision{border:1px solid #594b31;border-left:3px solid #9b793c;background:#1d1c18;border-radius:5px;padding:10px 12px;display:flex;gap:14px;align-items:center;margin-bottom:9px}.tc-decision b{font-size:14px;white-space:nowrap;color:#c2a366}.tc-decision span{font-size:12px;color:#b1bdcb}.tc-decision.no{border-left-color:#e77987;background:#251b24}.tc-decision.no b{color:#ef8b98}
.tc-grid{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:9px}.tc-box{background:#101821;border:1px solid #293744;border-radius:5px;overflow:hidden;min-width:0}.tc-title{display:flex;align-items:center;justify-content:space-between;gap:8px;background:#141e29;border-bottom:1px solid #293744;padding:8px 10px;font-size:13px;font-weight:700}.tc-title small{font-size:11px;color:#9aacc0;font-weight:400}.tc-body{padding:8px 10px}.tc-grid .table-scroll{max-height:none}.tc-grid .terminal-table td{padding:5px 6px}.tc-grid .terminal-table th{padding:8px 6px;font-size:10px}.tc-grid .terminal-table{font-size:12px!important}.tc-grid .table-scroll{border:0}.tc-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-bottom:9px}.tc-stat{line-height:1.3;background:#111c27;border:1px solid #293744;border-radius:5px;padding:8px 11px;min-width:0}.tc-stat small{display:block;font-size:11px;color:#96a8bb;margin-bottom:4px}.tc-stat b{font-size:14px;color:#d7e3ef}.tc-stat p{font-size:11px;color:#9badc0;margin:3px 0 0}.tc-values{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}.tc-values>div{padding:6px 0}.tc-values small{display:block;color:#9aacc0;font-size:11px}.tc-values b{display:block;font:600 16px monospace;color:#dce6f1;margin-top:4px}.tc-tag{display:inline-block;border-radius:3px;padding:3px 5px;font-size:11px;background:#243027;color:#74d5ac}.tc-tag.caution{background:#2a251c;color:#c0a064}.tc-tag.bad{background:#35232d;color:#f08a99}.tc-strip{display:flex;flex-wrap:wrap;gap:7px 16px;font-size:12px;color:#9aacbf;border-top:1px solid #283544;padding:8px 0 0;margin-top:6px}.tc-strip b{color:#d7e3ef}.tc-note{margin-top:6px}.st-key-ticker_lookup{padding:8px!important}.st-key-ticker_lookup [data-testid="stVerticalBlock"]{gap:0!important}
@media(max-width:900px){.tc-grid{grid-template-columns:1fr}.tc-decision{align-items:flex-start;flex-direction:column;gap:5px}}@media(max-width:600px){.tc-summary{grid-template-columns:1fr}.tc-values{grid-template-columns:repeat(2,minmax(0,1fr))}.tc-head{align-items:flex-start;flex-direction:column}.tc-decision b{white-space:normal}}
</style>'''


def tag(text):
    tone='bad' if any(v in text for v in ('NO GO','BELOW','CAUTION','INCOMPLETE')) else 'caution' if any(v in text for v in ('UNTESTED','UNKNOWN','NOT DETECTED')) else ''
    return f'<span class="tc-tag {tone}">{e(text)}</span>'


def box(title,meta,body):
    return f'<section class="tc-box"><div class="tc-title">{e(title)}<small>{e(meta)}</small></div><div class="tc-body">{body}</div></section>'


def multiple(value):
    n=number(value)
    return f'{n:.1f}×' if n is not None and n>0 else '—'


def dashboard(symbol,data,quarters,fund_state,tech,quote,combined,valuations):
    info=data['info'];stage=tech.get('stage',{});pattern=tech.get('pattern',{})
    head=f'<div class="tc-head"><b>{e(symbol)} <span class="muted">/ {e(info.get("shortName",symbol))}</span></b><small>Daily {e(tech.get("asof","unavailable"))} · Retrieved {e(data["retrieved"][11:19])} ET</small></div>'
    head+=f'<div class="tc-decision {"no" if combined.startswith("NO GO") else ""}"><b>{e(combined)}</b><span>{e(tech["reason"])}</span></div>'
    summary='<div class="tc-summary">'
    for label,value,detail in [(f'FUNDAMENTALS · {len(quarters)}/5 QUARTERS',fund_state,f'{len(quarters)}/5 reported quarters'),('STAGE ANALYSIS',stage.get('stage','UNKNOWN'),'Completed weekly · 30-week SMA'),('HIGH TIGHT FLAG','PREFERRED CANDIDATE' if pattern.get('found') else 'NOT DETECTED','Price + duration + volume checks')]:
        summary+=f'<div class="tc-stat" title="{e(detail)}"><small>{e(label)}</small><b>{e(value)}</b></div>'
    summary+='</div>'
    if quarters.empty:fund='<div class="tc-note">Quarterly statements unavailable.</div>'
    else:
        display=quarters.copy().round(2)
        for column in ('Revenue','Net income'):
            display[column]=display[column].map(lambda v:f'{float(v)/1e9:.2f}B' if number(v) is not None else '—')
        display=display.rename(columns={'Period end':'Quarter end','Operating margin %':'Op margin %','Revenue YoY %':'Rev YoY %','Diluted EPS':'EPS'})
        fund=leaders_table(display)
    fundamentals=box('Fundamentals · five quarters',f'{info.get("financialCurrency","Currency unverified")} · B = billion',fund)
    averages=tech['averages']
    if averages.empty:trend='<div class="tc-note">Insufficient completed price history.</div>'
    else:
        rows=''.join(f'<tr><td>{e(r["Average"].replace(" · completed weeks",""))}</td><td>{float(r["Value"]):.2f}</td><td>{tag(r["State"])}</td></tr>' if number(r['Value']) is not None else f'<tr><td>{e(r["Average"])}</td><td>—</td><td>{tag(r["State"])}</td></tr>' for _,r in averages.iterrows())
        trend='<div class="table-scroll"><table class="terminal-table"><thead><tr><th>Average</th><th>Level</th><th>Support</th></tr></thead><tbody>'+rows+'</tbody></table></div>'
    last=f'{tech["price"]:.2f}' if number(tech.get('price')) is not None else '—'
    trend+=f'<div class="tc-strip"><span>Last daily close <b>{last}</b></span><span>200 SMA = hard veto</span></div>'
    technical=box('Trend & support','Daily + completed weekly',trend)
    metrics='<div class="tc-values">'
    for label,key in [('P/E TTM','trailingPE'),('Forward P/E','forwardPE'),('P/S TTM','priceToSalesTrailing12Months'),('EV/EBITDA','enterpriseToEbitda')]:
        metrics+=f'<div><small>{label}</small><b>{multiple(info.get(key))}</b></div>'
    metrics+='</div>'
    if len(valuations)>=2:metrics+=f'<div class="tc-strip"><span>Year-end P/E mean <b>{valuations["P/E"].mean():.1f}×</b></span><span>Median <b>{valuations["P/E"].median():.1f}×</b></span><span>{len(valuations)} fiscal years</span></div>'
    else:metrics+='<div class="tc-note">Historical P/E reference unavailable.</div>'
    metrics+='<div class="tc-note">Annual snapshots, not a daily historical average.</div>'
    valuation=box('Valuation','Forward P/E = estimate',metrics)
    levels='<div class="tc-values">'
    for label,key in [('ENTRY','entry'),('STOP','stop'),('TARGET','target'),('REWARD / RISK','rr')]:
        value=number(tech.get(key));display=f'{value:.2f}'+('R' if key=='rr' else '') if value is not None else '—'
        levels+=f'<div><small>{label}</small><b>{display}</b></div>'
    levels+='</div><div class="tc-note">Conditional levels only · blank = not established. Fresh intraday confirmation required.</div>'
    plan=box('Trade plan','Structural invalidation · ≥2R required',levels)
    quote_html=(f'<b>TradingView {quote["price"]:.2f}</b> · SMA200 {quote["sma200"]:.2f} · {e(quote["feed"])} · {e(quote["updated"])}' if quote.get('valid') else e(quote['status']))
    return head+summary+'<div class="tc-grid">'+fundamentals+technical+valuation+plan+'</div>'+f'<div class="tc-note">{quote_html}</div>'
