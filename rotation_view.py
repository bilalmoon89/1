"""Rotation page: theme baskets ranked by return, relative strength, breadth and pace."""
import pandas as pd
import streamlit as st
from crescent_engine import complete_daily
from rotation_engine import stock_metrics, theme_metrics, leader_table
from rotation_themes import THEMES, SECTOR_PROXIES
from rotation_cards import CSS, PERIODS, theme_panels, strip, group_returns, theme_table, leaders_view
from liquid_table import leaders_table
from terminal_view import table, e

BATCH=24
BENCHMARKS=('SPY','QQQ','IWM')


def _setup_labels(history,symbols):
    """TIGHT · 8 EMA / EXTENDED for the members of one theme (same rule as Liquid Uptrend)."""
    from liquid_uptrend import _strength
    from crescent_engine import normalise
    out={}
    for symbol in symbols:
        f=normalise(history.get(symbol))
        if len(f)>=60:out[symbol]=_strength(f,float(f.Close.iloc[-1]))['Setup']
    return out


def render_rotation_page(daily_loader,now):
    st.markdown(CSS,unsafe_allow_html=True)
    st.markdown('<div class="section-heading">Theme Rotation <span>Where money is moving · completed daily candles · equal-weight baskets</span></div>',unsafe_allow_html=True)
    left,mid,right=st.columns([2,1.2,1],vertical_alignment='bottom')
    period=left.radio('Period',list(PERIODS),index=2,horizontal=True,key='rot_period')
    view=mid.radio('View',['Cards','Table'],horizontal=True,key='rot_view')
    benchmark=right.selectbox('Compare against',BENCHMARKS,key='rot_benchmark')
    groups=st.multiselect('Market groups',sorted({t['group'] for t in THEMES}),key='rot_groups',placeholder='All groups')
    selected=[t for t in THEMES if not groups or t['group'] in groups]
    catalog={t['name']:t for t in selected}
    with st.expander('How to read this',expanded=False):
        st.caption('Each theme is an equal-weight basket. Return is the average of its members; RS is that return minus the benchmark; rising is the share of members that are up. A theme is ranked only with at least 3 members and 70% of them on the latest session.')
        st.caption('Leading: beating the benchmark over 5 and 10 sessions with most members rising. Heating: beating it over the last 2 sessions, most members rising and the pace picking up. Cooling: ahead over 10 sessions but behind over the last 2, or few members rising. Rank vs 10D shows how many places a theme moved between its 10-session and 2-session rank.')
    symbols=sorted({s for t in selected for s in t['symbols']}|set(SECTOR_PROXIES.values())|set(BENCHMARKS))
    if st.button('Load rotation',type='primary',width='stretch',key='rot_load'):
        st.session_state.rotation_job={'symbols':symbols,'done':0,'history':{},'failures':{},'active':True}
        st.session_state.pop('rotation_result',None)
    job=st.session_state.get('rotation_job')
    polling=bool(job and job.get('active'))
    st.fragment(run_every='2s' if polling else None)(_results)(daily_loader,now,selected,catalog,PERIODS[period],view,benchmark)


def _results(daily_loader,now,selected,catalog,horizon,view,benchmark):
    from datetime import datetime
    now=datetime.now(now.tzinfo)
    job=st.session_state.get('rotation_job')
    if not job:
        st.info(f'{len(selected)} themes ready. Select Load rotation; about 550 price histories load in a minute or two.');return
    if job['active']:
        if st.button('Stop',key='rot_stop'):
            job['active']=False;st.rerun()
        batch=tuple(job['symbols'][job['done']:job['done']+BATCH])
        with st.spinner(f"Loading {job['done']+1}–{job['done']+len(batch)} of {len(job['symbols'])}…"):
            try:raw,fail=daily_loader(batch)
            except Exception as exc:raw,fail={},dict.fromkeys(batch,str(exc)[:160])
        job['history'].update({s:complete_daily(f,now) for s,f in raw.items() if s in batch})
        job['failures'].update(fail)
        job['done']+=len(batch)
        if job['done']>=len(job['symbols']):
            job['active']=False;st.rerun()
        st.progress(job['done']/max(1,len(job['symbols'])),text=f"{job['done']} / {len(job['symbols'])} loaded");return
    history=job['history']
    if benchmark not in history:
        st.error(f'{benchmark} history is unavailable, so relative strength cannot be measured. Load rotation again.');return
    # Metrics are computed once per load and benchmark, not on every rerun.
    key=(benchmark,len(history))
    cached=st.session_state.get('rotation_result')
    if not cached or cached[0]!=key:
        stocks,asof=stock_metrics(history,benchmark)
        st.session_state.rotation_result=cached=(key,stocks,asof)
    _,stocks,asof=cached
    if stocks.empty or asof is None:
        st.error('Not enough benchmark history to rank themes.');return
    themes=theme_metrics(stocks,selected)
    ranked=int(themes['Rank eligible'].sum())
    counts=themes[themes['Rank eligible']].State.value_counts()
    summary=' · '.join(f'{name} <b>{int(counts.get(name,0))}</b>' for name in ('Leading','Leading + heating','Heating','Cooling','Lagging','Mixed') if counts.get(name,0))
    html=f'<div class="rot-status">Session <b>{asof.date()}</b> · <b>{ranked}</b> of {len(themes)} themes ranked · vs <b>{e(benchmark)}</b> · {summary}</div>'
    ok=stocks[stocks.Data.eq('OK')].set_index('Symbol')
    html+=strip('Sectors',[(name,ok[f'{horizon}D %'].get(symbol)) for name,symbol in SECTOR_PROXIES.items()])
    html+=strip('Groups',group_returns(themes,horizon))
    if view=='Cards':html+=theme_panels(themes,stocks,catalog,horizon)
    st.markdown(html,unsafe_allow_html=True)
    ranking=theme_table(themes,horizon)
    if view=='Table':st.markdown(leaders_table(ranking),unsafe_allow_html=True)
    else:
        with st.expander(f'All {len(ranking)} themes'):st.markdown(leaders_table(ranking),unsafe_allow_html=True)
    st.markdown('<div class="sub-heading">Explore a theme</div>',unsafe_allow_html=True)
    order=list(ranking.Theme)
    choice=st.selectbox('Theme',order,key='rot_theme',label_visibility='collapsed')
    if choice in catalog:
        theme=catalog[choice];members=list(dict.fromkeys(theme['symbols']))
        leaders=leader_table(stocks,members)
        labels=_setup_labels(history,members)
        if not leaders.empty:leaders['Setup']=leaders.Symbol.map(labels).fillna('')
        st.caption(f"{theme['group']} · {len(members)} members"+(f" · {theme['context']}" if theme.get('context') else ''))
        st.markdown(leaders_table(leaders_view(leaders)),unsafe_allow_html=True)
        st.caption('Leader score ranks liquid members by relative strength over 2, 5 and 10 sessions. Review is a description, not an entry signal. Check any name on the Ticker Check page.')
    st.download_button('Export rotation CSV',themes.drop(columns=[c for c in themes if c.startswith('Valid ')],errors='ignore').to_csv(index=False),file_name='Crescent_Theme_Rotation.csv',mime='text/csv')
    if job['failures']:
        with st.expander(f"Unavailable histories · {len(job['failures'])}"):
            st.markdown('<div class="wrap-table">'+table(pd.DataFrame([{'Symbol':k,'Reason':v} for k,v in job['failures'].items()]))+'</div>',unsafe_allow_html=True)
