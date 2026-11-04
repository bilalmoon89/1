"""Dedicated liquid-uptrend page using the user's standard ALL preset."""
import pandas as pd
import streamlit as st
from crescent_engine import complete_daily
from crescent_feeds import symbols_from_file
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
        st.caption('Dollar volume = mean(close × volume) over 50 sessions. ADR N = (mean high N − mean low N) ÷ latest close × 100. Pharma exclusion uses Yahoo industry classification, including diagnostics/research; unverified industries are held out while this exclusion is enabled.')
    run=st.button('Run Liquid Uptrend',type='primary',use_container_width=True)
    initial=not st.session_state.get('liquid_started',False)
    if run or initial:
        st.session_state.liquid_started=True
        symbols=universe_loader(scope)
        stocks=symbols_from_file('stocks.csv')
        with st.spinner(f'Checking liquidity and trend · {scope}…'):
            try:
                raw,fail=daily_loader(tuple(symbols))
                history={s:complete_daily(f,now) for s,f in raw.items() if s in stocks}
                st.session_state.liquid_history=history
                st.session_state.liquid_scope=scope
                st.session_state.liquid_failures=fail
                st.session_state.liquid_updated=now.isoformat(timespec='seconds')
            except Exception as exc:st.error(f'Liquid scan feed unavailable: {type(exc).__name__}: {str(exc)[:160]}')
    history=st.session_state.get('liquid_history',{})
    if st.session_state.get('liquid_scope')!=scope:
        st.info('Run the scan to load the selected universe.');return
    matches,unavailable=screen_history(history,LiquidFilters(volume,dollar,sma200,sma50,adr1,adr20))
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
