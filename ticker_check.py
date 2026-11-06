"""Explicit research rules for an individual ticker; no broker/order actions."""
import math
import pandas as pd
from crescent_engine import complete_daily,normalise,_target_from_past
from session_validity import calendar,session_clock


def number(value):
    try:return float(value) if math.isfinite(float(value)) else None
    except (TypeError,ValueError):return None


def financial_quarters(statement):
    if statement is None or statement.empty:return pd.DataFrame()
    rows=[]
    for end in sorted(statement.columns,reverse=True)[:5]:
        def value(*keys):
            for key in keys:
                if key in statement.index:
                    v=number(statement.loc[key,end])
                    if v is not None:return v
            return None
        revenue=value('TotalRevenue','Total Revenue','OperatingRevenue','Operating Revenue')
        gross=value('GrossProfit','Gross Profit')
        operating=value('OperatingIncome','Operating Income')
        net=value('NetIncome','Net Income','NetIncomeCommonStockholders')
        margin=lambda v:v/revenue*100 if v is not None and revenue is not None and revenue>0 else None
        rows.append({'Period end':str(pd.Timestamp(end).date()),'Revenue':revenue,
            'Gross margin %':margin(gross),'Operating margin %':margin(operating),
            'Net margin %':margin(net),'Net income':net,'Diluted EPS':value('DilutedEPS','Diluted EPS')})
    result=pd.DataFrame(rows)
    result['Revenue YoY %']=None
    for i,row in result.iterrows():
        # Fiscal quarter end must match a year-earlier quarter, not an arbitrary fourth row.
        for j,older in result.iterrows():
            days=(pd.Timestamp(row['Period end'])-pd.Timestamp(older['Period end'])).days
            if 350<=days<=380 and number(row.Revenue) is not None and number(older.Revenue) is not None and older.Revenue>0:
                result.loc[i,'Revenue YoY %']=(row.Revenue/older.Revenue-1)*100
    return result


def fundamental_review(quarters,now):
    if len(quarters)<5:return 'INCOMPLETE','Five revenue quarters are required for the requested review.'
    if any(number(v) is None or float(v)<=0 for v in quarters.Revenue):
        return 'INCOMPLETE','All five reported revenue quarters must be available.'
    latest=quarters.iloc[0]
    if (pd.Timestamp(now.date())-pd.Timestamp(latest['Period end'])).days>180:
        return 'INCOMPLETE','Latest financial period is over 180 days old.'
    required=[latest['Revenue YoY %'],latest['Operating margin %'],latest['Net margin %']]
    if any(number(x) is None for x in required):return 'INCOMPLETE','Growth or margin data is missing.'
    if latest['Revenue YoY %']<=0 or latest['Operating margin %']<=0 or latest['Net margin %']<=0:
        return 'CAUTION','Revenue growth and positive operating/net margins do not all pass.'
    return 'SUPPORTIVE','Latest revenue grew year over year; operating and net margins are positive. Valuation is assessed separately.'


def completed_weeks(frame,now):
    f=normalise(frame)
    weekly=f.resample('W-FRI').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
    keep=[];cal=calendar()
    for end in weekly.index:
        start=(pd.Timestamp(end).tz_localize(None).normalize()-pd.Timedelta(days=4))
        sessions=cal.sessions_in_range(start,start+pd.Timedelta(days=4))
        if len(sessions):
            last=sessions[-1]
            keep.append(pd.Timestamp(now)>=cal.session_close(last)+pd.Timedelta(minutes=15) and any(f.index.date==last.date()))
        else:keep.append(False)
    return weekly.loc[keep]


def stage_analysis(weekly):
    if len(weekly)<39:return {'stage':'UNKNOWN','reason':'At least 39 completed weekly bars are required.'}
    close=weekly.Close;ma=close.rolling(30).mean()
    slope=(ma.iloc[-1]/ma.iloc[-5]-1)*100
    prior=(ma.iloc[-5]/ma.iloc[-9]-1)*100
    above=close.iloc[-1]>ma.iloc[-1]
    if slope>1 and above:stage='2 · ADVANCING'
    elif slope< -1 and not above:stage='4 · DECLINING'
    elif abs(slope)<=1 and prior>1:stage='3 · TOPPING CANDIDATE'
    elif abs(slope)<=1 and prior< -1:stage='1 · BASING CANDIDATE'
    else:stage='TRANSITION / UNCLEAR'
    return {'stage':stage,'reason':f'30-week SMA slope over four weeks: {slope:+.2f}%; price is {"above" if above else "below"} it. Rule-based approximation; inspect the weekly chart.',
        'SMA30W':float(ma.iloc[-1]),'slope':float(slope)}


def high_tight_flag(frame):
    f=normalise(frame)
    for length in range(10,26):
        if len(f)<length+40:continue
        flag=f.iloc[-length:];pole=f.iloc[-length-40:-length]
        peak=float(pole.High.max());low=float(pole.loc[:pole.High.idxmax()].Low.min())
        if pole.High.iloc[-5:].max()<peak or low<=0:continue
        advance=(peak/low-1)*100;depth=(1-float(flag.Low.min())/peak)*100
        contraction=flag.Volume.mean()<pole.Volume.tail(10).mean()
        if advance>=100 and 0<=depth<=25 and flag.High.max()<=peak*1.05 and flag.Close.iloc[-1]>=peak*.85 and contraction:
            return {'found':True,'advance':advance,'depth':depth,'days':length,
                'pivot':max(peak,float(flag.High.max())),'low':float(flag.Low.min()),
                'reason':'100%+ pole within 40 sessions; 10–25-session flag, <=25% depth and lower average volume. Candidate, not a confirmed breakout.'}
    return {'found':False,'reason':'No high tight flag satisfies the stated price, duration and volume rules.'}


def technical_review(raw,now):
    f=complete_daily(raw,now)
    if len(f)<200:return {'decision':'NO GO · DATA INCOMPLETE','reason':'200 completed daily bars required.','averages':pd.DataFrame(),'frame':f}
    close=f.Close;price=float(close.iloc[-1]);tr=pd.concat([f.High-f.Low,(f.High-close.shift()).abs(),(f.Low-close.shift()).abs()],axis=1).max(axis=1)
    atr=float(tr.tail(14).mean());checks=[]
    for n in (9,21,50):
        ema=close.ewm(span=n,adjust=False).mean()
        above=price>=ema.iloc[-1]
        held=above and (close.tail(3)>=ema.tail(3)).all() and (f.Low.tail(5)<=ema.tail(5)+.25*atr).any()
        checks.append({'Average':f'Daily EMA {n}','Value':round(ema.iloc[-1],2),'State':'TESTED & HELD' if held else 'ABOVE · UNTESTED' if above else 'BELOW'})
    sma200=float(close.tail(200).mean())
    checks.append({'Average':'Daily SMA 200','Value':round(sma200,2),'State':'ABOVE' if price>=sma200 else 'NO GO · BELOW'})
    weeks=completed_weeks(f,now);stage=stage_analysis(weeks)
    weekly8=float(weeks.Close.ewm(span=8,adjust=False).mean().iloc[-1]) if len(weeks)>=8 else None
    weekly_held=False
    if weekly8:
        wema=weeks.Close.ewm(span=8,adjust=False).mean()
        weekly_held=price>=weekly8 and (weeks.Close.tail(3)>=wema.tail(3)).all() and (weeks.Low.tail(3)<=wema.tail(3)+.25*atr).any()
    checks.append({'Average':'Weekly EMA 8 · completed weeks','Value':round(weekly8,2) if weekly8 else None,
        'State':'TESTED & HELD' if weekly_held else 'ABOVE · UNTESTED' if weekly8 and price>=weekly8 else 'BELOW' if weekly8 else 'UNKNOWN'})
    pattern=high_tight_flag(f);entry=stop=target=rr=None
    expected=session_clock(now)['date']
    clock=session_clock(now)
    if pd.Timestamp(now)<clock['close']+pd.Timedelta(minutes=15):
        expected=calendar().previous_session(pd.Timestamp(expected)).date()
    stale=f.index[-1].date()<expected
    if price<sma200:decision='NO GO · BELOW 200 SMA';reason='Your hard exclusion overrides fundamentals and patterns.'
    elif stale:decision='NO GO · STALE DATA';reason=f'Completed prices end {f.index[-1].date()}; latest session is {expected}.'
    elif not stage['stage'].startswith('2'):decision='WATCH · STAGE NOT CONFIRMED';reason=stage['reason']
    elif not weekly8 or price<weekly8 or any(r['State']=='BELOW' for r in checks[:3]):
        decision='WATCH · SUPPORT NOT ALIGNED';reason='Daily EMAs and weekly 8 EMA are not all supporting price.'
    else:
        ema21=float(close.ewm(span=21,adjust=False).mean().iloc[-1])
        if pattern['found']:entry=pattern['pivot']+.05*atr;stop=pattern['low']-.15*atr
        elif abs(price-ema21)<=1.5*atr and checks[1]['State']=='TESTED & HELD':
            entry=float(f.High.iloc[-1])+.05*atr;stop=float(f.Low.tail(5).min())-.15*atr
        if entry and stop and entry>stop:
            target=_target_from_past(f,entry,1,atr)
            rr=(target-entry)/(entry-stop) if target else None
            decision='CONDITIONAL TRADE PLAN' if rr and rr>=2 and entry-stop<=3*atr else 'WATCH · RISK/REWARD UNVERIFIED'
            reason='Breakout trigger and structural invalidation are conditional. A known resistance target and >=2R are required; no automatic entry.'
        else:decision='WAIT · NO DEFINED SETUP';reason='Trend alone does not establish a low-risk entry or stop.'
    return {'decision':decision,'reason':reason,'price':price,'asof':str(f.index[-1].date()),'averages':pd.DataFrame(checks),
        'stage':stage,'pattern':pattern,'entry':entry,'stop':stop,'target':target,'rr':rr,'atr':atr,'frame':f,'weekly':weeks}


def valuation_history(annual,prices,info):
    """Fiscal-year-end P/E reference, explicitly not a daily historical P/E average."""
    if annual is None or annual.empty or prices.empty:return pd.DataFrame(),'Annual earnings or historical prices unavailable.'
    if info.get('currency')!=info.get('financialCurrency') or not info.get('currency'):
        return pd.DataFrame(),'Price and financial reporting currencies cannot be reconciled.'
    if 'Stock Splits' in prices and (prices['Stock Splits'].fillna(0)!=0).any():
        return pd.DataFrame(),'Historical P/E withheld: stock splits require reconciled EPS/share adjustments.'
    key=next((k for k in ('DilutedEPS','Diluted EPS') if k in annual.index),None)
    if key is None:return pd.DataFrame(),'Annual diluted EPS unavailable.'
    rows=[]
    for end in sorted(annual.columns):
        eps=number(annual.loc[key,end]);date=pd.Timestamp(end).date()
        before=prices[prices.index.date<=date]
        if not eps or eps<=0 or before.empty:continue
        stamp=before.index[-1]
        if (pd.Timestamp(date)-pd.Timestamp(stamp.date())).days>7:continue
        price=float(before.Close.iloc[-1])
        rows.append({'Fiscal year end':str(date),'Price date':str(stamp.date()),'Year-end price':price,'Annual diluted EPS':eps,'P/E':price/eps})
    return pd.DataFrame(rows),'Fiscal-year-end price / reported annual diluted EPS. Restated reporting snapshot; not point-in-time data or a backtest. Loss years omitted.'


def quote_review(quote,now):
    from session_validity import regular_status
    try:
        stamp=pd.Timestamp(float(quote['last_bar_update_time']),unit='s',tz='UTC')
        session=pd.Timestamp(float(quote['time']),unit='s',tz='UTC').tz_convert('America/New_York')
        clock=session_clock(now)
        status=regular_status(stamp,now,max_age_seconds=1800,close_tolerance_seconds=60)
        if session.date()!=clock['date'] or status in ('STALE','UNVERIFIED'):raise ValueError('Quote does not represent the latest valid regular session')
        price=number(quote.get('close'));sma=number(quote.get('SMA200'))
        if price is None or sma is None or price<=0 or sma<=0:raise ValueError('Price or 200 SMA missing')
        feed=str(quote.get('update_mode','Unverified'))
        if feed.startswith('delayed_streaming_'):
            delay=int(feed.rsplit('_',1)[1])//60
            feed=f'{delay} min delayed'
            if status=='CURRENT':status='DELAYED'
        return {'valid':True,'price':price,'sma200':sma,'below200':price<sma,'status':status,
            'updated':stamp.tz_convert('America/New_York').isoformat(timespec='seconds'),'feed':feed}
    except (KeyError,ValueError,TypeError,OverflowError):
        return {'valid':False,'status':'UNAVAILABLE / STALE · fresh intraday check required'}
