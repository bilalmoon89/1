"""Additional reported revenue comparisons and latest-TTM Rule of 40."""
import pandas as pd
from ticker_check import number


def revenue_comparisons(ticker,statement):
    if statement is None or statement.empty:return {}
    key=next((k for k in ('TotalRevenue','Total Revenue','OperatingRevenue') if k in statement.index),None)
    if key is None:return {}
    dates=sorted(statement.columns,reverse=True)[:5]
    result={str(pd.Timestamp(d).date()):number(statement.loc[key,d]) for d in statement.columns}
    # Yahoo can return additional older observations when the request window ends earlier.
    # Exact fiscal period dates are matched later; annual totals are never treated as quarters.
    for end in {pd.Timestamp(d)-pd.Timedelta(days=330) for d in (dates[0],dates[-1])}:
        payload=ticker._data.get_raw_json(
            f'https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{ticker.ticker}',
            params={'symbol':ticker.ticker,'type':'quarterlyTotalRevenue',
                'period1':int((pd.Timestamp(dates[-1])-pd.Timedelta(days=450)).timestamp()),
                'period2':int(end.timestamp())},timeout=6)
        for item in payload.get('timeseries',{}).get('result',[]) or []:
            for record in item.get('quarterlyTotalRevenue',[]):
                value=number(record.get('reportedValue',{}).get('raw'))
                if value is not None and number(result.get(record['asOfDate'])) is None:result[record['asOfDate']]=value
    return result


def rule_of_40(quarterly,cashflow,comparisons=None,annual=None):
    """Latest reported TTM only. Never move back to an older common period."""
    result={'score':None,'status':'UNAVAILABLE','period':'','growth':None,'margin':None,
        'reason':'Quarterly revenue or cash flow unavailable.','revenue':None,'prior_revenue':None,'fcf':None}
    def dates(frame):
        if frame is None or frame.empty:return []
        return sorted([pd.Timestamp(d) for d in frame.columns if not frame[d].isna().all()],reverse=True)
    income_dates=dates(quarterly);cash_dates=dates(cashflow)
    if not income_dates:return result
    end=income_dates[0];result['period']=str(end.date())
    if not cash_dates or cash_dates[0]!=end:
        result['reason']='Cash flow is not available for the latest reported revenue quarter.'
        return result
    key=next((k for k in ('TotalRevenue','Total Revenue','OperatingRevenue') if k in quarterly.index),None)
    if key is None:return result
    revenues={str(pd.Timestamp(d).date()):number(quarterly.loc[key,d]) for d in quarterly.columns}
    for d,v in (comparisons or {}).items():
        if number(revenues.get(str(pd.Timestamp(d).date()))) is None and number(v) is not None:
            revenues[str(pd.Timestamp(d).date())]=float(v)
    def anchors(offset):
        values=[]
        for months in range(offset,offset+12,3):
            anchor=end-pd.DateOffset(months=months)
            if end.is_month_end:anchor=anchor+pd.offsets.MonthEnd(0)
            values.append(anchor)
        return values
    def matched(mapping,requested):
        values=[];used=set()
        for anchor in requested:
            choices=[(abs((pd.Timestamp(d)-anchor).days),str(d),v) for d,v in mapping.items()
                if str(d) not in used and number(v) is not None and abs((pd.Timestamp(d)-anchor).days)<=14]
            if not choices:return None
            _,date,value=min(choices);used.add(date);values.append(float(value))
        return sum(values)
    current=matched(revenues,anchors(0));prior=matched(revenues,anchors(12))
    # A reported annual total is a valid TTM comparator ONLY when its period end
    # coincides with the required year-earlier TTM end. No fiscal-year fallback.
    if prior is None and annual is not None and not annual.empty:
        akey=next((k for k in ('TotalRevenue','Total Revenue','OperatingRevenue') if k in annual.index),None)
        if akey:
            expected=anchors(12)[0]
            candidates=[(abs((pd.Timestamp(d)-expected).days),number(annual.loc[akey,d]))
                for d in annual.columns if abs((pd.Timestamp(d)-expected).days)<=7 and number(annual.loc[akey,d]) is not None]
            if candidates:prior=min(candidates)[1]
    if current is None or current<=0 or prior is None or prior<=0:
        result['reason']='Four current revenue quarters and an exact year-earlier TTM revenue comparator are required.'
        return result
    def get(date,keys):
        for name in keys:
            if name in cashflow.index:
                value=number(cashflow.loc[name,date])
                if value is not None:return value
        return None
    flows={}
    for date in cashflow.columns:
        value=get(date,('FreeCashFlow','Free Cash Flow'))
        if value is None:
            cfo=get(date,('OperatingCashFlow','Operating Cash Flow'))
            capex=get(date,('CapitalExpenditure','Capital Expenditure'))
            if cfo is not None and capex is not None:value=cfo-abs(capex)
        flows[str(pd.Timestamp(date).date())]=value
    fcf=matched(flows,anchors(0))
    if fcf is None:
        result['reason']='All four cash-flow quarters must match the latest TTM revenue window.'
        return result
    growth=(current/prior-1)*100;margin=fcf/current*100;score=growth+margin
    result.update(score=score,status='≥40' if score>=40 else '<40',growth=growth,margin=margin,
        revenue=current,prior_revenue=prior,fcf=fcf,reason='Latest four reported quarters versus the preceding four quarters.')
    return result


def reconcile_revenue(comparisons,annual):
    """Recover one missing fiscal quarter only when the other three are known."""
    result=dict(comparisons);derived=[]
    if annual is None or annual.empty:return result,derived
    key=next((k for k in ('TotalRevenue','Total Revenue','OperatingRevenue') if k in annual.index),None)
    if key is None:return result,derived
    for end in sorted(annual.columns):
        total=number(annual.loc[key,end])
        prior=next((d for d in annual.columns if 350<=(pd.Timestamp(end)-pd.Timestamp(d)).days<=380),None)
        if total is None or total<=0 or prior is None:continue
        values=[];missing=[];used=set()
        for months in (9,6,3,0):
            anchor=pd.Timestamp(end)-pd.DateOffset(months=months)
            if pd.Timestamp(end).is_month_end:anchor=anchor+pd.offsets.MonthEnd(0)
            matches=[(abs((pd.Timestamp(d)-anchor).days),d,v) for d,v in result.items()
                if d not in used and number(v) is not None and v>0
                and abs((pd.Timestamp(d)-anchor).days)<=14
                and pd.Timestamp(prior)<pd.Timestamp(d)<=pd.Timestamp(end)]
            if matches:
                _,date,value=min(matches);used.add(date);values.append(value)
            else:missing.append(str(anchor.date()))
        if len(values)==3 and len(missing)==1 and total>sum(values):
            result[missing[0]]=total-sum(values);derived.append(missing[0])
    return result,derived
