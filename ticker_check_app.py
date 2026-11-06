"""Standalone single-ticker research page, independent of scanner detection rules."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from liquid_data import bounded_call
from ticker_check import financial_quarters,fundamental_review,technical_review,valuation_history,quote_review,number
from terminal_view import CSS,header,table,e,money
from ticker_check_view import CSS as TICKER_CSS,dashboard
from ticker_financials import revenue_comparisons,rule_of_40,reconcile_revenue


@st.cache_data(ttl=900,show_spinner=False)
def load_ticker(symbol):
    import yfinance as yf
    ticker=yf.Ticker(symbol.replace('.','-'));errors=[]
    def fetch(label,function,default):
        try:return bounded_call(function,timeout=12)
        except Exception as exc:
            errors.append(f'{label}: {type(exc).__name__}');return default
    info=fetch('Current valuation / company profile',ticker.get_info,{})
    history=fetch('Daily prices',lambda:ticker.history(period='5y',auto_adjust=False,actions=True,timeout=8),pd.DataFrame())
    quarters=fetch('Quarterly statements',lambda:ticker.get_income_stmt(freq='quarterly'),pd.DataFrame())
    annual=fetch('Annual statements',lambda:ticker.get_income_stmt(freq='yearly'),pd.DataFrame())
    comparisons=fetch('Year-earlier revenue comparisons',lambda:revenue_comparisons(ticker,quarters),{})
    comparisons,derived=reconcile_revenue(comparisons,annual)
    quarterly_cash=fetch('Quarterly cash flow',lambda:ticker.get_cashflow(freq='quarterly'),pd.DataFrame())
    if not info.get('financialCurrency') or not (info.get('shortName') or info.get('longName')):
        errors.append('Company profile / current valuation incomplete; retry Check ticker')
    from liquid_data import fetch_session_quotes
    try:quote=fetch_session_quotes((symbol,)).get(symbol,{})
    except Exception as exc:
        errors.append(f'TradingView session quote: {type(exc).__name__}');quote={}
    result={'comparison_derived':derived,'comparisons':comparisons,'quarterly_cash':quarterly_cash,'quote':quote,'history':history,'quarters':quarters,'annual':annual,'info':info,'errors':errors,
        'retrieved':datetime.now(ZoneInfo('America/New_York')).isoformat(timespec='seconds')}
    # Do not cache provider failures: the next explicit request can retry immediately.
    if errors:raise PartialTicker(result)
    return result


class PartialTicker(Exception):
    pass


def main():
    st.set_page_config(page_title='Ticker Check | Crescent Trade Terminal — BETA',page_icon='🌙',layout='wide',initial_sidebar_state='collapsed')
    st.markdown(CSS+TICKER_CSS,unsafe_allow_html=True)
    st.markdown(header(source='Yahoo Finance · reported financials'),unsafe_allow_html=True)
    st.markdown('<div class="tc-note">TICKER CHECK · Fundamentals / technicals / trade plan</div>',unsafe_allow_html=True)
    with st.form('ticker_lookup'):
        left,right=st.columns([4,1],vertical_alignment='bottom')
        symbol=left.text_input('Ticker',value=st.query_params.get('symbol','AAPL'),placeholder='e.g. NVDA, COHR, LITE',label_visibility='collapsed').strip().upper()
        with right:run=st.form_submit_button('Check ticker',type='primary',use_container_width=True)
    if run:
        if not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,14}',symbol):st.error('Enter one valid stock ticker.');return
        with st.spinner('Checking reported financials, valuation and completed daily/weekly trends…'):
            try:data=load_ticker(symbol)
            except PartialTicker as exc:data=exc.args[0]
            except Exception as exc:st.error(f'Provider unavailable: {type(exc).__name__}');return
        st.session_state.ticker_check_result={'symbol':symbol,'data':data}
    saved=st.session_state.get('ticker_check_result')
    if not saved:
        st.info('Enter a ticker to load five reported quarters and its technical review. Below the daily 200 SMA is a firm NO GO.');return
    symbol=saved['symbol'];data=saved['data'];now=datetime.now(ZoneInfo('America/New_York'))
    for error in data['errors']:st.warning(error+' · affected conclusions remain incomplete.')
    quarters=financial_quarters(data['quarters'],data.get('comparisons',{}));fund_state,fund_reason=fundamental_review(quarters,now)
    tech=technical_review(data['history'],now)
    quote=quote_review(data.get('quote',{}),now)
    if quote.get('valid') and quote['below200']:
        tech['decision']='NO GO · CURRENT PRICE BELOW 200 SMA'
        tech['reason']='The validated TradingView session price is below its daily 200 SMA. This veto overrides the completed-close plan.'
        tech['entry']=tech['stop']=tech['target']=tech['rr']=None
    if tech['decision'].startswith('NO GO'):combined=tech['decision']
    elif fund_state=='INCOMPLETE':combined='REVIEW INCOMPLETE · FUNDAMENTALS'
    elif fund_state=='CAUTION':combined='WATCH · FUNDAMENTAL CAUTION'
    else:combined=tech['decision']
    valuations,note=valuation_history(data['annual'],data['history'],data['info'])
    r40=rule_of_40(data['quarters'],data.get('quarterly_cash',pd.DataFrame()),data.get('comparisons',{}),data['annual'])
    st.markdown(dashboard(symbol,data,quarters,fund_state,tech,quote,combined,valuations,r40),unsafe_allow_html=True)
    with st.expander('Analysis detail · rationale, valuation history & data timing'):
        st.write(f'Fundamentals: {fund_state} — {fund_reason}')
        st.caption(f'Retrieved {data["retrieved"]} · Yahoo Finance reported statements · 15-minute response cache. Technical prices are completed regular sessions; current TradingView quote/feed status is shown separately.')
        if len(valuations)>=2:st.markdown(table(valuations.round(2)),unsafe_allow_html=True)
        st.caption(note)
        component=lambda v:f'{float(v):.2f}' if number(v) is not None else '—'
        st.write(f"Rule of 40 · TTM ending {r40['period'] or 'unavailable'} · revenue growth {component(r40['growth'])}% + FCF margin {component(r40['margin'])}%. Same four-quarter window; growth compares the preceding TTM. Software/SaaS reference, not a universal trade gate.")
        st.caption(r40['reason'])
        st.markdown('[Rule of 40 methodology](https://www.saasmetricsboard.com/rule-of-40)')
        missing=int(quarters['Revenue YoY %'].isna().sum()) if not quarters.empty else 5
        if data.get('comparison_derived'):st.caption('Derived year-earlier revenue: '+', '.join(data['comparison_derived'])+'; reconciled annual revenue minus the other three reported fiscal quarters.')
        if missing:st.caption(f'{missing} revenue YoY comparisons unavailable: the provider did not return matching year-earlier quarters. No growth estimates or annual-as-quarter substitutions are used.')
        if not tech['averages'].empty:
            st.write('Stage analysis: '+tech['stage']['stage']);st.caption(tech['stage']['reason'])
            st.write('High tight flag: '+('PREFERRED CANDIDATE' if tech['pattern']['found'] else 'NOT DETECTED'));st.caption(tech['pattern']['reason'])
            st.caption(f"Weekly calculation through {tech['weekly'].index[-1].date()}" if not tech['weekly'].empty else 'Weekly history unavailable.')
        st.caption('Support holding requires three closes above plus a recent test within 0.25 daily ATR. Above without a test is labelled untested. Stops: flag low or five-session pullback low minus 0.15 ATR. Trigger: pivot/high plus 0.05 ATR. Unknown targets stay blank. Gaps may fill beyond stops.')
        st.caption('Fundamental supportive requires five available revenue quarters, latest revenue YoY growth and positive operating/net margins. This is an operating-quality screen; balance sheet, dilution, earnings-event and industry-specific assessment remain separate.')
    if tech['averages'].empty:return
    with st.expander('Daily chart · 9 / 21 / 50 EMA & 200 SMA'):
        chart=tech['frame'].Close.to_frame('Close')
        for period in (9,21,50):chart[f'EMA {period}']=tech['frame'].Close.ewm(span=period,adjust=False).mean()
        chart['SMA 200']=tech['frame'].Close.rolling(200).mean()
        st.line_chart(chart.tail(252))
    with st.expander('Weekly chart · stage context'):
        weekly=tech['weekly'].Close.to_frame('Weekly close')
        weekly['EMA 8']=tech['weekly'].Close.ewm(span=8,adjust=False).mean()
        weekly['SMA 30']=tech['weekly'].Close.rolling(30).mean()
        st.line_chart(weekly.tail(104))
