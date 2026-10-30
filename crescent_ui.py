"""Crescent original mark geometry and restrained institutional Streamlit UI."""
import base64
import streamlit as st

# Same SVG geometry as the recovered Crescent branding component.
LOGO_SVG='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" fill="none"><circle cx="24" cy="24" r="22" stroke="#B8922A" stroke-width="1" opacity="0.6"/><path d="M24 8C16.268 8 10 14.268 10 22s6.268 14 14 14c1.96 0 3.82-.39 5.52-1.09C26.04 32.56 23 28.56 23 24s3.04-8.56 6.52-10.91A13.93 13.93 0 0 0 24 8z" fill="#B8922A"/></svg>'
CSS='''<style>
:root{--cx-bg:#0E1D30;--cx-panel:#162941;--cx-line:#2e455d;--cx-text:#eef3f6;--cx-muted:#a3b5c9;--cx-gold:#d3ab55;--cx-green:#58c4a2;--cx-red:#eb8790}
:root{color-scheme:dark}
[data-testid="stHeader"]{background:#0e1d30!important;color:#eef3f6!important}
[data-testid="stToolbar"] button,[data-testid="stSidebarCollapseButton"] button,[data-testid="stExpandSidebarButton"] button{color:#eef3f6!important;background:#162941!important}
[data-testid="stWidgetLabel"],[data-testid="stWidgetLabel"] *,
[data-testid="stRadio"] label,[data-testid="stRadio"] label *,
[data-testid="stCheckbox"] label,[data-testid="stCheckbox"] label *,
[data-testid="stMarkdownContainer"]{color:#eef3f6!important}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] *{color:#bdcbdc!important}
[data-testid="stAlert"]{background:#1b3049!important;border:1px solid #65819e!important;color:#f2f6fb!important}
[data-testid="stAlert"] [data-testid="stMarkdownContainer"],
[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p{color:#f2f6fb!important}
[data-testid="stAlert"] svg{fill:currentColor!important;color:#f0ca75!important}
[data-baseweb="select"]>div,[data-baseweb="select"]>div>div{background:#1b3049!important;color:#f2f6fb!important}
[data-baseweb="select"] svg{fill:#f2f6fb!important}
[data-baseweb="popover"],[data-baseweb="menu"],[role="listbox"],[role="option"]{background:#1b3049!important;color:#f2f6fb!important}
[role="option"]:hover,[role="option"][aria-selected="true"]{background:#344c65!important;color:#ffffff!important}
[data-baseweb="input"],[data-baseweb="base-input"],[data-baseweb="textarea"]{background:#1b3049!important;color:#f2f6fb!important}
input::placeholder,textarea::placeholder{color:#b8c9db!important;opacity:1!important}
[data-testid="stFileUploaderDropzone"]{background:#162941!important;color:#eef3f6!important;border-color:#65819e!important}
[data-testid="stExpander"] summary,[data-testid="stTabs"] button{color:#eef3f6!important}
[data-testid="stTooltipIcon"] svg{fill:#bdcbdc!important}
a{color:#f0ca75}a:hover{color:#ffe3a0}
.stApp,[data-testid="stAppViewContainer"]{background:var(--cx-bg);color:var(--cx-text)}
[data-testid="stSidebar"]{background:#101f34;border-right:1px solid var(--cx-line)}
.block-container{padding-top:1.8rem!important;max-width:1370px}
@media(max-width:740px){.block-container{padding:1rem .72rem 3rem!important}}
h1,h2,h3{letter-spacing:-.016em;color:var(--cx-text)!important}
h1{font-weight:650!important;font-size:1.7rem!important}
h2{font-size:1.3rem!important}h3{font-size:1.08rem!important}
.cx-header{display:flex;align-items:center;gap:13px;border-bottom:1px solid #4d4c46;padding:8px 0 14px;margin-bottom:16px}
.cx-header img{width:38px;height:38px}.cx-word{font:600 26px/1.1 Georgia,serif;color:#f1e9da}.cx-sub{font:600 10px/1.6 Arial,sans-serif;color:#d3ab55;letter-spacing:.2em;text-transform:uppercase;margin-top:3px}
.cx-kicker{font-size:11px;color:#d3ab55;letter-spacing:.2em;font-weight:700;text-transform:uppercase;margin:4px 0 6px}
.cx-hero{padding:15px 18px;background:linear-gradient(110deg,#1d354f,#14273e);border:1px solid #34506a;border-radius:12px;margin:8px 0 14px}
.cx-hero b{font-size:17px}.cx-muted{font-size:12px;color:var(--cx-muted)}
.cx-call{border-left:3px solid var(--cx-gold);background:#1b2d42;padding:12px 14px;margin:9px 0;border-radius:0 9px 9px 0;font-size:14px;line-height:1.55}
.cx-plan{background:#162a43;border:1px solid #314965;border-radius:11px;padding:15px;margin:8px 0}
.cx-plan-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:7px}
.cx-plan-title{font-size:22px;font-weight:750;letter-spacing:-.02em}.cx-detail{font-size:13px;color:#c4d1df;margin:6px 0;line-height:1.5}
.cx-small{font-size:11px;color:#aabccc;letter-spacing:.03em}
.cx-status{font:700 10px Arial,sans-serif;letter-spacing:.08em;padding:5px 8px;border-radius:5px;border:1px solid #5c6f83;color:#e9e4d2;white-space:nowrap}
.cx-status-ARMED{color:#d4b46a;border-color:#8d7239}.cx-status-READY{color:#81dfb8;border-color:#43966a}.cx-status-BLOCKED,.cx-status-INVALID{color:#f0a2a8;border-color:#9f5a64}.cx-status-EXTENDED,.cx-status-STALE{color:#b4c4d7;border-color:#52677f}
[data-testid="stMetric"]{border:1px solid #31465d;padding:10px;border-radius:9px;background:#172b42}
[data-testid="stMetricLabel"],[data-testid="stMetricLabel"] *{color:#b9c7d7!important}
[data-testid="stMetricValue"],[data-testid="stMetricValue"] *{color:#f0e9dc!important}
[data-testid="stDataFrame"]{border:1px solid #304961;border-radius:10px;overflow:hidden}
/* Keep every action readable at rest, including secondary and download buttons. */
:is(.stButton,.stDownloadButton,.stLinkButton,.stFormSubmitButton) :is(button,a),
button:is([kind="primary"],[kind="secondary"],[data-testid^="stBaseButton-"]){background:#d3ab55!important;color:#0d2032!important;border:1px solid #e3bf73!important;font-weight:700!important;opacity:1!important}
:is(.stButton,.stDownloadButton,.stLinkButton,.stFormSubmitButton) :is(button,a) *,
button:is([kind="primary"],[kind="secondary"],[data-testid^="stBaseButton-"]) *{color:inherit!important}
:is(.stButton,.stDownloadButton,.stLinkButton,.stFormSubmitButton) :is(button,a):hover,
button:is([kind="primary"],[kind="secondary"],[data-testid^="stBaseButton-"]):hover{background:#e7c477!important;color:#0d2032!important;border-color:#f0d89c!important}
:is(.stButton,.stDownloadButton,.stLinkButton,.stFormSubmitButton) :is(button,a):focus-visible,
button:is([kind="primary"],[kind="secondary"],[data-testid^="stBaseButton-"]):focus-visible{outline:3px solid #f4deb0!important;outline-offset:3px!important}
:is(.stButton,.stDownloadButton,.stLinkButton,.stFormSubmitButton) :is(button,a):disabled,
button:is([kind="primary"],[kind="secondary"],[data-testid^="stBaseButton-"]):disabled{background:#776844!important;color:#ffffff!important;border-color:#ad9563!important;opacity:1!important;cursor:not-allowed!important}
[data-baseweb="select"]>div,input,textarea{background:#1b3049!important;color:#f2f6fb!important}
[data-testid="stTabs"] [aria-selected="true"]{color:#d3ab55!important}
[data-testid="stExpander"]{border-color:#304961!important}
.cx-divider{border-top:1px solid #31465c;margin:15px 0}
</style>'''


def brand(label='Decision & Execution Desk'):
    st.markdown(CSS,unsafe_allow_html=True)
    logo='data:image/svg+xml;base64,'+base64.b64encode(LOGO_SVG.encode()).decode()
    st.markdown(f'<div class="cx-header"><img alt="Crescent Insights mark" src="{logo}"><div><div class="cx-word">Crescent Insights</div><div class="cx-sub">{label}</div></div></div>',unsafe_allow_html=True)


def status_html(name):
    from html import escape
    label=str(name)[:36]
    klass=label if label in {'ARMED','READY','WATCH','BLOCKED','INVALID','EXTENDED','STALE'} else 'WATCH'
    return f'<span class="cx-status cx-status-{klass}">{escape(label)}</span>'


def card(plan,helper=''):
    """Concise research card. Escapes all untrusted text."""
    from html import escape
    from crescent_engine import money
    p=plan.to_dict() if hasattr(plan,'to_dict') else plan
    e=lambda x:escape(str(x),quote=True)
    direction=e(p['direction']);symbol=e(p['symbol']);setup=e(p['setup'])
    target=money(p.get('target'))
    if_clause=f"IF a completed 10m candle confirms {direction.lower()} beyond <b>{money(p['trigger'])}</b>, with VWAP alignment."
    return f'''<div class="cx-plan"><div class="cx-plan-head"><div><span class="cx-plan-title">{symbol}</span> &nbsp;<span class="cx-small">{e(p.get('sector',''))}</span></div>{status_html(p['status'])}</div>
<div class="cx-small">{setup} · {direction} · {e(p['asof'])} close · {e(p.get('source',''))}</div>
<div class="cx-detail">{e(p['reason'])}</div>
<div class="cx-detail"><b>IF:</b> {if_clause}</div>
<div class="cx-detail"><b>WRONG:</b> {money(p['stop'])} &nbsp; <b>NEXT:</b> {target} &nbsp; <b>R:R:</b> {e(p.get('rr') or 'Unverified')}</div>
<div class="cx-detail"><b>NOW:</b> {e(helper or p['blocker'])}</div></div>'''
