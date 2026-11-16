"""Compact read-only presentation of ticker-check results."""
from terminal_view import e
from liquid_table import leaders_table
from ticker_check import number

CSS='''<style>
.tc-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:3px 0 5px}.tc-head b{font-size:18px}.tc-head small,.tc-note{color:#98aabd;font-size:12px;line-height:1.5}.tc-decision{border:1px solid #594b31;border-left:3px solid #B8922A;background:#1B1810;border-radius:5px;padding:7px 10px;display:flex;gap:14px;align-items:center;margin-bottom:9px}.tc-decision b{font-size:14px;white-space:nowrap;color:#D4A840}.tc-decision span{font-size:12px;color:#b1bdcb}.tc-decision.no{border-left-color:#e77987;background:#251b24}.tc-decision.no b{color:#ef8b98}
.tc-grid{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:9px}.tc-box{background:#101821;border:1px solid #293744;border-radius:5px;overflow:hidden;min-width:0}.tc-title{display:flex;align-items:center;justify-content:space-between;gap:8px;background:#141e29;border-bottom:1px solid #293744;padding:8px 10px;font-size:13px;font-weight:700}.tc-title small{font-size:11px;color:#9aacc0;font-weight:400}.tc-body{padding:5px 8px}.tc-grid .table-scroll{max-height:none}.tc-grid .terminal-table td{padding:4px 5px}.tc-grid .terminal-table th{padding:8px 6px;font-size:10px}.tc-grid .terminal-table{font-size:12px!important}.tc-grid .table-scroll{border:0}.tc-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-bottom:6px}.tc-stat{line-height:1.3;background:#111c27;border:1px solid #293744;border-radius:5px;padding:6px 9px;min-width:0}.tc-stat small{display:block;font-size:11px;color:#96a8bb;margin-bottom:4px}.tc-stat b{font-size:14px;color:#d7e3ef}.tc-stat p{font-size:11px;color:#9badc0;margin:3px 0 0}.tc-values{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}.tc-values>div{padding:6px 0}.tc-values small{display:block;color:#9aacc0;font-size:11px}.tc-values b{display:block;font:600 16px monospace;color:#dce6f1;margin-top:4px}.tc-tag{display:inline-block;border-radius:3px;padding:3px 5px;font-size:11px;background:#243027;color:#74d5ac}.tc-tag.caution{background:#2E2715;color:#E3C77E}.tc-tag.bad{background:#35232d;color:#f08a99}.tc-strip{display:flex;flex-wrap:wrap;gap:7px 16px;font-size:12px;color:#9aacbf;border-top:1px solid #283544;padding:8px 0 0;margin-top:6px}.tc-strip b{color:#d7e3ef}.tc-note{margin-top:6px}.st-key-ticker_lookup{padding:8px!important}.st-key-ticker_lookup [data-testid="stVerticalBlock"]{gap:0!important}
@media(max-width:900px){.tc-grid{grid-template-columns:1fr}.tc-decision{align-items:flex-start;flex-direction:column;gap:5px}}@media(max-width:600px){.tc-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.tc-values{grid-template-columns:repeat(2,minmax(0,1fr))}.tc-head{align-items:flex-start;flex-direction:column}.tc-decision b{white-space:normal}}
.terminal-header{min-height:48px;padding-bottom:9px;margin-bottom:5px}.block-container{padding-top:14px!important}[data-testid="stMainBlockContainer"]{padding-top:14px!important}.tc-title{padding:6px 8px}.tc-values>div{padding:3px 0}.tc-strip{padding-top:5px;margin-top:4px}.tc-summary small{font-size:10px}.tc-note{font-size:11px}
</style>'''


CSS+='''<style>
.tc-top{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin:2px 0 10px}
.tc-id b{font:600 30px/1 var(--serif,Georgia,serif);color:#F0EDE6;letter-spacing:.01em}
.tc-id span{display:block;margin-top:5px;font-size:13px;color:#C9D3DF}.tc-id small{display:block;margin-top:2px;font-size:11.5px;color:#A9B6C6}
.tc-price{text-align:right}.tc-price b{display:block;font:600 26px/1 var(--mono,monospace);color:#F0EDE6;font-variant-numeric:tabular-nums}
.tc-price small{display:block;margin-top:5px;font-size:11.5px;color:#A9B6C6}
.tc-verdict{display:grid;grid-template-columns:auto 1fr;gap:4px 16px;align-items:center;border:1px solid #5E4C25;border-left:4px solid #B8922A;background:#1B1810;border-radius:6px;padding:11px 14px;margin-bottom:10px}
.tc-verdict b{font:700 15px var(--sans,sans-serif);letter-spacing:.05em;color:#D4A840;white-space:nowrap}.tc-verdict span{font-size:13px;line-height:1.45;color:#D5DEE8}
.tc-verdict.no{border-color:#5a2f3a;border-left-color:#F47F8E;background:#22161d}.tc-verdict.no b{color:#F47F8E}
.tc-verdict.go{border-color:#23503f;border-left-color:#45D6A0;background:#10211d}.tc-verdict.go b{color:#45D6A0}
.tc-checks{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
.tc-chip{font:500 12px var(--sans,sans-serif);border-radius:20px;padding:5px 10px;border:1px solid #2C3A4C;background:#121C29;color:#B9C5D3;white-space:nowrap}
.tc-chip i{font-style:normal;font-weight:700;margin-right:5px}
.tc-chip.pass{border-color:#23503f;color:#8fe6c3}.tc-chip.fail{border-color:#5a2f3a;color:#f6a3ae}.tc-chip.warn{border-color:#5E4C25;color:#E3C77E}
.tc-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(128px,1fr));gap:0;background:#101925;border:1px solid #253244;border-radius:6px;overflow:hidden;margin-bottom:10px}
.tc-kpi{background:#101925;padding:9px 12px;min-width:0;border-right:1px solid #253244;border-bottom:1px solid #253244;margin:0 -1px -1px 0}.tc-kpi small{display:block;font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;color:#A9B6C6}
.tc-kpi b{display:block;margin-top:4px;font:600 17px var(--mono,monospace);color:#F0EDE6;font-variant-numeric:tabular-nums}
.tc-kpi span{display:block;margin-top:2px;font-size:11px;color:#A9B6C6}.tc-kpi.up b{color:#45D6A0}.tc-kpi.down b{color:#F47F8E}.tc-kpi.warn b{color:#E3C77E}
.tc-values b{font-size:18px}
.tc-plan-entry b{color:#D4A840}.tc-plan-stop b{color:#F47F8E}.tc-plan-target b{color:#45D6A0}
@media(max-width:680px){.tc-top{flex-direction:column;align-items:flex-start;gap:8px}.tc-price{text-align:left}.tc-verdict{grid-template-columns:1fr}.tc-verdict b{white-space:normal}.tc-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>'''

def tag(text):
    tone='bad' if any(v in text for v in ('NO GO','BELOW','CAUTION','INCOMPLETE')) else 'caution' if any(v in text for v in ('UNTESTED','UNKNOWN','NOT DETECTED')) else ''
    return f'<span class="tc-tag {tone}">{e(text)}</span>'


def box(title,meta,body):
    return f'<section class="tc-box"><div class="tc-title">{e(title)}<small>{e(meta)}</small></div><div class="tc-body">{body}</div></section>'


def multiple(value):
    n=number(value)
    return f'{n:.1f}×' if n is not None and n>0 else '—'


CHIP_MARK={'pass':'✓','fail':'✕','warn':'!','na':'·'}


def fmt(value,pattern='{:+.1f}%'):
    n=number(value)
    return pattern.format(n) if n is not None else '—'


def dollars(value):
    n=number(value)
    if n is None:return '—'
    return f'${n/1e9:.1f}B' if n>=1e9 else f'${n/1e6:.0f}M'


def kpi(label,value,tone='',sub=''):
    return f'<div class="tc-kpi {tone}"><small>{e(label)}</small><b>{e(value)}</b>'+(f'<span>{e(sub)}</span>' if sub else '')+'</div>'


def signed_tone(value):
    n=number(value)
    return '' if n is None else 'up' if n>=0 else 'down'


def dashboard(symbol,data,quarters,fund_state,tech,quote,combined,valuations,r40=None,extra=None):
    """One screen: identity and price, verdict, gate checklist, key numbers, then plan / trend / fundamentals / valuation."""
    r40=r40 or {'score':None,'status':'UNAVAILABLE','period':''}
    extra=extra or {}
    context=extra.get('context') or {};earnings=extra.get('earnings') or {}
    info=data['info'];averages=tech['averages']
    name=info.get('shortName') or info.get('longName') or symbol
    sector=' · '.join(str(x) for x in (info.get('sector'),info.get('industry')) if x)
    if quote.get('valid'):
        price=f'{quote["price"]:,.2f}';price_note=f'TradingView · {quote["feed"]} · {quote["updated"][11:19]} ET'
    else:
        price=f'{tech["price"]:,.2f}' if number(tech.get('price')) is not None else '—'
        price_note=f'Daily close {tech.get("asof","unavailable")} · live quote {str(quote.get("status","unavailable")).split(" · ")[0].lower()}'
    head=(f'<div class="tc-top"><div class="tc-id"><b>{e(symbol)}</b><span>{e(name)}</span>'+(f'<small>{e(sector)}</small>' if sector else '')
        +f'</div><div class="tc-price"><b>{e(price)}</b><small>{e(price_note)}</small></div></div>')
    tone='no' if combined.startswith('NO GO') else 'go' if combined.startswith('CONDITIONAL') else ''
    head+=f'<div class="tc-verdict {tone}"><b>{e(combined)}</b><span>{e(tech["reason"])}</span></div>'
    checks=''.join(f'<span class="tc-chip {state}" title="{e(detail)}"><i>{CHIP_MARK.get(state,"·")}</i>{e(label)}</span>' for label,state,detail in extra.get('checks') or [])
    if checks:head+=f'<div class="tc-checks">{checks}</div>'
    tiles=[]
    if context:
        tiles+=[kpi('vs 200 SMA',fmt(context.get('vs200')),signed_tone(context.get('vs200'))),
            kpi('Off 52W high',fmt(context.get('off_high')),'' if (number(context.get('off_high')) or -100)>=-25 else 'down'),
            kpi('RS 63D vs SPY',fmt(context.get('rs63'),'{:+.1f} pp'),signed_tone(context.get('rs63'))),
            kpi('vs 8 EMA',fmt(context.get('ext8'),'{:+.1f} ATR'),'warn' if (number(context.get('ext8')) or 0)>2.5 else ''),
            kpi('ATR 14',fmt(context.get('atr_pct'),'{:.1f}%'),'',f'ADR 20D {fmt(context.get("adr20"),"{:.1f}%")}'),
            kpi('Avg $ volume 50D',dollars(context.get('dollar_volume')))]
    if earnings.get('next'):
        days=earnings.get('days')
        tiles.append(kpi('Next earnings',earnings['next'],'warn' if days is not None and days<=7 else '',f'in {days} days' if days else 'today' if days==0 else ''))
    kpis='<div class="tc-kpis">'+''.join(tiles)+'</div>' if tiles else ''
    # Trade plan
    levels='<div class="tc-values">'
    for label,key,cls in [('ENTRY','entry','tc-plan-entry'),('STOP','stop','tc-plan-stop'),('TARGET','target','tc-plan-target'),('REWARD / RISK','rr','')]:
        value=number(tech.get(key));display=(f'{value:.2f}'+('R' if key=='rr' else '')) if value is not None else '—'
        levels+=f'<div class="{cls}"><small>{label}</small><b>{display}</b></div>'
    levels+='</div>'
    entry=number(tech.get('entry'));stop=number(tech.get('stop'))
    if entry and stop and entry>stop:
        levels+=f'<div class="tc-strip"><span>Risk per share <b>{entry-stop:.2f}</b> · <b>{(entry-stop)/entry*100:.1f}%</b></span>'+(f'<span>Basis <b>{e(extra["plan_source"])}</b></span>' if extra.get('plan_source') else '')+'</div>'
    levels+='<div class="tc-note">Conditional levels only · blank = not established. Fresh intraday confirmation required.</div>'
    plan=box('Trade plan','Structural invalidation · ≥2R required',levels)
    # Trend and support
    if averages.empty:trend='<div class="tc-note">Insufficient completed price history.</div>'
    else:
        rows=''.join(f'<tr><td>{e(r["Average"].replace(" · completed weeks",""))}</td><td>{float(r["Value"]):.2f}</td><td>{tag(r["State"])}</td></tr>' if number(r['Value']) is not None else f'<tr><td>{e(r["Average"])}</td><td>—</td><td>{tag(r["State"])}</td></tr>' for _,r in averages.iterrows())
        trend='<div class="table-scroll"><table class="terminal-table"><thead><tr><th>Average</th><th>Level</th><th>Support</th></tr></thead><tbody>'+rows+'</tbody></table></div>'
    last=f'{tech["price"]:.2f}' if number(tech.get('price')) is not None else '—'
    stage=tech.get('stage',{}).get('stage','UNKNOWN')
    trend+=f'<div class="tc-strip"><span>Last daily close <b>{last}</b></span><span>Stage <b>{e(stage)}</b></span><span>200 SMA = hard veto</span></div>'
    technical=box('Trend & support','Daily + completed weekly',trend)
    # Fundamentals
    if fund_state=='NOT APPLICABLE':fund='<div class="tc-note">Not a reporting company (ETF, future or index): fundamentals are not applicable. The technical review decides.</div>'
    elif quarters.empty:fund='<div class="tc-note">Quarterly statements unavailable.</div>'
    else:
        display=quarters.drop(columns=['Net income'],errors='ignore').copy().round(2)
        display['Revenue']=display['Revenue'].map(lambda v:'—' if number(v) is None else f'{float(v)/1e9:.2f}B' if abs(float(v))>=1e9 else f'{float(v)/1e6:.0f}M' if abs(float(v))>=1e6 else f'{float(v):,.0f}')
        display=display.rename(columns={'Period end':'Quarter end','Operating margin %':'Op margin %','Revenue YoY %':'Rev YoY %','Diluted EPS':'EPS'})
        order=[c for c in ('Quarter end','Revenue','Rev YoY %','EPS','EPS YoY %','Gross margin %','Op margin %','Net margin %') if c in display.columns]
        fund=leaders_table(display[order])
    rule=f'{r40["score"]:.1f} · {r40["status"]}' if r40.get('score') is not None else 'UNAVAILABLE'
    if fund_state!='NOT APPLICABLE':
        fund+=f'<div class="tc-strip"><span>Review <b>{e(fund_state)}</b></span><span title="Latest TTM revenue growth + matching TTM FCF margin; software/SaaS reference">RULE OF 40 · TTM {e(r40["period"])} <b>{e(rule)}</b></span></div>'
    fundamentals=box('Fundamentals · five quarters',f'{info.get("financialCurrency","Currency unverified")} · B/M = billions/millions · YoY {int(quarters["Revenue YoY %"].notna().sum()) if not quarters.empty else 0}/5',fund)
    # Valuation
    metrics='<div class="tc-values">'
    for label,key in [('P/E TTM','trailingPE'),('Forward P/E','forwardPE'),('P/S TTM','priceToSalesTrailing12Months'),('EV/EBITDA','enterpriseToEbitda')]:
        metrics+=f'<div><small>{label}</small><b>{multiple(info.get(key))}</b></div>'
    metrics+='</div>'
    if len(valuations)>=2:metrics+=f'<div class="tc-strip"><span>Year-end P/E mean <b>{valuations["P/E"].mean():.1f}×</b></span><span>Median <b>{valuations["P/E"].median():.1f}×</b></span><span>{len(valuations)} fiscal years</span></div><div class="tc-note">Annual snapshots, not a daily historical average.</div>'
    else:metrics+='<div class="tc-note">Historical P/E reference unavailable.</div>'
    valuation=box('Valuation','Forward P/E = estimate',metrics)
    return head+kpis+'<div class="tc-grid">'+plan+technical+fundamentals+valuation+'</div>'
