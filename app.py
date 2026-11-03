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
    yahoo_daily,yahoo_five_minute,read_events,risk_events,news_rss)
from crescent_ui import card
from terminal_view import CSS, header, overview, opportunity, table, e
from intraday_context import fetch_intraday, session_rows, tradingview_quotes
from crescent_charts import candles
from rotation_themes import THEMES
from cloud_engine import bar_session_resample,scan_symbol

st.set_page_config(page_title='Crescent Trade Terminal — BETA',page_icon='🌙',
                   layout='wide',initial_sidebar_state='collapsed')
NOW=lambda:datetime.now(ET)


@st.cache_data(ttl=1200,show_spinner=False)
def cached_daily(symbols_tuple):
    return yahoo_daily(symbols_tuple,period='1y')


@st.cache_data(ttl=105,show_spinner=False)
def cached_intraday(symbol,extended=False):
    return yahoo_five_minute(symbol,days='10d',extended=extended)


@st.cache_data(ttl=55,show_spinner=False)
def cached_context_bars():
    return fetch_intraday(tuple(dict.fromkeys(['SPY','QQQ','IWM','^VIX']+list(SECTORS))))


@st.cache_data(ttl=60,show_spinner=False)
def cached_tv_quotes(symbols):
    return tradingview_quotes(symbols)


@st.fragment(run_every='60s')
def render_intraday_context():
    snap=st.session_state.market_snapshot
    context={'rows':pd.DataFrame(),'status':'UNAVAILABLE'}
    if snap.get('loaded',0):
        try:
            frames,failures=cached_context_bars()
            context=session_rows(frames,snap['frames'],NOW())
            if failures:st.caption(f'Intraday coverage: {len(frames)} series · {len(failures)} unavailable')
        except Exception as exc:
            st.caption(f'Intraday feed unavailable: {type(exc).__name__}. No daily substitute is shown.')
    st.session_state.intraday_context=context
    st.markdown(overview(snap,get_plans(),st.session_state.frozen,context),unsafe_allow_html=True)


@st.cache_data(ttl=900,show_spinner=False)
def cached_headlines(query):
    return news_rss(query)




def init_state():
    defaults={'data_mode':'Yahoo Finance — beta','market_snapshot':None,'failure':{},
        'plans':[],'frozen':{},'journal':[],'positions':{},'view':'The Watchtower',
        'last_stop':None,'events':pd.DataFrame(),'news':[], 'live_result':{},
        'last_refresh':None,'manual_event_block':False,'pins':', '.join(DEFAULT_WATCH),
        'source_caption':'','universe_caption':'','scan_errors':[],'include_etfs':True}
    for k,v in defaults.items():
        if k not in st.session_state:st.session_state[k]=v
    previous=st.session_state.get('market_snapshot')
    if previous and 'SIMULATED' in previous.get('source',''):
        st.session_state.market_snapshot=None
        st.session_state.initial_fetch_attempted=False
        st.session_state.frozen={k:v for k,v in st.session_state.frozen.items() if 'SIMULATED' not in v.get('source','')}
        st.session_state.live_result={}
    st.session_state.data_mode='Yahoo Finance — beta'
    if st.session_state['market_snapshot'] is None:
        install_snapshot({},'Yahoo Finance · awaiting data', {})
        st.session_state.last_refresh=None


def all_symbols(pins,mode,breadth,with_tv):
    sectors=symbols_from_file('stocks.csv')
    pinlist=[s.strip().upper() for s in pins.replace('\n',',').split(',') if s.strip()]
    lim={'Balanced 60':60,'Balanced 120':120,'Full 574':9999}[breadth]
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
    effective=now
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




def plans_frame(plans):
    return pd.DataFrame([{
        'Symbol':p.symbol,'Sector':p.sector,'Setup':p.setup,'Side':p.direction,
        'State':p.status,'Trigger':p.trigger,'Stop':p.stop,'Target':p.target,
        'R:R':p.rr,'Quality*':p.score,'Why not ready':p.blocker,'As of':p.asof
    } for p in plans])








def event_panel():
    e=st.session_state.events
    st.caption('Events come from uploaded CSV; no calendar was silently invented.')
    if e.empty:
        st.warning('Event calendar NOT VERIFIED. Import dated macro/earnings events in Terminal controls before relying on event-risk clearance.')
    else:
        now=NOW().replace(tzinfo=None);soon=e[(e['When ET']>=now-timedelta(days=1)) & (e['When ET']<=now+timedelta(days=10))]
        if soon.empty:st.info('No events in the next ten days in the uploaded calendar. This does not certify that no events exist.')
        else:dark_frame(soon[['When ET','Title','Impact','Tickers','Confirmed','Source']],hide_index=True,use_container_width=True)




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
    st.markdown(opportunity(plan,1,snap['frames']),unsafe_allow_html=True)
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






def render_journal():
    st.subheader('Plan adherence & manual journal')
    st.caption('Session-only storage by design (no shared unprotected server database). Download a JSON backup before your Streamlit session expires.')
    frozen=st.session_state.frozen
    st.metric('Frozen plans',len(frozen));st.metric('Recorded events',len(st.session_state.journal))
    if st.session_state.journal:
        f=pd.DataFrame(st.session_state.journal)
        dark_frame(f,hide_index=True,use_container_width=True)
        closed=f[f['event']=='EXIT_RECORDED']
        if not closed.empty and 'R_before_costs' in closed:
            v=pd.to_numeric(closed['R_before_costs'],errors='coerce').dropna()
            if len(v):st.metric('Recorded average R (before costs)',f'{v.mean():.2f}R')
    else:st.info('No trade records yet. A properly skipped setup and a disciplined losing trade both matter.')
    if frozen:
        st.markdown('#### Frozen plan archive')
        dark_frame(pd.DataFrame([{'Symbol':p['symbol'],'Setup':p['setup'],'Trigger':p['trigger'],
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












def dark_frame(frame, *args, **kwargs):
    st.markdown(table(frame), unsafe_allow_html=True)


def refresh_market(breadth, pins, discovery):
    symbols,_,explanation,warnings=all_symbols(pins,'Yahoo Finance — beta',breadth,discovery)
    st.session_state.universe_caption=explanation
    with st.spinner(f'Fetching real market history · {len(symbols)} instruments…'):
        try:
            frames,fail=cached_daily(tuple(symbols))
            if not frames:
                st.session_state.scan_errors=warnings+['Yahoo returned no usable history. No generated prices or signals have been substituted. Retry the scan when the provider is available.']
                st.session_state.provider_failures=fail
                return
            install_snapshot(frames,'Yahoo Finance · completed daily candles',fail)
            st.session_state.scan_errors=warnings
            if fail:st.session_state.scan_errors.append(f'{len(fail)} instruments unavailable; excluded from ranking.')
        except Exception as exc:
            st.session_state.scan_errors=[f'Market feed unavailable: {type(exc).__name__}: {str(exc)[:140]}. No simulated fallback.']


def render_terminal(snap, side, search):
    plans=get_plans()
    shown=[p for p in plans if (side=='All' or p.direction==side) and (not search or search.upper() in p.symbol)]
    st.markdown('<div class="section-heading">Top 3 right now <span>Ranked from loaded history · triggers require confirmation</span></div>',unsafe_allow_html=True)
    if shown:
        for col,(index,plan) in zip(st.columns(3),enumerate(shown[:3],1)):
            with col:
                st.markdown(opportunity(plan,index,snap['frames']),unsafe_allow_html=True)
                if st.button('＋ Watch setup',key='watch_'+plan.id,use_container_width=True,
                    disabled=plan.id in st.session_state.frozen or len(st.session_state.frozen)>=3):
                    st.session_state.frozen[plan.id]=plan.to_dict()
                    st.session_state.journal.append({'at':NOW().isoformat(),'event':'PLAN_FROZEN' if plan.status=='ARMED' else 'WATCH_FROZEN',
                        'id':plan.id,'symbol':plan.symbol,'note':'Frozen from completed market history'})
                    st.rerun()
    else:
        st.markdown('<div class="terminal-panel empty">No qualifying setups in the current selection. Market data and entry permission are never assumed.</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="section-heading">The Watchtower <span>{len(st.session_state.frozen)} / 3 monitored setups · manual trigger checks</span></div>',unsafe_allow_html=True)
    rows=[]
    for plan in st.session_state.frozen.values():
        result=st.session_state.live_result.get(plan['id'],{})
        checked=result.get('checked_at'); fresh=False
        if checked:
            try:
                now=NOW();age=(now-datetime.fromisoformat(checked)).total_seconds()
                fresh=0<=age<=180 and now.weekday()<5 and time(9,30)<=now.time()<time(16,0)
            except (ValueError,TypeError):pass
        state='OPEN' if plan['id'] in st.session_state.positions else result.get('status','WATCH') if fresh else 'STALE' if result else 'AWAITING CHECK'
        rows.append({'Symbol':plan['symbol'],'Side':plan['direction'],'Setup':plan['setup'],'State':state,
            'Trigger':money(plan['trigger']),'Invalidation':money(plan['stop']),'Target':money(plan.get('target')),'Checked':checked or 'Not checked'})
    if rows:
        dark_frame(pd.DataFrame(rows))
        with st.expander('Inspect setup / check trigger / manage position',expanded=True):render_live(snap)
    else:
        st.markdown('<div class="terminal-panel empty">No setups monitored. Use <b>＋ Watch setup</b> on a ranked opportunity.<br>Frozen trigger, invalidation and target levels stay fixed until you remove the setup.</div>',unsafe_allow_html=True)
    with st.expander(f'All candidates · {len(shown)}'):
        dark_frame(plans_frame(shown))
        if shown:
            index=st.selectbox('Select candidate',range(len(shown)),format_func=lambda i:shown[i].symbol+' · '+shown[i].setup)
            plan=shown[index]
            if st.button('Watch selected setup',disabled=plan.id in st.session_state.frozen or len(st.session_state.frozen)>=3):
                st.session_state.frozen[plan.id]=plan.to_dict()
                st.session_state.journal.append({'at':NOW().isoformat(),'event':'WATCH_FROZEN','id':plan.id,'symbol':plan.symbol,'note':'Frozen research candidate'})
                st.rerun()
    with st.expander('TradingView stock quotes / comparison'):
        st.caption('Public screener snapshot, separate from your connected TradingView account. Some stocks are 15 minutes delayed; ETF coverage was unavailable in testing. These quotes never authorize entries.')
        if st.button('Fetch TradingView quotes'):
            symbols=tuple(dict.fromkeys([p.symbol for p in shown[:20]]+[s.strip().upper() for s in st.session_state.pins.split(',') if s.strip()]))
            try:
                quotes=cached_tv_quotes(symbols)
                st.session_state.tv_quote_comparison=quotes
                missing=sorted(set(symbols)-set(quotes.Symbol if not quotes.empty else []))
                st.session_state.tv_quote_missing=missing
            except Exception as exc:
                st.session_state.tv_quote_comparison=pd.DataFrame()
                st.warning(f'TradingView quote request failed: {type(exc).__name__}. Yahoo data remains separate.')
        quotes=st.session_state.get('tv_quote_comparison')
        if quotes is not None:
            dark_frame(quotes)
            missing=st.session_state.get('tv_quote_missing',[])
            if missing:st.caption('No TradingView quote returned: '+', '.join(missing))
    with st.expander('Journal / session backup'):render_journal()
    with st.expander('Risk controls / event calendar'):render_settings()


def main():
    init_state()
    st.markdown(CSS,unsafe_allow_html=True)
    st.markdown(header(st.session_state.last_refresh),unsafe_allow_html=True)
    snap=st.session_state.market_snapshot
    render_intraday_context()
    controls=st.columns([1.2,1,1,1,1.4])
    breadth=controls[0].selectbox('Stock universe',['Balanced 60','Balanced 120','Full 574'])
    side=controls[1].selectbox('Show',['All','LONG','SHORT'],format_func=lambda x:{'All':'All setups','LONG':'▲ Bullish','SHORT':'▼ Bearish'}[x])
    search=controls[2].text_input('Symbol filter',placeholder='Ticker…')
    controls[3].markdown('<div style="height:23px"></div>',unsafe_allow_html=True)
    refresh=controls[3].button('↻ Scan now',type='primary',use_container_width=True)
    updated=st.session_state.last_refresh
    pins=controls[4].text_input('My list',value=st.session_state.pins,placeholder='Tickers, comma separated')
    st.session_state.pins=pins
    with st.expander('Data connection / coverage'):
        st.caption('Sector Today % compares completed 5-minute regular-session bars with the previous close. Vs SPY is session relative strength in percentage points. VWAP uses this regular session only. Context refreshes every 60 seconds; stale/closed sessions are labelled. Daily setup rankings and entry checks remain separate.')
        st.caption(f'Last refresh: {updated or "Awaiting provider"} · {snap.get("loaded",0)} histories loaded')
        discovery=st.checkbox('Use TradingView public screener for discovery',value=False)
        st.session_state.include_etfs=st.checkbox('Include ETF setup candidates',value=st.session_state.include_etfs)
        st.caption(st.session_state.universe_caption or 'Sector-balanced stock selection with benchmark and sector context.')
        failures=st.session_state.get('provider_failures') or snap.get('fail',{})
        if failures:dark_frame(pd.DataFrame([{'Symbol':k,'Feed issue':v} for k,v in failures.items()]))
    auto=not st.session_state.get('initial_fetch_attempted',False)
    if refresh or auto:
        st.session_state.initial_fetch_attempted=True
        refresh_market(breadth,pins,discovery)
        st.rerun()
    for warning in st.session_state.scan_errors:st.warning(warning)
    render_terminal(snap,side,search)
    st.markdown('<div class="terminal-foot">CRESCENT TRADE TERMINAL — BETA / REAL PROVIDER DATA ONLY / DAILY RESEARCH + ON-DEMAND INTRADAY CHECKS / NO AUTOMATIC ORDERS</div>',unsafe_allow_html=True)


if __name__=='__main__':main()
