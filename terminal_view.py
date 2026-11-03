"""Dense, dark terminal presentation. Values come only from supplied market frames."""
from html import escape
import math
import pandas as pd
from crescent_engine import snapshot, money, SECTORS

def e(value):
    return escape(str(value), quote=True)

def num(value, suffix=''):
    try:
        return f'{float(value):+.2f}{suffix}' if math.isfinite(float(value)) else '—'
    except (TypeError, ValueError):
        return '—'

def tone(value):
    try:return 'up' if float(value)>0 else 'down' if float(value)<0 else 'muted'
    except (TypeError, ValueError):return 'muted'

def table(frame):
    if frame is None or frame.empty:return '<div class="empty">No verified rows available.</div>'
    heads=''.join(f'<th>{e(x)}</th>' for x in frame.columns)
    rows=''.join('<tr>'+''.join(f'<td>{e("—" if pd.isna(x) else x)}</td>' for x in row)+'</tr>' for row in frame.itertuples(index=False,name=None))
    return f'<div class="table-scroll"><table class="terminal-table"><thead><tr>{heads}</tr></thead><tbody>{rows}</tbody></table></div>'

def spark(frame, color, label="Last 32 completed daily closes"):
    if frame is None or frame.empty:return '<span class="no-series">NO HISTORY</span>'
    values=frame.Close.tail(32).astype(float).tolist()
    low,high=min(values),max(values)
    points=' '.join(f'{i*120/max(1,len(values)-1):.1f},{32-(x-low)*26/max(high-low,.00001):.1f}' for i,x in enumerate(values))
    return f'<svg class="spark" viewBox="0 0 124 38" aria-label="{e(label)}"><polyline points="{points}" fill="none" stroke="{color}" stroke-width="1.5"/></svg>'

def panel(title, body, meta=''):
    return f'<section class="terminal-panel"><div class="panel-head"><b><span class="grip">⠿</span> {e(title)}</b><span>{e(meta)}</span></div><div class="panel-body">{body}</div></section>'

def header(updated=None):
    return f'<div class="terminal-header"><div class="terminal-brand"><span class="moon">☾</span><div><strong>CRESCENT <span>TRADE TERMINAL</span><em>BETA</em></strong><small>MARKET INTELLIGENCE / AIR GAP RESEARCH</small></div></div><div class="header-meta"><span class="source-pill">● Yahoo Finance</span><span>5m intraday · provider delay</span><span class="build-pill">CTT 7.3</span></div></div>'

def overview(snap, plans, frozen, intraday=None):
    intraday=intraday or {}
    intra=intraday.get("rows",pd.DataFrame())
    ctx=snap['context'];frames=snap['frames'];posture=ctx.get('posture','UNKNOWN')
    asof=snap.get('asof') or 'Not loaded'
    market=intra[intra.Symbol.isin(['SPY','QQQ','IWM'])] if not intra.empty else pd.DataFrame()
    covered=market[market['Vs VWAP %'].notna()] if not market.empty else pd.DataFrame()
    above=int((covered['Vs VWAP %']>0).sum()) if not covered.empty else 0
    state=intraday.get('status','UNAVAILABLE')
    description=f'{above}/{len(covered)} benchmark ETFs above session VWAP. Sector leadership is ranked versus SPY today.' if len(covered) else 'Intraday benchmark history unavailable. No daily readings are substituted.'
    bar=intraday.get('asof') or 'Unavailable'
    regime=f'<div class="regime-strip"><span class="pill amber">INTRADAY · {e(state)}</span><div><b>{e(description)}</b><small>Completed 5-minute bar · {e(bar)} · Yahoo provider delay · 60-second refresh.</small></div><span class="strip-right">SESSION CONTEXT</span></div>'
    quotes=[]
    for symbol in ['^VIX','SPY','QQQ','IWM']:
        matches=intra[intra.Symbol==symbol] if not intra.empty else pd.DataFrame()
        r=matches.iloc[0] if not matches.empty else None
        change=r['Today %'] if r is not None else None
        last=(f'{r["Last"]:.2f}' if symbol=='^VIX' else money(r['Last'])) if r is not None else '—'
        trend=('ABOVE VWAP' if r['Vs VWAP %']>0 else 'BELOW VWAP') if r is not None and pd.notna(r['Vs VWAP %']) else 'NO DATA'
        if symbol=='^VIX' and r is not None:trend='ELEVATED' if r['Last']>20 else 'NORMAL'
        state=intraday.get('status','UNAVAILABLE')
        if state!='CURRENT':trend=state
        quote_tone=('down' if change and change>0 else 'up') if symbol=='^VIX' and r is not None else tone(change)
        quotes.append(f'<div class="quote"><div><b>{e("VIX" if symbol=="^VIX" else symbol)}</b> <span class="pill {quote_tone}">{trend}</span><strong>{last}</strong></div><div class="quote-change {quote_tone}">{num(change,"%")}<small>vs previous close</small></div>{spark(intraday.get("frames",{}).get(symbol),"#37ca94" if quote_tone=="up" else "#ed6e7c","Completed 5-minute RTH closes")}</div>')
    sector=intra[intra.Symbol.isin(SECTORS)].sort_values('Vs SPY pp',ascending=False) if not intra.empty else pd.DataFrame()
    rows=[]
    if not sector.empty:
        for _,r in sector.iterrows():
            vwap='Above' if r['Vs VWAP %']>0 else 'Below' if pd.notna(r['Vs VWAP %']) else '—'
            rows.append(f'<tr><td><b>{e(r["Symbol"])}</b> <span class="muted">{e(r["Name"])}</span></td><td class="{tone(r["Today %"])}">{num(r["Today %"],"%")}</td><td class="{tone(r["Vs SPY pp"])}">{num(r["Vs SPY pp"])}</td><td class="{tone(r["Vs VWAP %"])}">{vwap}</td></tr>')
    sectors='<table class="terminal-table"><thead><tr><th>SECTOR</th><th>TODAY %</th><th>VS SPY pp</th><th>VWAP</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>' if rows else '<div class="empty">Intraday sector data unavailable.<br>Daily performance is not substituted.</div>'
    forming=[p for p in plans if p.status in ('ARMED','WATCH')][:3]
    setups=''.join(f'<div class="forming"><b class="{ "up" if p.direction=="LONG" else "down"}">{e(p.direction)} {e(p.symbol)}</b><span class="tiny-state">{e(p.status)}</span><p>{e(p.setup)}</p><div>Trigger <b>{money(p.trigger)}</b><br>Invalidation <b>{money(p.stop)}</b><br>Target <b>{money(p.target)}</b></div></div>' for p in forming) or '<div class="empty">No forming setups from loaded history.<br>Run a scan to assess candidates.</div>'
    status=f'<span class="pill amber">{e(posture)}</span><p>{e(ctx.get("reason","No benchmark coverage."))}</p><div class="status-line">Daily close <b>{e(asof)}</b></div><div class="status-line">Coverage <b>{snap.get("loaded",0)} instruments</b></div><div class="status-line">Entry confirmation <b>On request</b></div><div class="micro-note">Daily regime is not a live cloud reading. Research scores are not win probabilities.</div>'
    rotations=''
    stamp=intraday.get('asof') or 'Unavailable'
    label=intraday.get('status','UNAVAILABLE')
    if not sector.empty and pd.notna(sector.iloc[0]['Vs SPY pp']):
        lead=sector.iloc[0]
        rotations=f'<div class="rotation-lead"><small>SESSION RELATIVE LEADER / {e(label)}</small><h3>{e(lead["Name"])}</h3><b class="{tone(lead["Vs SPY pp"])}">{e(lead["Symbol"])} · {num(lead["Vs SPY pp"])} pp vs SPY today</b></div><div class="sector-chips">'+''.join(f'<span>{e(r["Symbol"])} <b class="{tone(r["Vs SPY pp"])}">{num(r["Vs SPY pp"])}</b></span>' for _,r in sector.iterrows())+'</div>'
    else:rotations='<div class="empty">Rotation requires comparable intraday SPY and sector bars.</div>'
    rotations+=f'<div class="micro-note">Completed bar close: {e(stamp)}<br>Yahoo 5m · {e(label)} · Refresh every 60s</div>'
    return regime+'<div class="quote-strip">'+''.join(quotes)+'</div><div class="context-grid">'+panel('Sectors · intraday',sectors,label)+panel('Setups forming',setups,f'{len(forming)} heads-up')+panel('Daily backdrop',status,'Daily structure')+panel('Sector rotation',rotations,'Today vs SPY')+'</div>'


def opportunity(plan, rank, frames):
    p=plan.to_dict() if hasattr(plan,'to_dict') else plan
    m=snapshot(frames[p['symbol']]) if p['symbol'] in frames else None
    last=money(m['price']) if m else '—'
    direction='up' if p['direction']=='LONG' else 'down'
    return f'<article class="opportunity {direction}"><div class="op-head"><span class="rank">#{rank}</span><b>{e(p["symbol"])}</b><span class="pill {direction}">{e(p["direction"])}</span><span class="op-state">{e(p["status"])}</span></div><div class="price-line">Close <b>{last}</b><span>→</span> Target <b>{money(p.get("target"))}</b></div><div class="setup-chip">{e(p["setup"])}</div><p>{e(p["reason"])}</p><div class="level-grid"><div><small>TRIGGER</small><b>{money(p["trigger"])}</b></div><div><small>INVALIDATION</small><b>{money(p["stop"])}</b></div><div><small>PLANNED R:R</small><b>{e(p.get("rr") or "—")}</b></div></div><div class="op-footer">{e(p["blocker"])}</div></article>'

CSS='''
<style>
:root{color-scheme:dark;--bg:#080d14;--panel:#101821;--line:#26313d;--muted:#8493a5;--gold:#d8b76b;--green:#43d29e;--red:#f27888}
.stApp,[data-testid="stAppViewContainer"]{background:var(--bg)!important;color:#dde4ed!important}
[data-testid="stHeader"]{display:none!important}[data-testid="stSidebar"]{display:none!important}
.block-container{max-width:1920px!important;padding:22px 20px 48px!important}
[data-testid="stMainBlockContainer"]{padding-top:22px!important}
[data-testid="stVerticalBlock"]{gap:.55rem!important}
body,p,button,input,label,select{font-family:Arial,Helvetica,sans-serif!important}
h1,h2,h3{color:#e6edf6!important;font-family:Arial,Helvetica,sans-serif!important;letter-spacing:0!important}
h3{font-size:15px!important;padding:5px 0!important}p{font-size:12px;line-height:1.5}
.terminal-header{display:flex;align-items:center;justify-content:space-between;gap:15px;border-bottom:1px solid #7c6637;padding:0 0 15px;margin-bottom:12px;min-height:64px}
.terminal-brand{display:flex;align-items:center;gap:10px;min-width:0}.moon{color:var(--gold);border:1px solid #5b4d30;border-radius:50%;font:32px Georgia;padding:0 8px}
.terminal-brand strong{font-size:21px;letter-spacing:.035em;display:block;line-height:1.5;white-space:normal}.terminal-brand strong span{font-weight:400;color:#becad9}.terminal-brand em{font-size:9px;letter-spacing:.12em;font-style:normal;color:var(--gold);border:1px solid #5c4d30;border-radius:3px;padding:3px 5px;margin-left:9px;vertical-align:middle}
.terminal-brand small{display:block;color:var(--muted);font-size:8px;letter-spacing:.22em}.header-meta{display:flex;align-items:center;gap:16px;color:#8795a8;font:10px monospace;white-space:nowrap}.source-pill{color:#43d29e;border:1px solid #244c40;border-radius:20px;padding:5px 9px}.build-pill{color:var(--gold)}
.regime-strip{display:flex;gap:12px;align-items:center;background:#111a24;border:1px solid var(--line);border-left:2px solid var(--gold);border-radius:5px;padding:11px 13px;margin-bottom:10px;font-size:11px}.regime-strip b{font-size:11px;font-weight:500}.regime-strip small{display:block;color:var(--muted);font-size:9px;margin-top:4px}.strip-right{margin-left:auto;color:#778496;font-size:8px;white-space:nowrap;letter-spacing:.12em}
.pill{display:inline-block;border-radius:3px;background:#19212c;font-size:8px;font-weight:700;padding:3px 6px;white-space:nowrap}.pill.amber{color:#e9c975;background:#3a311c}.pill.up{background:#133429;color:#53dba7}.pill.down{background:#3a2029;color:#fb8391}
.quote-strip{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line);border-radius:5px;margin-bottom:10px;background:#0e151e}.quote{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:10px 15px;border-right:1px solid #222d39;min-width:0}.quote:last-child{border:0}.quote b{font:700 10px monospace}.quote strong{display:block;font:700 17px monospace;margin-top:5px}.quote-change{font:10px monospace}.quote-change small{display:block;color:var(--muted);font:8px Arial;margin-top:4px}.spark{width:110px;max-width:35%;height:36px}.no-series{color:#657589;font:8px monospace}
.context-grid{display:grid;grid-template-columns:1.45fr .95fr 1fr 1fr;gap:9px;margin-bottom:4px}.terminal-panel{background:var(--panel);border:1px solid var(--line);border-bottom:1px solid #6d5730;border-radius:5px;min-width:0;overflow:hidden}.panel-head{padding:9px 10px;background:#141e29;border-bottom:1px solid #2a3543;display:flex;justify-content:space-between;gap:5px;font-size:10px}.panel-head b{font-weight:600}.panel-head span{color:var(--muted);font-size:8px}.grip{color:#6d798a;margin-right:5px}.panel-body{padding:9px 10px;height:224px;overflow:auto;font-size:10px;line-height:1.5}.panel-body p{font-size:10px;line-height:1.55;margin:9px 0}.empty{padding:22px 7px;color:#8191a5;font-size:11px;line-height:1.8;text-align:center}.muted{color:var(--muted)}.up{color:var(--green)}.down{color:var(--red)}
.terminal-table{border-collapse:collapse;width:100%;color:#ced7e3;background:#101821;font:10px Arial!important}.terminal-table th{text-align:left;background:#141e29;color:#8293a7;font:8px monospace;letter-spacing:.04em;padding:8px 7px;border-bottom:1px solid #2b3848;white-space:nowrap}.terminal-table td{padding:7px;border-bottom:1px solid #202b38;white-space:nowrap}.terminal-table tr:hover td{background:#172431}.terminal-table td .muted{font-size:8px}.table-scroll{overflow:auto;max-height:420px;border:1px solid var(--line);border-radius:4px}.tiny-state{font-size:8px;color:#abbace}.forming{border:1px solid #285447;border-radius:4px;padding:9px;margin-bottom:7px;background:#0e1c20;font:10px monospace}.forming>.tiny-state{float:right}.forming p{margin:4px 0!important}.forming div{font-size:9px;color:#9daebd}.forming div b{color:#dce6ef}
.status-line{border-top:1px solid #25303d;padding:7px 0;color:#91a0b3;font-size:9px;display:flex;justify-content:space-between;gap:8px}.status-line b{color:#c5d1df;font-weight:400}.micro-note{font-size:9px;color:#718298;line-height:1.6;margin-top:8px}.rotation-lead{border-left:2px solid #4bc99b;background:#101f24;padding:9px;margin-bottom:14px}.rotation-lead small{font-size:7px;color:#8496a8;letter-spacing:.07em}.rotation-lead h3{font-size:15px!important;margin:2px 0!important}.rotation-lead b{font-size:9px}.sector-chips{display:grid;grid-template-columns:repeat(3,1fr);gap:5px}.sector-chips>span{font:8px monospace;background:#17222e;border:1px solid #283746;padding:4px;border-radius:3px}
.section-heading{display:flex;align-items:center;justify-content:space-between;padding:9px 11px;background:#121c27;border:1px solid var(--line);border-radius:4px;margin:8px 0;color:#e0e8f1;font-size:11px;font-weight:600}.section-heading span{font-size:9px;color:#8698ac;font-weight:400}
.opportunity{background:#101821;border:1px solid var(--line);border-left:2px solid var(--green);border-radius:5px;padding:13px;min-height:215px;color:#cbd6e4}.opportunity.down{border-left-color:var(--red)}.op-head{display:flex;align-items:center;gap:7px}.op-head>b{font:700 18px monospace;color:#f3f6fc}.rank{color:#8495a9;font:10px monospace}.op-state{margin-left:auto;font:8px monospace;color:#c0b080}.price-line{font-size:10px;color:#95a6ba;margin:12px 0 8px}.price-line b{color:#e7edf5}.price-line span{margin:0 9px}.setup-chip{font-size:8px;display:inline-block;background:#1d2938;border:1px solid #304155;border-radius:3px;padding:3px 6px;color:#9db5cd}.opportunity p{font-size:10px;line-height:1.65;margin:10px 0;min-height:32px}.level-grid{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid #263440;padding-top:10px;gap:8px}.level-grid small{font-size:7px;color:#8597ac;display:block;letter-spacing:.07em}.level-grid b{font:11px monospace;color:#dbe6f4;display:block;margin-top:4px}.op-footer{font-size:9px;color:#a5b3c4;border-top:1px solid #263440;margin-top:10px;padding-top:8px;line-height:1.5}.terminal-foot{color:#63758b;font:9px monospace;border-top:1px solid var(--line);padding:14px 0;margin-top:10px}
[data-testid="stWidgetLabel"] p{font-size:9px!important;color:#8798ad!important;text-transform:uppercase;letter-spacing:.05em}input,[data-baseweb="select"]>div{background:#111d2a!important;color:#dae5f2!important;border-color:#2b3a4b!important;font-size:11px!important}
[data-testid="stButton"] button,[data-testid="stDownloadButton"] button{background:#172332!important;border:1px solid #344252!important;color:#cbd7e7!important;border-radius:4px!important;font-size:11px!important;min-height:32px!important;padding:4px 12px!important}
[data-testid="stButton"] button[kind="primary"]{background:#c5a45c!important;border-color:#ddc58c!important;color:#0c141e!important}
[data-testid="stButton"] button:disabled{opacity:.4!important}.stButton p{font-size:11px!important}
[data-testid="stExpander"]{background:#101821!important;border:1px solid #26313d!important;border-radius:4px!important}[data-testid="stExpander"] summary p{font-size:11px!important} [data-testid="stAlert"]{background:#17222e!important;color:#c9d7e6!important;border:1px solid #334555!important} [data-testid="stCaptionContainer"] p{font-size:10px!important;color:#8798ab!important}
[data-testid="stDataFrame"]{background:#101821!important}footer{display:none!important}
@media(max-width:1100px){.context-grid{grid-template-columns:1.3fr 1fr}.header-meta{gap:8px}.header-meta>span:nth-child(2){display:none}.quote{padding:10px}.terminal-brand strong{font-size:18px}}
@media(max-width:680px){.block-container{padding:16px 10px 35px!important}.terminal-header{align-items:flex-start}.terminal-brand strong{font-size:14px}.terminal-brand strong span{display:block}.terminal-brand small{font-size:6px;letter-spacing:.08em}.header-meta{font-size:8px;display:block}.header-meta>span{display:block;margin-bottom:5px}.quote-strip{grid-template-columns:repeat(2,1fr)}.quote{border-bottom:1px solid var(--line)}.context-grid{grid-template-columns:1fr}.panel-body{height:auto;max-height:270px;min-height:140px}.strip-right{display:none}.regime-strip{align-items:flex-start}.regime-strip>.pill{font-size:7px}.quote strong{font-size:14px}}
/* Readability pass: no critical trading values below 12px. */
:root{--muted:#a5b3c5}
.panel-head{font-size:13px;padding:11px 12px}.panel-head span{font-size:11px}.panel-body{height:290px;font-size:13px;padding:12px}.panel-body p{font-size:13px;line-height:1.6}
.terminal-table{font-size:13px!important}.terminal-table th{font-size:11px;padding:10px 7px}.terminal-table td{padding:9px 7px}.terminal-table td .muted{font-size:11px;display:block;white-space:normal}.tiny-state{font-size:11px}
.forming{font-size:13px;padding:11px}.forming div{font-size:12px}.status-line{font-size:12px}.micro-note{font-size:11px;color:#a5b3c5}.empty{font-size:13px}
.regime-strip b{font-size:13px}.regime-strip small{font-size:11px}.pill{font-size:10px}.quote b{font-size:13px}.quote strong{font-size:21px}.quote-change{font-size:13px}.quote-change small{font-size:10px}
.rotation-lead small{font-size:10px}.rotation-lead b{font-size:12px}.sector-chips>span{font-size:11px}.sector-chips{grid-template-columns:repeat(2,1fr)}
.section-heading{font-size:14px;padding:11px 12px}.section-heading span{font-size:11px}.opportunity{min-height:265px}.opportunity p{font-size:13px;line-height:1.65}.price-line{font-size:13px}.setup-chip{font-size:11px}.op-state,.rank{font-size:11px}.op-head>b{font-size:21px}.level-grid small{font-size:10px}.level-grid b{font-size:14px}.op-footer{font-size:12px}.terminal-foot{font-size:11px}
[data-testid="stWidgetLabel"] p{font-size:12px!important}input,[data-baseweb="select"]>div{font-size:14px!important}[data-testid="stButton"] button{min-height:40px!important;font-size:13px!important}.stButton p{font-size:13px!important}[data-testid="stExpander"] summary p{font-size:13px!important}[data-testid="stCaptionContainer"] p{font-size:12px!important}
@media(min-width:1101px) and (max-width:1500px){.context-grid{grid-template-columns:1.35fr 1fr}.panel-body{height:280px}}
@media(max-width:680px){.terminal-header{flex-wrap:wrap}.terminal-brand strong{font-size:18px}.terminal-brand small{font-size:10px;letter-spacing:.04em}.header-meta{display:flex;flex-wrap:wrap;font-size:11px}.terminal-brand em{font-size:10px}.terminal-header .moon{font-size:30px}.regime-strip{flex-direction:column}.regime-strip b{font-size:13px}.regime-strip small{font-size:12px}.regime-strip>.pill{font-size:10px}.quote{padding:12px 9px;flex-wrap:wrap;gap:5px}.quote strong{font-size:20px}.quote b{font-size:12px}.quote-change{font-size:12px}.spark{max-width:100%;width:100%;height:30px}.panel-body{height:auto;max-height:380px;min-height:0}.terminal-table{font-size:12px!important}.terminal-table th{font-size:10px;white-space:normal}.terminal-table td{padding:9px 5px}.terminal-table td:first-child{max-width:120px}.section-heading{align-items:flex-start;gap:8px;flex-direction:column}.opportunity{min-height:0}.op-head{flex-wrap:wrap}.level-grid b{font-size:15px}[data-testid="stButton"] button{min-height:44px!important}input{font-size:16px!important}}
</style>
'''
