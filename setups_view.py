"""VCP and Power Earnings Gap scanner page: batched loading, adjustable rules."""
import re
import pandas as pd
import streamlit as st
from crescent_engine import complete_daily
from setup_scanner import PRESETS, Tightness, VCPRules, PEGRules, scan, annotate
from terminal_view import table, e
from liquid_data import SETUP_TIERS, COMMODITIES, SINA_FUTURES, complete_asia_daily

BATCH=12
EARNINGS_CHECK_LIMIT=30


def _tightness_controls(preset_name):
    base=PRESETS[preset_name]
    with st.expander(f'Tight-candle rule · {preset_name} preset (adjustable)',expanded=False):
        st.caption('Accumulation footprint: small-range candles whose closes cluster on or just above the EMA while volume dries up.')
        a,b,c=st.columns(3)
        tight_days=a.number_input('Small-range days needed (of last 5)',1,5,base.tight_days,key=f'st_days_{preset_name}')
        range_ratio=b.number_input('Small = range below × 20D avg range',0.2,1.5,base.range_ratio,0.05,key=f'st_range_{preset_name}')
        spread=c.number_input('Last 3 closes within %',0.2,5.0,base.close_spread_pct,0.1,key=f'st_spread_{preset_name}')
        d,f,g=st.columns(3)
        ema_atr=d.number_input('Closes within N ATR of the EMA',0.25,3.0,base.ema_atr,0.05,key=f'st_ema_{preset_name}')
        below=f.number_input('Last close at most N ATR under the EMA',0.0,2.0,base.below_ema_atr,0.05,key=f'st_below_{preset_name}')
        vol=g.number_input('Volume below × 50D average',0.2,2.0,base.volume_ratio,0.05,key=f'st_vol_{preset_name}')
    return Tightness(tight_days=int(tight_days),range_ratio=range_ratio,close_spread_pct=spread,
        ema_atr=ema_atr,below_ema_atr=below,volume_ratio=vol)


def _rule_controls():
    with st.expander('VCP and PEG rules',expanded=False):
        st.markdown('**VCP** — stage-2 uptrend (price > 50 > 150 > 200 SMA, 200 SMA rising), within 25% of the 52-week high, 2–4 pullbacks each smaller than the last, final pullback tight, price just under the pivot.')
        a,b,c=st.columns(3)
        first=a.number_input('First pullback max %',10.0,60.0,35.0,1.0,key='vcp_first')
        last=b.number_input('Final pullback max %',3.0,25.0,12.0,0.5,key='vcp_last')
        below=c.number_input('Max % below pivot',1.0,20.0,8.0,0.5,key='vcp_below')
        st.markdown('**PEG (Power Earnings Gap)** — gap up on very heavy volume, closes strong, never undercuts the gap-day low, then tightens on the 8 or 21 EMA.')
        d,f,g=st.columns(3)
        gap=d.number_input('Gap at least %',2.0,30.0,5.0,0.5,key='peg_gap')
        mult=f.number_input('Gap volume × 50D average',1.5,10.0,2.5,0.25,key='peg_mult')
        look=g.number_input('Gap within last N sessions',5,120,40,5,key='peg_look')
    return (VCPRules(first_max_depth=first,last_max_depth=last,max_below_pivot_pct=below),
            PEGRules(gap_pct=gap,volume_mult=mult,lookback=int(look)))


LEAD=['Symbol','Name','Close','Trigger','Stop','Risk %']
SPECIFIC={'VCP':['Pullbacks','Contractions','Pivot','Vs pivot %','Base days','Base vol dry-up'],
          'PEG':['Gap date','Gap %','Gap volume x','Gap-day low','Days since gap','Earnings']}
TAIL=['Leadership','EMA','Vs EMA ATR','Tight days','Close spread %','Volume vs 50D','Day vol vs 20D %','RS 63D vs SPY pp','As of']


def _display(part):
    """Setup-specific column order, whole numbers shown without decimals."""
    if part.empty:return part
    setup=part['Setup'].iloc[0]
    part=part.dropna(axis=1,how='all')
    order=[c for c in LEAD+SPECIFIC.get(setup,[])+TAIL if c in part.columns]
    part=part[order].copy()
    if 'Leadership' in part and not part['Leadership'].astype(str).str.len().any():part=part.drop(columns='Leadership')
    if 'Name' in part and not part['Name'].astype(str).str.len().any():part=part.drop(columns='Name')
    for c in ('Contractions','Base days','Days since gap','Tight days'):
        if c in part:part[c]=part[c].astype('Int64')
    return part


STOCK_LIST='Stock list · 574'


def render_setups_page(daily_loader,universe_loader,earnings_loader,now,etf_names=None):
    st.markdown('<div class="section-heading">VCP &amp; Power Earnings Gap <span>Tight 8 EMA accumulation · completed daily candles only</span></div>',unsafe_allow_html=True)
    left,mid,right=st.columns([1.3,1.2,1],vertical_alignment='bottom')
    scope=left.selectbox('Universe',list(SETUP_TIERS)+[STOCK_LIST,'My list only'],key='su_scope')
    setups=mid.multiselect('Setups',['VCP','PEG'],default=['VCP','PEG'],key='su_setups')
    preset=right.selectbox('Tightness',list(PRESETS),index=0,key='su_preset')
    if scope in SETUP_TIERS:
        count={500:'the 500 most liquid',1500:'the 1,500 most liquid'}.get(SETUP_TIERS[scope],'all')
        timing={500:'about 3–4 minutes',1500:'about 7–10 minutes'}.get(SETUP_TIERS[scope],'10–15 minutes or more')
        st.caption(f'Scans {len(COMMODITIES)} commodities (Yahoo front-month futures, plus SHFE hot-rolled coil HC1! from Sina), the {len(etf_names or {})} ETFs in etfs.csv, and {count} US stocks above \\$10 with at least \\$20M average daily dollar volume. Stocks more than 3% under their 50-day average are skipped, since neither setup can match them. Expect {timing} on Yahoo; commodities and ETFs load first. For ETFs and commodities a PEG row is a power gap, not an earnings gap.')
    custom=st.text_input('My list / additional tickers',placeholder='e.g. NVDA, COHR, ANF',key='su_extra')
    tight=_tightness_controls(preset)
    vcp_rules,peg_rules=_rule_controls()
    st.caption('Candidates, not signals. Trigger = pivot (VCP) or recent tight-area high (PEG) + 0.03 ATR; stop = below the tight area / gap-day low. Earnings dates come from Yahoo and are labelled Confirmed / Not earnings / Unverified.')
    if st.button('Run setup scan',type='primary',width='stretch'):
        extras=[x.upper() for x in re.split(r'[\s,;]+',custom.strip()) if re.fullmatch(r'[A-Za-z][A-Za-z0-9.\-]{0,14}',x)]
        try:
            base,note=([],'') if scope=='My list only' else universe_loader(scope)
        except Exception as exc:
            st.error(f'Could not load the universe: {str(exc)[:160]}');return
        symbols=list(dict.fromkeys(['SPY']+extras+base))
        if len(symbols)<=1:st.warning('Add at least one ticker.');return
        st.session_state.setup_job={'symbols':symbols,'done':0,'history':{},'failures':{},'active':True,'scope':scope,'extras':extras,'note':note}
        st.session_state.pop('setup_earnings',None)
    job=st.session_state.get('setup_job')
    from datetime import datetime
    import scan_store
    from session_validity import completed_session
    expected=str(completed_session(datetime.now(now.tzinfo)))
    if scope!='My list only' and (job is None or (not job.get('active') and job.get('scope')!=scope)):
        # A scan of this tier finished earlier (in any tab) is reused until the next session closes.
        saved=scan_store.load('setups:'+scope,expected)
        if saved:
            st.session_state.setup_job=job=saved;st.session_state.pop('setup_earnings',None)
    polling=bool(job and job.get('active'))
    names=dict(etf_names or {});names.update(COMMODITIES)
    st.fragment(run_every='2s' if polling else None)(_results)(daily_loader,earnings_loader,now,setups,tight,vcp_rules,peg_rules,names,expected)


def _results(daily_loader,earnings_loader,now,setups,tight,vcp_rules,peg_rules,names=None,expected=''):
    import scan_store
    names=names or {}
    from datetime import datetime
    now=datetime.now(now.tzinfo)
    job=st.session_state.get('setup_job')
    if not job:
        st.info('Choose a scan and select Run setup scan. Core takes a few minutes, Medium and Full longer; matches appear while it runs.');return
    if job.get('note'):st.warning(job['note'])
    if job['active']:
        if st.button('Stop scan',key='setup_stop'):
            job['active']=False;st.rerun()
        batch=tuple(job['symbols'][job['done']:job['done']+BATCH])
        with st.spinner(f"Loading {job['done']+1}–{job['done']+len(batch)} of {len(job['symbols'])}…"):
            try:raw,fail=daily_loader(batch)
            except Exception as exc:raw,fail={},dict.fromkeys(batch,str(exc)[:160])
        job['history'].update({s:complete_asia_daily(f,now) if s in SINA_FUTURES else complete_daily(f,now) for s,f in raw.items() if s in batch})
        job['failures'].update(fail)
        job['done']+=len(batch)
        if job['done']>=len(job['symbols']):
            job['active']=False
            if expected and job.get('scope')!='My list only':scan_store.save('setups:'+job.get('scope',''),job,expected,now)
            st.rerun()
        st.progress(job['done']/max(1,len(job['symbols'])),text=f"{job['done']} / {len(job['symbols'])} loaded · {len(job['history'])} usable")
    history=job['history']
    spy=history.get('SPY')
    if spy is None and not job['active']:
        st.warning('SPY history unavailable: relative strength column is blank.')
    matches,reasons=scan(history,spy,tuple(setups),tight,vcp_rules,peg_rules,st.session_state.get('setup_earnings'))
    # Earnings check for PEG rows once the scan is finished (bounded, cached per ticker for a day).
    if not job['active'] and 'PEG' in setups and not matches.empty and st.session_state.get('setup_earnings') is None:
        pegs=[x for x in matches.loc[matches.Setup=='PEG','Symbol'] if x not in names][:EARNINGS_CHECK_LIMIT]
        found={}
        with st.spinner(f'Checking earnings dates for {len(pegs)} gap candidates…'):
            for s in pegs:
                dates=earnings_loader(s)
                if dates:found[s]=dates
        st.session_state.setup_earnings=found
        matches,reasons=scan(history,spy,tuple(setups),tight,vcp_rules,peg_rules,found)
    matches=annotate(matches,names)
    done_at=str(job.get('loaded_at',''))[11:16] or now.strftime('%H:%M')
    status='Scanning · partial results' if job['active'] else f"{job.get('scope','Scan')} · data through {scan_store.data_through(history) or 'n/a'} · loaded {done_at} ET"
    st.markdown(f'<div class="section-heading">Setups <span>{len(matches)} matches · {len(history)} histories · {e(status)}</span></div>',unsafe_allow_html=True)
    if matches.empty:
        st.info('No stock passes every rule in the loaded data. The rules have not been relaxed; try the Loose preset to see near-misses.')
    else:
        for name in ('VCP','PEG'):
            part=_display(matches[matches.Setup==name])
            if part.empty:continue
            label='VCP · volatility contraction' if name=='VCP' else 'PEG · power earnings gap'
            st.markdown(f'<div class="sub-heading">{label}<span>{len(part)}</span></div>',unsafe_allow_html=True)
            st.markdown(table(part),unsafe_allow_html=True)
        st.download_button('Export setups CSV',matches.to_csv(index=False),file_name='Crescent_VCP_PEG_Setups.csv',mime='text/csv')
    mine=[s for s in job.get('extras',[]) if s in reasons]
    if mine:
        with st.expander(f'Why your tickers did not match · {len(mine)}',expanded=True):
            st.markdown('<div class="wrap-table">'+table(pd.DataFrame([{'Symbol':s,'Reason':reasons[s]} for s in mine]))+'</div>',unsafe_allow_html=True)
    if job['failures']:
        with st.expander(f"Unavailable histories · {len(job['failures'])}"):
            st.markdown('<div class="wrap-table">'+table(pd.DataFrame([{'Symbol':k,'Reason':v} for k,v in job['failures'].items()]))+'</div>',unsafe_allow_html=True)
