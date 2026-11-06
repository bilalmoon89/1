"""Standalone single-ticker research page, independent of scanner detection rules."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from liquid_data import bounded_call
from ticker_check import financial_quarters,fundamental_review,technical_review,valuation_history,quote_review,number
from terminal_view import CSS,header,table,e,money
from liquid_table import leaders_table


@st.cache_data(ttl=900,show_spinner=False)
def load_ticker(symbol):
    import yfinance as yf
    ticker=yf.Ticker(symbol.replace('.','-'));errors=[]
    def fetch(label,function,default):
        try:return bounded_call(function,timeout=12)
        except Exception as exc:
            errors.append(f'{label}: {type(exc).__name__}');return default
    history=fetch('Daily prices',lambda:ticker.history(period='5y',auto_adjust=False,actions=True,timeout=8),pd.DataFrame())
    quarters=fetch('Quarterly statements',lambda:ticker.get_income_stmt(freq='quarterly'),pd.DataFrame())
    annual=fetch('Annual statements',lambda:ticker.get_income_stmt(freq='yearly'),pd.DataFrame())
    info=fetch('Current valuation / company profile',ticker.get_info,{})
    from liquid_data import fetch_session_quotes
    try:quote=fetch_session_quotes((symbol,)).get(symbol,{})
    except Exception as exc:
        errors.append(f'TradingView session quote: {type(exc).__name__}');quote={}
    result={'quote':quote,'history':history,'quarters':quarters,'annual':annual,'info':info,'errors':errors,
        'retrieved':datetime.now(ZoneInfo('America/New_York')).isoformat(timespec='seconds')}
    # Do not cache provider failures: the next explicit request can retry immediately.
    if errors:raise PartialTicker(result)
    return result


class PartialTicker(Exception):
    pass


def main():
    st.set_page_config(page_title='Ticker Check | Crescent Trade Terminal — BETA',page_icon='🌙',layout='wide',initial_sidebar_state='collapsed')
    st.markdown(CSS,unsafe_allow_html=True)
    st.markdown(header(source='Yahoo Finance · reported financials'),unsafe_allow_html=True)
    st.markdown('<div class="section-heading">Ticker Check <span>Fundamentals · valuation · trend · conditional trade plan</span></div>',unsafe_allow_html=True)
    with st.form('ticker_lookup'):
        symbol=st.text_input('Ticker',value=st.query_params.get('symbol','AAPL'),placeholder='e.g. NVDA, COHR, LITE').strip().upper()
        run=st.form_submit_button('Check ticker',type='primary',use_container_width=True)
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
    st.subheader(f'{symbol} · {data["info"].get("shortName",symbol)}')
    st.caption(f'Yahoo Finance · retrieved {data["retrieved"]}. Fundamentals are reported fiscal quarters. Technical decisions use completed sessions, not live/after-hours prices. Reload with Check ticker; provider responses are cached for 15 minutes.')
    for error in data['errors']:st.warning(error+' · affected conclusions remain incomplete.')
    quarters=financial_quarters(data['quarters']);fund_state,fund_reason=fundamental_review(quarters,now)
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
    st.markdown(f'<div class="preset-banner"><b>{e(combined)}</b><span>{e(tech["reason"])}</span></div>',unsafe_allow_html=True)
    st.caption('A conditional plan needs a confirmed trigger, current liquidity/volume, market context and a fresh intraday check. It is not an instruction to buy. Stops define invalidation; gaps can fill beyond them.')
    st.subheader('Fundamental review · five reported quarters')
    st.write(f'{fund_state} — {fund_reason}')
    if quarters.empty:st.warning('No reported quarterly statements returned. No generated financials are substituted.')
    else:
        display=quarters.copy().round(2)
        for column in ('Revenue','Net income'):
            display[column]=display[column].map(lambda v:f'{float(v)/1e9:,.2f}B' if number(v) is not None else '—')
        st.caption(f'{len(quarters)}/5 quarters available · reporting currency {data["info"].get("financialCurrency","unverified")}. B = billion currency units. YoY compares matching fiscal periods; missing EPS remains unavailable.')
        st.markdown(leaders_table(display),unsafe_allow_html=True)
    st.subheader('Valuation · current multiples and historical reference')
    info=data['info'];metrics=[]
    for label,key in [('Trailing P/E','trailingPE'),('Forward P/E · analyst estimate','forwardPE'),('Price / sales TTM','priceToSalesTrailing12Months'),('EV / EBITDA','enterpriseToEbitda')]:
        value=number(info.get(key));metrics.append({'Metric':label,'Multiple':round(value,2) if value is not None and value>0 else None})
    st.markdown(table(pd.DataFrame(metrics)),unsafe_allow_html=True)
    valuations,note=valuation_history(data['annual'],data['history'],info)
    if len(valuations)>=2:
        st.write(f'Annual year-end P/E reference: mean {valuations["P/E"].mean():.1f}× · median {valuations["P/E"].median():.1f}× · {len(valuations)} profitable fiscal years.')
        st.markdown(table(valuations.round(2)),unsafe_allow_html=True)
    else:st.info('A reliable historical valuation average is unavailable from the supplied data. Current multiples alone do not establish its usual valuation.')
    st.caption(note+' This is an annual snapshot reference, not the average multiple it traded at every day. Valuation is context, not a standalone cheap/expensive or trade decision.')
    st.subheader('Technical decision · daily and weekly')
    if quote.get('valid'):
        st.markdown(table(pd.DataFrame([{'TradingView last':quote['price'],'Daily SMA200 · current':quote['sma200'],
            'Status':quote['status'],'Updated ET':quote['updated'],'Feed':quote['feed']}]).round(2)),unsafe_allow_html=True)
    else:st.warning(quote['status'])
    if tech['averages'].empty:st.warning(tech['reason']);return
    st.caption(f'Completed daily prices through {tech["asof"]} · last close {money(tech["price"])}. EMA holding requires three closes above plus a recent test within 0.25 ATR; above without a test is labelled untested. Weekly EMA uses completed weekly bars.')
    st.markdown(table(tech['averages']),unsafe_allow_html=True)
    st.caption(f"Weekly calculation through week ending {tech['weekly'].index[-1].date()}" if not tech['weekly'].empty else 'Weekly history unavailable.')
    stage=tech['stage'];st.write('Stage analysis: '+stage['stage']);st.caption(stage['reason'])
    pattern=tech['pattern'];st.write('High tight flag: '+('PREFERRED CANDIDATE' if pattern['found'] else 'NOT DETECTED'));st.caption(pattern['reason'])
    levels=pd.DataFrame([{'Conditional entry':tech.get('entry'),'Structural stop':tech.get('stop'),
        'Observed resistance target':tech.get('target'),'Reward / risk':tech.get('rr'),'ATR 14':tech.get('atr')}]).round(2)
    st.markdown(table(levels),unsafe_allow_html=True)
    st.caption('High tight flag stop: below flag low minus 0.15 ATR. Pullback stop: below the last five-session low minus 0.15 ATR. Trigger: pivot/high plus 0.05 ATR. Unknown structural targets remain blank; a target is never invented to produce a passing reward/risk ratio.')
    chart=tech['frame'].Close.to_frame('Close')
    for period in (9,21,50):chart[f'EMA {period}']=tech['frame'].Close.ewm(span=period,adjust=False).mean()
    chart['SMA 200']=tech['frame'].Close.rolling(200).mean()
    st.line_chart(chart.tail(252))
    with st.expander('Weekly chart · stage context'):
        weekly=tech['weekly'].Close.to_frame('Weekly close')
        weekly['EMA 8']=tech['weekly'].Close.ewm(span=8,adjust=False).mean()
        weekly['SMA 30']=tech['weekly'].Close.rolling(30).mean()
        st.line_chart(weekly.tail(104))
    with st.expander('Research rules and limits'):
        st.write('Fundamental supportive: positive latest revenue YoY, operating margin and net margin, with five reported quarters and a latest period no older than 180 days. This simple operating-quality screen is not a full balance-sheet, dilution, earnings-event or industry-specific assessment.')
        st.write('Stage 2/4: price above/below a 30-week SMA whose four-week slope exceeds +1% / falls below −1%. Flat ±1% slopes following an earlier rise/fall flag provisional Stage 3/1; other cases remain transition/unclear. Stage labels need chart review.')
        st.markdown('[High tight flag reference](https://s3-us-east-2.amazonaws.com/marderreport/wp-content/uploads/2020/05/16121620/Kuhn-The-High-Tight-Flag.pdf) · [Reported financial data](https://ranaroussi.github.io/yfinance/reference/yfinance.financials.html)')
