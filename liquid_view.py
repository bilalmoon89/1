"""Dedicated liquid-uptrend page using the user's standard ALL preset."""
import pandas as pd
import streamlit as st
from crescent_engine import complete_daily
from liquid_uptrend import LiquidFilters, screen_history, apply_exclusions
from terminal_view import table, e


DEFAULTS={'lu_volume':1_000_000.0,'lu_dollar':100_000_000.0,'lu_200':.01,'lu_50':.01,'lu_adr1':3.0,'lu_adr20':3.0,
    'lu_pharma':True,'lu_excluded_tickers':'','lu_excluded_industries':''}


def reset_preset():
    st.session_state.update(DEFAULTS)


def render_liquid_page(daily_loader,industry_loader,universe_loader,now):
    st.markdown('<div class="section-heading">Liquid Uptrend <span>Completed daily candles · ALL conditions must pass</span></div>',unsafe_allow_html=True)
    standard=all(st.session_state.get(key,value)==value for key,value in DEFAULTS.items())
    badge='STANDARD PRESET' if standard else 'CUSTOM FILTERS'
    summary='20D volume &gt; 1M · 50D dollar volume &gt; $100M · above SMA200 and SMA50 · ADR 1D and 20D &gt; 3%' if standard else 'All six technical checks and selected exclusions apply. Restore the standard preset to reset.'
    st.markdown(f'<div class="preset-banner"><b>{badge}</b><span>{summary}</span></div>',unsafe_allow_html=True)
    for key,value in DEFAULTS.items():
        if key not in st.session_state:st.session_state[key]=value
    left,right=st.columns([3,1],vertical_alignment='bottom')
    scope=left.selectbox('Liquid scan universe',['Balanced 60','Balanced 120','Full 574'],key='lu_scope')
    right.button('Restore standard preset',on_click=reset_preset,use_container_width=True)
    with st.expander('Filters / exclusions · standard preset',expanded=True):
        first=st.columns(3)
        volume=first[0].number_input('Average volume 20D >',min_value=0.0,step=100_000.0,key='lu_volume',format='%.0f')
        dollar=first[1].number_input('Average $ volume 50D >',min_value=0.0,step=10_000_000.0,key='lu_dollar',format='%.0f')
        sma200=first[2].number_input('Price vs SMA200 % >',min_value=0.0,step=.01,key='lu_200',format='%.2f')
        second=st.columns(3)
        sma50=second[0].number_input('Price vs SMA50 % >',min_value=0.0,step=.01,key='lu_50',format='%.2f')
        adr1=second[1].number_input('ADR 1D % >',min_value=0.0,step=.1,key='lu_adr1',format='%.2f')
        adr20=second[2].number_input('ADR 20D % >',min_value=0.0,step=.1,key='lu_adr20',format='%.2f')
        exclude_pharma=st.checkbox('Exclude Pharmaceuticals, Biotechnology & Life Sciences',key='lu_pharma')
        one,two=st.columns(2)
        excluded=one.text_input('Exclude tickers',placeholder='e.g. ABC, XYZ',key='lu_excluded_tickers')
        keywords=two.text_input('Exclude other industries · keywords',placeholder='e.g. banks, insurance',key='lu_excluded_industries')
        st.caption('Dollar volume = mean(close × volume) over 50 sessions. ADR N = (mean high N − mean low N) ÷ latest close × 100. Industry classification uses a bounded TradingView request, including diagnostics/research where identified; unverified industries are held out while this exclusion is enabled.')
    run=st.button('Run Liquid Uptrend',type='primary',use_container_width=True)
    if run:
        symbols=list(dict.fromkeys(universe_loader(scope)))
        st.session_state.liquid_job={'scope':scope,'symbols':symbols,'done':0,'history':{},'failures':{},'active':True}
    scan_results(daily_loader,industry_loader,scope,now,
        LiquidFilters(volume,dollar,sma200,sma50,adr1,adr20),exclude_pharma,excluded,keywords)


@st.fragment(run_every='2s')
def scan_results(daily_loader,industry_loader,scope,now,filters,exclude_pharma,excluded,keywords):
    job=st.session_state.get('liquid_job')
    if job and job['scope']!=scope:job['active']=False
    if job and job['active']:
        if st.button('Stop scan',key='liquid_stop'):job['active']=False
        else:
            batch=tuple(job['symbols'][job['done']:job['done']+12])
            with st.spinner(f"Checking stocks {job['done']+1}–{job['done']+len(batch)}…"):
                try:raw,fail=daily_loader(batch)
                except Exception as exc:raw,fail={},dict.fromkeys(batch,str(exc)[:160])
            job['history'].update({s:complete_daily(f,now) for s,f in raw.items() if s in batch})
            job['failures'].update(fail)
            job['done']+=len(batch)
            if job['done']>=len(job['symbols']):
                job['active']=False
                if job['history']:
                    st.session_state.liquid_history=job['history']
                    st.session_state.liquid_scope=scope
                    st.session_state.liquid_failures=job['failures']
                    st.session_state.liquid_updated=now.isoformat(timespec='seconds')
        st.progress(job['done']/max(1,len(job['symbols'])),text=f"{job['done']} / {len(job['symbols'])} stocks checked · {len(job['history'])} available")
    if job and job['scope']==scope and job['failures']:
        st.warning(f"{len(job['failures'])} histories unavailable. Coverage is incomplete; unavailable stocks are not treated as failed setups.")
    if job and not job['active'] and not job['history']:
        st.error('The scan received no usable histories. Retry the scan; the last successful results have been retained.')
    history=st.session_state.get('liquid_history',{})
    if st.session_state.get('liquid_scope')!=scope:
        st.info('Select Run Liquid Uptrend to scan. The page loads without waiting for market-data connections. Results appear when the scan completes.');return
    if job and job['active']:st.caption('Scan in progress. Showing the last completed results below.')
    matches,unavailable=screen_history(history,filters)
    if not matches.empty:
        try:industries=industry_loader(tuple(matches.Symbol))
        except Exception:industries={}
        result,excluded_rows=apply_exclusions(matches,industries,exclude_pharma,
            [x.strip().upper() for x in excluded.split(',') if x.strip()],keywords.split(','))
    else:result=pd.DataFrame();excluded_rows=pd.DataFrame()
    st.markdown(f'<div class="section-heading">Liquid uptrends <span>{len(result)} matches · {len(history)} stock histories · {e(scope)} · {e(st.session_state.get("liquid_updated",""))}</span></div>',unsafe_allow_html=True)
    if result.empty:st.info('No stocks pass every selected condition and exclusion in this universe. The preset has not been relaxed.')
    else:
        pretty=result.copy()
        pretty['Avg volume 20D']=pretty['Avg volume 20D'].map(lambda x:f'{x/1_000_000:.2f}M')
        pretty['Avg $ volume 50D']=pretty['Avg $ volume 50D'].map(lambda x:f'${x/1_000_000:.1f}M')
        st.markdown(table(pretty),unsafe_allow_html=True)
        st.download_button('Export liquid matches CSV',result.to_csv(index=False),file_name='Crescent_Liquid_Uptrend.csv',mime='text/csv')
    if not excluded_rows.empty:
        with st.expander(f'Excluded after technical checks · {len(excluded_rows)}'):
            st.markdown(table(excluded_rows),unsafe_allow_html=True)
    if unavailable or st.session_state.get('liquid_failures'):
        with st.expander('Data coverage / unavailable histories'):
            problems={**st.session_state.get('liquid_failures',{}),**unavailable}
            st.markdown(table(pd.DataFrame([{'Symbol':s,'Reason':v} for s,v in problems.items()])),unsafe_allow_html=True)
