"""Crescent V7 — independent Streamlit Decision & Execution Desk.
This does not import, deploy to or mutate the original Crescent Scanner.
Research/paper-planning only; no broker connection, no automatic trading.
"""
from __future__ import annotations
import io
import json
from datetime import datetime,time,timedelta
from html import escape
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

from crescent_engine import (ET,SECTORS,BENCHMARKS,CROSS_ASSETS,DEFAULT_WATCH,ETF_TRADE_CANDIDATES,LEVERAGED_ETFS,Plan,
    complete_daily,normalise,snapshot,regime,make_plans,rank_plans,live_check,
    money,finite,mock_regime_note,preopen_assessment)
from crescent_feeds import (symbols_from_file,seed_universe,tv_leadership,
    yahoo_daily,yahoo_five_minute,generate_demo,read_events,risk_events,news_rss)
from crescent_ui import brand,card
from crescent_charts import candles
from rotation_themes import THEMES
from cloud_engine import bar_session_resample,scan_symbol

st.set_page_config(page_title='Crescent Trade Terminal — BETA',page_icon='🌙',
                   layout='wide',initial_sidebar_state='expanded')
NOW=lambda:datetime.now(ET)


@st.cache_data(ttl=1200,show_spinner=False)
def cached_daily(symbols_tuple):
    return yahoo_daily(symbols_tuple,period='1y')


@st.cache_data(ttl=105,show_spinner=False)
def cached_intraday(symbol,extended=False):
    return yahoo_five_minute(symbol,days='10d',extended=extended)


@st.cache_data(ttl=900,show_spinner=False)
def cached_headlines(query):
    return news_rss(query)


@st.cache_data(show_spinner=False)
def demo_pack():
    return generate_demo()


def init_state():
    defaults={'data_mode':'Demo — simulated','market_snapshot':None,'failure':{},
        'plans':[],'frozen':{},'journal':[],'positions':{},'view':'The Watchtower',
        'last_stop':None,'events':pd.DataFrame(),'news':[], 'live_result':{},
        'last_refresh':None,'manual_event_block':False,'pins':', '.join(DEFAULT_WATCH),
        'source_caption':'','universe_caption':'','scan_errors':[],'include_etfs':True}
    for k,v in defaults.items():
        if k not in st.session_state:st.session_state[k]=v
    if st.session_state['market_snapshot'] is None:
        frames,_=demo_pack()
        install_snapshot(frames,'SIMULATED research candles — not market prices', {})


def all_symbols(pins,mode,breadth,with_tv):
    sectors=symbols_from_file('stocks.csv')
    pinlist=[s.strip().upper() for s in pins.replace('\n',',').split(',') if s.strip()]
    lim={'Balanced 60':60,'Balanced 120':120,'Full 574':9999}[breadth]
    if mode=='Demo — simulated':
        frames,stockmap=demo_pack()
        return list(frames),stockmap,'Synthetic research sample — no market data',[]
    if breadth=='Full 574':
        selection=list(sectors)
        explanation='Full original 574-stock file; may take several minutes and hit Yahoo rate limits.'
    else:
        selection=seed_universe(sectors,pinlist,per_sector=12 if breadth=='Balanced 120' else 6,limit=lim)
        explanation='Sector-balanced subset of original stock universe (not a full-market leadership scan).'
    warnings=[]
    if with_tv:
        try:
            discovered,note=tv_leadership(limit=120)
            if discovered:
                # Priority pins + TV leaders + sector-balanced fallback; never technology-only focus.
                selection=list(dict.fromkeys(pinlist+discovered+selection))[:lim]
                explanation='TradingView public screener discovery (non-official API), plus balanced fallback.'
            else:warnings.append(note)
        except Exception as exc:
            warnings.append(f'TradingView screener unavailable: {type(exc).__name__}: {str(exc)[:120]}. Using sector-balanced fallback.')
    mandatory=list(BENCHMARKS)+list(SECTORS)+list(CROSS_ASSETS)
    if st.session_state.get('include_etfs',True):mandatory+=list(ETF_TRADE_CANDIDATES)
    return list(dict.fromkeys(selection+mandatory)),sectors,explanation,warnings


def install_snapshot(frames,source,fail):
    now=NOW()
    # Demo is intentionally frozen to a past date: never appear live.
    effective=datetime(2026,10,30,17,0,tzinfo=ET) if source.startswith('SIMULATED') else now
    daily={s:complete_daily(f,effective) for s,f in frames.items() if f is not None and len(f)}
    context=regime(daily,effective)
    universe=symbols_from_file('stocks.csv')
    etfs=pd.read_csv('etfs.csv').fillna('')
    etf_map=dict(zip(etfs.Symbol.astype(str),etfs.Sector.astype(str)))
    etf_map.update({'XBI':'Health Care','IHI':'Health Care','KRE':'Financials','XRT':'Consumer Discretionary',
       'SMH':'Information Technology','GDX':'Materials','GLD':'Materials','TLT':'Bonds','IBIT':'Crypto'})
    spy=snapshot(daily.get('SPY',pd.DataFrame()))
    plans=[];metrics=[]
    sector_rs={}
    sf=context['sectors']
    if not sf.empty:
        sector_rs=dict(zip(sf.Symbol,sf['Vs SPY 21D pp']))
    proxies={'Information Technology':'XLK','Technology':'XLK','Health Care':'XLV','Healthcare':'XLV',
        'Consumer Staples':'XLP','Utilities':'XLU','Energy':'XLE','Financials':'XLF',
        'Industrials':'XLI','Materials':'XLB','Consumer Discretionary':'XLY',
        'Communication Services':'XLC','Real Estate':'XLRE','Biotech':'XLV',
        'Semiconductors':'XLK','Precious Metals':'XLB','Healthcare':'XLV'}
    for symbol,f in daily.items():
        if symbol in SECTORS or symbol in BENCHMARKS or symbol in CROSS_ASSETS:continue
        sector=universe.get(symbol)
        if sector is None and symbol in ETF_TRADE_CANDIDATES:sector=etf_map.get(symbol,'Unknown')
        if sector is None:continue
        m=snapshot(f)
        if m and spy and m['asof']==spy['asof']:
            metrics.append({'Symbol':symbol,'Sector':sector,'Price':round(m['price'],2),
                '5D %':m['r5'],'21D %':m['r21'],'RS 21D pp':m['r21']-spy['r21'],
                'ATR14':round(m['atr'],2),'Dollar volume 20D':m['dvol'],
                '21EMA':round(m['ema21'],2),'Trend':'UP' if m['trend_up'] else 'DOWN' if m['trend_down'] else 'MIXED',
                'As of':m['asof']})
        candidate_plans=make_plans(symbol,f,spy,sector,sector_rs.get(proxies.get(sector)),
                    context['posture'],now=effective,source=source)
        if symbol in LEVERAGED_ETFS:
            for p in candidate_plans:
                p.status='WATCH';p.blocker='Leveraged ETF: independent volatility and leverage review required.'
        plans.extend(candidate_plans)
    st.session_state.market_snapshot={'frames':daily,'context':context,'metrics':pd.DataFrame(metrics),
        'source':source,'asof':context['asof'],'updated_at':now.isoformat(),
        'attempted':len(frames)+len(fail),'loaded':len(daily),
        'comparable':sum(1 for f in daily.values() if (snapshot(f) and snapshot(f)['asof']==context['asof'])),
        'fail':fail}
    st.session_state.plans=rank_plans(plans)
    st.session_state.failure=fail
    st.session_state.live_result={}
    st.session_state.source_caption=source
    st.session_state.last_refresh=now.isoformat()


def get_plans():return st.session_state.get('plans',[])


def percentfmt(x):return f'{x:+.1f}%' if finite(x) else '—'


def draw_topbanner(snap):
    ctx=snap['context'];sim='SIMULATED • NOT LIVE' if 'SIMULATED' in snap['source'] else 'YAHOO BETA • DELAYED / UNVERIFIED'
    st.markdown('<div class="cx-kicker">Market context · Sector-neutral research</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="cx-hero"><b>{escape(str(ctx["posture"]))}</b> &nbsp; | &nbsp; {escape(str(ctx["rotation"]))}'
                f'<div class="cx-muted">{escape(ctx["reason"])}<br>Data: {escape(sim)} · Completed through {escape(str(ctx["asof"] or "unknown"))}</div></div>',unsafe_allow_html=True)
    if 'SIMULATED' in snap['source']:
        st.warning('DEMO MODE: All prices, historical candles, sectors and plans are simulated for UI testing. Do not trade from them.')
        st.caption('To use Yahoo research: open Streamlit’s sidebar (top-left) → select Yahoo Finance — beta → Run overnight research.')
    elif ctx['posture']=='UNKNOWN':st.error('Market benchmark coverage inadequate — no regime permission is available.')


def plans_frame(plans):
    return pd.DataFrame([{
        'Symbol':p.symbol,'Sector':p.sector,'Setup':p.setup,'Side':p.direction,
        'State':p.status,'Trigger':p.trigger,'Stop':p.stop,'Target':p.target,
        'R:R':p.rr,'Quality*':p.score,'Why not ready':p.blocker,'As of':p.asof
    } for p in plans])


def setup_overview(snap):
    ctx=snap['context'];fr=ctx['sectors']
    if fr.empty:return 'Sector rotation unavailable — insufficient fresh ETF data.'
    leaders=fr.head(3)
    return ' / '.join(f"{r['Name']} ({percentfmt(r['Vs SPY 21D pp'])} vs SPY 21D)" for _,r in leaders.iterrows())


def open_issues():
    st.caption('Earnings dates, corporate filings, options spreads and geopolitical headlines are not automatically verified. Check independent sources before any live trade.')




def event_panel():
    e=st.session_state.events
    st.caption('Events come from uploaded CSV; no calendar was silently invented.')
    if e.empty:
        st.warning('Event calendar NOT VERIFIED. Import dated macro/earnings events in Terminal controls before relying on event-risk clearance.')
    else:
        now=NOW().replace(tzinfo=None);soon=e[(e['When ET']>=now-timedelta(days=1)) & (e['When ET']<=now+timedelta(days=10))]
        if soon.empty:st.info('No events in the next ten days in the uploaded calendar. This does not certify that no events exist.')
        else:st.dataframe(soon[['When ET','Title','Impact','Tickers','Confirmed','Source']],hide_index=True,use_container_width=True)




def plan_selector():
    frozen=st.session_state.frozen
    if not frozen:return None
    opts=list(frozen)
    choice=st.selectbox('Frozen trade plan',opts,format_func=lambda x: f"{frozen[x]['symbol']} · {frozen[x]['setup']} · {frozen[x]['direction']} · {frozen[x]['asof']}")
    return frozen.get(choice)




def live_result(plan):
    st.markdown('#### Live trigger check')
    sym=plan['symbol'];now=NOW()
    stopped=st.session_state.last_stop
    if stopped and (now-datetime.fromisoformat(stopped)).total_seconds()<st.session_state.get('cooldown_minutes',20)*60:
        st.error('Cooldown active after a recorded stop-out. Review, do not re-enter.')
        return
    event_block=bool(risk_events(st.session_state.events,now,sym)) or st.session_state.manual_event_block
    event_verified=st.checkbox('I checked upcoming earnings and material events for this ticker',value=False,key='check_event_'+plan['id'])
    st.caption('The current price and VWAP are read only when you explicitly request the live check. The button does not place orders.')
    if st.button(f'Check {sym} — completed 10m & VWAP',type='primary',key='checklive_'+plan['id']):
        if 'SIMULATED' in st.session_state.market_snapshot['source']:
            st.session_state.live_result[plan['id']]={'status':'DEMO','why':'Live confirmation disabled in simulated mode. Switch to Yahoo data and refresh research.'}
        elif now.weekday()>=5 or not (time(9,30)<=now.time()<time(16,0)) or event_block or plan.get('status')!='ARMED':
            st.session_state.live_result[plan['id']]=live_check(plan,None,now=now,manual_event_block=event_block)
        else:
            try:
                five=cached_intraday(sym)
                proxy_map={'Health Care':'XLV','Healthcare':'XLV','Consumer Staples':'XLP','Utilities':'XLU',
                    'Energy':'XLE','Information Technology':'XLK','Technology':'XLK','Financials':'XLF',
                    'Industrials':'XLI','Materials':'XLB','Consumer Discretionary':'XLY',
                    'Communication Services':'XLC','Real Estate':'XLRE'}
                sector_proxy=proxy_map.get(plan['sector'])
                sector_feed=cached_intraday(sector_proxy) if sector_proxy else None
                # Market context is optional/diagnostic, sector confirmation is required.
                try:spy_feed=cached_intraday('SPY')
                except Exception:spy_feed=None
                st.session_state.live_result[plan['id']]=live_check(plan,five,now=now,
                    opening_cutoff=time.fromisoformat(st.session_state.get('cutoff','09:50')),
                    manual_event_block=event_block,sector_five=sector_feed,require_sector=True,market_five=spy_feed)
            except Exception as exc:
                st.session_state.live_result[plan['id']]={'status':'STALE','why':f'Intraday feed unavailable: {type(exc).__name__}: {str(exc)[:180]}'}
    if plan['id'] in st.session_state.live_result:
        st.session_state.live_result[plan['id']].setdefault('checked_at',now.isoformat())
    result=st.session_state.live_result.get(plan['id'])
    if result:
        state=result.get('status','UNKNOWN')
        why=result.get('why','')
        try:
            seconds_since=(NOW()-datetime.fromisoformat(result.get('checked_at',now.isoformat()))).total_seconds()
        except Exception:seconds_since=1_000_000
        if seconds_since>180 or NOW().weekday()>=5 or not (time(9,30)<=NOW().time()<time(16,0)):
            state='STALE';why='Previous live check expired or cash session closed. Refresh to reassess; do not trade from this old status.'
        if state=='READY' and not event_verified:state='BLOCKED';why='Earnings/event verification not acknowledged. '+why
        if state=='READY':st.success(f'READY FOR MANUAL REVIEW — {why}')
        elif state in ('EXTENDED','INVALID','BLOCKED','STALE'):st.error(f'{state} — {why}')
        else:st.info(f'{state} — {why}')
        if 'price' in result and result.get('price') is not None:
            c1,c2,c3=st.columns(3)
            c1.metric('Last 10m close',money(result['price']))
            c2.metric('RTH VWAP',money(result.get('vwap')))
            c3.metric('Remaining R:R',str(result.get('remaining_rr','—')))
            if result.get('sector_price') is not None:
                st.caption(f"Sector confirmation: {money(result['sector_price'])} vs session VWAP {money(result.get('sector_vwap'))}. SPY context: {result.get('market_agrees','unknown')} (diagnostic only).")
        if result.get('bar_time'):st.caption('Completed bar start: '+result['bar_time']+' • Provider may be delayed.')
    if event_block:st.error('Macro/event restriction active. Revalidate plan after the event.')


def manual_manage(plan):
    pid=plan['id'];symbol=plan['symbol']
    position=st.session_state.positions.get(pid)
    if position:
        st.markdown(f'#### MANAGE — {symbol} (manual record)')
        st.warning('This is not connected to your broker. Price, fills, stop execution and account exposure are NOT verified.')
        st.markdown(f"**Frozen thesis:** {plan['setup']} · {plan['direction']} · stop reference {money(plan['stop'])} · next obstacle {money(plan['target'])}.")
        st.info('Decision: Is the original thesis still valid? Use the planned SWING structure, not a random intraday EMA dip.')
        daily=st.session_state.market_snapshot['frames'].get(symbol)
        daily_m=snapshot(daily) if daily is not None else None
        if daily_m:
            st.caption(f"Last completed daily close {money(daily_m['price'])} · 21 EMA {money(daily_m['ema21'])} · as of {daily_m['asof']}. Daily trend context, not a stop execution feed.")
        if st.button('Check underlying against frozen stop / target',key='manage_quote_'+pid):
            if 'SIMULATED' in st.session_state.market_snapshot['source']:
                st.info('Price management check disabled in synthetic demo mode.')
            else:
                try:
                    quote=cached_intraday(symbol)
                    if quote.empty:raise ValueError('No intraday quote')
                    q=float(quote.Close.iloc[-1]);qt=quote.index[-1]
                    if qt.tzinfo is None:raise ValueError('Missing quote timezone')
                    qt=qt.tz_convert(ET)
                    age=(NOW()-qt.to_pydatetime()).total_seconds()/60
                    if age>30 or qt.date()!=NOW().date():
                        st.warning(f'Last known underlying close {money(q)} is STALE (bar {qt}). Do not infer current stop status.')
                    else:
                        sign=1 if plan['direction']=='LONG' else -1
                        if sign*(q-plan['stop'])<=0:
                            st.error(f'Underlying {money(q)} beyond planned stop reference {money(plan["stop"])}. This does NOT mean any broker stop executed.')
                        elif plan['target'] is not None and sign*(q-plan['target'])>=0:
                            st.info(f'Underlying {money(q)} reached the planned obstacle {money(plan["target"])}. Follow your predefined management plan.')
                        else:
                            st.info(f'Underlying {money(q)} has not breached the stop reference. Reassess price structure and earnings; this alone does not prove the thesis is intact.')
                        st.caption('Quote bar time '+str(qt)+' · Yahoo may be delayed.')
                except Exception as exc:st.error(f'Quote not verified: {type(exc).__name__}: {str(exc)[:160]}')
        with st.form('exit_'+pid):
            exit_price=st.number_input('Actual exit fill ($)',min_value=0.01,value=float(position['entry_price']),format='%.2f')
            reason=st.selectbox('Reason for exit',['Planned target','Structural invalidation / stop','Trailing exit','Manual override','Other'])
            notes=st.text_input('Review note',max_chars=300)
            ended=st.form_submit_button('Mark closed (manual journal)')
        if ended:
            sign=1 if plan['direction']=='LONG' else -1
            per_unit=sign*(exit_price-position['entry_price'])
            planned_risk=sign*(position['entry_price']-plan['stop'])
            realized_r=per_unit/planned_risk if planned_risk>0 else None
            st.session_state.journal.append({'at':NOW().isoformat(),'event':'EXIT_RECORDED','id':pid,'symbol':symbol,
                'entry':position['entry_price'],'exit':exit_price,'reason':reason,'R_before_costs':round(realized_r,3) if realized_r is not None else None,'note':notes})
            if reason=='Structural invalidation / stop':st.session_state.last_stop=NOW().isoformat()
            del st.session_state.positions[pid]
            st.success('Manual exit recorded; export your session JSON to preserve it.');st.rerun()
    else:
        with st.expander('I placed a trade independently — record it for management (no broker orders)',expanded=False):
            with st.form('taken_'+pid):
                entry=st.number_input('Actual underlying-equivalent entry price',min_value=0.01,value=float(plan['trigger']),format='%.2f')
                execution=st.selectbox('Instrument',['Common stock','ETF','Options (underlying reference only)','Other'])
                note=st.text_input('Why did you take this entry?',max_chars=200)
                submit=st.form_submit_button('Record entered trade')
            if submit:
                st.session_state.positions[pid]={'entry_price':float(entry),'instrument':execution,'at':NOW().isoformat()}
                st.session_state.journal.append({'at':NOW().isoformat(),'event':'ENTRY_RECORDED','id':pid,'symbol':symbol,
                    'entry':entry,'instrument':execution,'plan_state_when_frozen':plan['status'],'note':note})
                st.warning('Entry recorded in this browser session only. Not a broker confirmation.');st.rerun()


def render_live(snap):
    st.subheader('Focused setup review')
    if st.session_state.positions:
        st.info('A manual position is open. Entry scanning is suspended; manage the original plan first.')
    if st.session_state.positions:
        open_ids=[k for k in st.session_state.positions if k in st.session_state.frozen]
        if open_ids:
            active_pid=st.selectbox('Manage an open manual position',open_ids,
                format_func=lambda x:st.session_state.frozen[x]['symbol']+' · '+st.session_state.frozen[x]['setup'])
            plan=st.session_state.frozen[active_pid]
        else:plan=None
    else:plan=plan_selector()
    if plan is None:
        st.info('Add a candidate to The Watchtower above to review its trigger and invalidation.')
        return
    st.markdown(card(plan),unsafe_allow_html=True)
    if plan['id'] not in st.session_state.positions:
        live_result(plan)
    else:
        st.caption('Active manual trade record — entry scanner is intentionally hidden while managing.')
    manual_manage(plan)
    frames=snap['frames']
    if plan['symbol'] in frames:
        with st.expander('Show the focused chart & decision levels',expanded=True):
            fig=candles(frames[plan['symbol']],plan=plan,title=f"{plan['symbol']} · completed daily structure")
            if fig is not None:st.plotly_chart(fig,use_container_width=True,config={'displayModeBar':False,'scrollZoom':False})
            st.caption('Daily chart for trend context. This is NOT a live trade confirmation chart.')
    event_panel()


def theme_table(snap):
    """Basket descriptors, never claim full 90-theme breadth from thin coverage."""
    m={s:snapshot(f) for s,f in snap['frames'].items()}
    spy=m.get('SPY');out=[]
    for theme in THEMES:
        members=list(dict.fromkeys(theme['symbols']))
        valid=[m[s] for s in members if m.get(s) and spy and m[s]['asof']==spy['asof']]
        coverage=len(valid)/max(1,len(members))
        eligible=len(valid)>=3 and coverage>=.60
        out.append({'Theme':theme['name'],'Group':theme['group'], 'Valid / Members':f'{len(valid)}/{len(members)}',
                    'RS 5D pp':(sum(x['r5']-spy['r5'] for x in valid)/len(valid) if eligible else None),
                    'Above 21 %':(100*sum(x['price']>x['ema21'] for x in valid)/len(valid) if eligible else None),
                    'State':'PROXY BREADTH' if eligible else 'INSUFFICIENT COVERAGE'})
    return pd.DataFrame(out)




def render_journal():
    st.subheader('Plan adherence & manual journal')
    st.caption('Session-only storage by design (no shared unprotected server database). Download a JSON backup before your Streamlit session expires.')
    frozen=st.session_state.frozen
    st.metric('Frozen plans',len(frozen));st.metric('Recorded events',len(st.session_state.journal))
    if st.session_state.journal:
        f=pd.DataFrame(st.session_state.journal)
        st.dataframe(f,hide_index=True,use_container_width=True)
        closed=f[f['event']=='EXIT_RECORDED']
        if not closed.empty and 'R_before_costs' in closed:
            v=pd.to_numeric(closed['R_before_costs'],errors='coerce').dropna()
            if len(v):st.metric('Recorded average R (before costs)',f'{v.mean():.2f}R')
    else:st.info('No trade records yet. A properly skipped setup and a disciplined losing trade both matter.')
    if frozen:
        st.markdown('#### Frozen plan archive')
        st.dataframe(pd.DataFrame([{'Symbol':p['symbol'],'Setup':p['setup'],'Trigger':p['trigger'],
            'Invalidation':p['stop'],'As of':p['asof']} for p in frozen.values()]),hide_index=True)
    if frozen:
        removal=st.selectbox('Remove an outdated frozen plan',list(frozen),
            format_func=lambda k:f"{frozen[k]['symbol']} — {frozen[k]['setup']} ({frozen[k]['asof']})")
        if st.button('Remove selected frozen plan',disabled=removal in st.session_state.positions):
            removed=frozen.pop(removal)
            st.session_state.journal.append({'at':NOW().isoformat(),'event':'PLAN_REMOVED','id':removal,
                'symbol':removed['symbol'],'note':'Removed from current focus; original plan event preserved'})
            st.success('Plan removed from active watchlist. Export backup to preserve change.');st.rerun()
    payload={'schema':'crescent-v7-session-1','frozen':frozen,'positions':st.session_state.positions,
             'last_stop':st.session_state.last_stop,
             'journal':st.session_state.journal,'exported_at':NOW().isoformat()}
    st.download_button('Export session backup JSON',data=json.dumps(payload,indent=2,default=str),
                       file_name='Crescent_V7_Session_Backup.json',mime='application/json',type='primary')
    uploaded=st.file_uploader('Restore previously exported Crescent V7 session JSON',type=['json'],key='restore_json')
    if uploaded and st.button('Validate & restore journal'):
        try:
            if uploaded.size>2_000_000:raise ValueError('Backup exceeds 2 MB maximum')
            data=json.loads(uploaded.getvalue().decode('utf-8'))
            if data.get('schema')!='crescent-v7-session-1' or not isinstance(data.get('journal'),list) or not isinstance(data.get('frozen'),dict):
                raise ValueError('Unexpected backup schema')
            if len(data['journal'])>5000 or len(data['frozen'])>500:raise ValueError('Backup exceeds allowed limits')
            st.session_state.frozen={k:v for k,v in data['frozen'].items() if isinstance(v,dict) and all(n in v for n in ['symbol','trigger','stop','direction','id'])}
            st.session_state.journal=[x for x in data['journal'] if isinstance(x,dict)]
            st.session_state.positions={k:v for k,v in data.get('positions',{}).items() if k in st.session_state.frozen and isinstance(v,dict)}
            st.session_state.last_stop=data.get('last_stop') if isinstance(data.get('last_stop'),str) else None
            st.success('Restored. Export again after changes.');st.rerun()
        except Exception as exc:st.error('Could not restore: '+str(exc))


def render_settings():
    st.subheader('Execution rules & data policy')
    st.caption('These settings help maintain a precommitted process; they cannot enforce broker-side risk limits.')
    st.session_state.cutoff=st.selectbox('Earliest entry confirmation (US Eastern)',options=['09:50','10:00','10:15','10:30'],
              index=['09:50','10:00','10:15','10:30'].index(st.session_state.get('cutoff','09:50')))
    st.session_state.cooldown_minutes=st.slider('Cooldown after a manually recorded stop (minutes)',5,90,
                                              value=st.session_state.get('cooldown_minutes',20),step=5)
    st.session_state.manual_event_block=st.checkbox('Temporarily block new live trade reviews due to macro/news risk',
                                                    value=st.session_state.manual_event_block)
    st.markdown('#### Event calendar input')
    st.write('Upload your own confirmed economic/earnings calendar CSV. This is not a replacement for an official calendar. High-impact **confirmed** events inside ±75 minutes block matching live entries.')
    st.code('Date,Time_ET,Title,Impact,Tickers,Source,Confirmed\n2026-11-04,14:00,Illustrative policy event,HIGH,ALL,EXAMPLE ONLY,false',language='csv')
    ev=st.file_uploader('Upload events CSV (not auto-shared)',type=['csv'],key='evcsv')
    if ev and st.button('Import event calendar'):
        try:
            st.session_state.events=read_events(ev.getvalue())
            st.success(f'Imported {len(st.session_state.events)} user-supplied events. Re-check source accuracy.')
        except Exception as exc:st.error('Calendar rejected: '+str(exc))
    st.markdown('#### Explicit limitations')
    st.write('No broker integration or risk enforcement, no position sizing, no automatic order routing, no calibrated win probabilities, no reliable live news verification, no options chain/spread checks, and no durable shared backend.')
    st.write('Yahoo is an unofficial delayed/best-effort data adapter. The optional TradingView Screener package is separate from the authenticated TradingView connection in ChatGPT and may fail.')
    st.write('The original Crescent Scanner is independent. Running or deploying this app does not modify its code or settings.')


def sidebar_controls():
    st.sidebar.markdown('### Research data')
    mode=st.sidebar.radio('Market-data source',['Demo — simulated','Yahoo Finance — beta'],
         index=['Demo — simulated','Yahoo Finance — beta'].index(st.session_state.data_mode),key='source_radio')
    st.session_state.data_mode=mode
    breadth=st.sidebar.selectbox('Universe coverage',['Balanced 60','Balanced 120','Full 574'],index=0,
         help='Balanced sample is NOT a full-market scan; the original 574 stock CSV is retained.')
    st.session_state.include_etfs=st.sidebar.checkbox('Include diversified ETF trade candidates',value=st.session_state.include_etfs,
            help='Separate from broad-market and sector ETFs used only for regime context. Leveraged ETFs are not automatically armed.')
    tv=st.sidebar.checkbox('Optional TradingView public screener discovery',value=False,
        help='This is not your authenticated TradingView connector. Yahoo still supplies actual OHLC candles.')
    pins=st.sidebar.text_input('Pinned focus symbols (comma-separated)',value=st.session_state.pins)
    st.session_state.pins=pins
    if st.sidebar.button('Run overnight research',type='primary',use_container_width=True):
        symbols,_,explanation,warnings=all_symbols(pins,mode,breadth,tv)
        st.session_state.scan_errors=warnings
        st.session_state.universe_caption=explanation
        if mode=='Demo — simulated':
            frames,_=demo_pack()
            install_snapshot(frames,'SIMULATED research candles — not market prices',{})
            st.sidebar.success('Simulated research updated.')
        else:
            st.sidebar.info(f'Requesting {len(symbols)} instruments in batches. Full 574 can take time; Yahoo may limit access.')
            progress=st.sidebar.progress(0)
            # cache daily for identical requested batches; no promise of automatic refresh.
            try:
                frames,fail=cached_daily(tuple(symbols))
                install_snapshot(frames,'Yahoo Finance daily candles (best effort / delayed)',fail)
                progress.progress(100)
                st.sidebar.success(f'{len(frames)}/{len(symbols)} histories downloaded. See Research for coverage.')
            except Exception as exc:st.sidebar.error(f'Provider failed: {type(exc).__name__}: {str(exc)[:150]}. Previous snapshot remains visible.')
    st.sidebar.divider()
    st.sidebar.caption('Original Crescent stock and ETF universes preserved in this standalone package.')
    st.sidebar.caption('Live entry checks are available only for frozen plans during regular US market hours.')
    st.sidebar.caption('No broker orders · no sizing · no fake win probabilities')





def render_terminal(snap):
    draw_topbanner(snap)
    ctx = snap['context']
    benchmarks = ctx['benchmarks']
    if not benchmarks.empty:
        columns = st.columns(len(benchmarks))
        for col, (_, row) in zip(columns, benchmarks.iterrows()):
            col.metric(str(row['Symbol']), str(row['Trend']), percentfmt(row['5D %']))
    with st.expander('Sector leadership', expanded=True):
        st.caption('ETF relative strength versus SPY · completed daily history')
        sectors = ctx['sectors']
        if sectors.empty:
            st.info('Sector history unavailable.')
        else:
            st.dataframe(sectors[['Name','5D %','21D %','Vs SPY 21D pp','Rotation']],
                         hide_index=True, use_container_width=True)

    st.subheader('Ranked opportunities')
    st.caption('Research candidates from loaded history. Saving a setup freezes its levels; it does not confirm an entry.')
    plans = get_plans()
    left, right = st.columns(2)
    side = left.selectbox('Direction', ['All', 'LONG', 'SHORT'])
    query = right.text_input('Find a symbol', placeholder='e.g. NVDA').strip().upper()
    visible = [p for p in plans if (side == 'All' or p.direction == side) and (not query or query in p.symbol)]
    if not visible:
        st.info('No candidates match the current filters.')
    columns = st.columns(3)
    for col, plan in zip(columns, visible[:3]):
        with col:
            st.markdown(card(plan), unsafe_allow_html=True)
            if st.button('Add to The Watchtower', key='add_'+plan.id,
                         disabled=plan.id in st.session_state.frozen or len(st.session_state.frozen)>=3):
                st.session_state.frozen[plan.id] = plan.to_dict()
                st.session_state.journal.append({'at':NOW().isoformat(),
                    'event':'PLAN_FROZEN' if plan.status=='ARMED' else 'WATCH_FROZEN',
                    'id':plan.id,'symbol':plan.symbol,'note':'Frozen from completed daily history'})
                st.rerun()
    with st.expander(f'All matching candidates ({len(visible)})'):
        st.dataframe(plans_frame(visible), hide_index=True, use_container_width=True)
        if visible:
            selected = st.selectbox('Candidate to monitor', list(range(len(visible))),
                format_func=lambda i: f'{visible[i].symbol} · {visible[i].setup} · {visible[i].direction}')
            plan = visible[selected]
            if st.button('Save selected setup', key='save_candidate',
                         disabled=plan.id in st.session_state.frozen or len(st.session_state.frozen)>=3):
                st.session_state.frozen[plan.id] = plan.to_dict()
                st.session_state.journal.append({'at':NOW().isoformat(),'event':'WATCH_FROZEN',
                    'id':plan.id,'symbol':plan.symbol,'note':'Frozen research candidate; no entry permission'})
                st.rerun()

    st.divider()
    st.subheader('The Watchtower')
    st.caption('Active setup monitoring · up to three frozen plans · checks run only when requested')
    frozen = list(st.session_state.frozen.values())
    if frozen:
        rows = []
        for plan in frozen:
            result = st.session_state.live_result.get(plan['id'], {})
            checked = result.get('checked_at')
            fresh = False
            if checked:
                try:
                    now = NOW()
                    fresh = (now-datetime.fromisoformat(checked)).total_seconds() <= 180 and now.weekday()<5 and time(9,30)<=now.time()<time(16,0)
                except (ValueError, TypeError):
                    pass
            state = 'OPEN' if plan['id'] in st.session_state.positions else (result.get('status','WATCH') if fresh else 'STALE' if result else 'AWAITING CHECK')
            rows.append({'Symbol':plan['symbol'],'Setup':plan['setup'],'Side':plan['direction'],
                'State':state,'Trigger':plan['trigger'],'Invalidation':plan['stop'],
                'Target':plan.get('target'),'Checked at':checked or 'Not checked'})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        render_live(snap)
    else:
        st.info('Your watchtower is clear. Add a ranked opportunity to begin monitoring.')

    with st.expander('Session journal & backups'):
        render_journal()
    with st.expander('Terminal controls & event calendar'):
        render_settings()


def main():
    init_state()
    brand('Market intelligence · Active setup monitoring')
    sidebar_controls()
    snap = st.session_state.market_snapshot
    if st.session_state.data_mode.startswith('Yahoo') and 'SIMULATED' in snap['source']:
        st.error('The displayed snapshot is still simulated. Run research from the sidebar to load market history.')
    for warning in st.session_state.scan_errors:
        st.warning(warning)
    render_terminal(snap)
    st.divider()
    st.caption('Crescent Trade Terminal — BETA · Standalone test application · Paper planning only · As of '+str(snap['asof']))


if __name__=='__main__':main()
