"""Additional reported revenue comparisons and annual Rule of 40 inputs."""
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


def rule_of_40(annual,cashflow):
    unavailable={'score':None,'status':'UNAVAILABLE','period':'','growth':None,'margin':None}
    if annual is None or cashflow is None or annual.empty or cashflow.empty:return unavailable
    revenue_key=next((k for k in ('TotalRevenue','Total Revenue','OperatingRevenue') if k in annual.index),None)
    if not revenue_key:return unavailable
    def get(frame,end,keys):
        for key in keys:
            if key in frame.index:
                value=number(frame.loc[key,end])
                if value is not None:return value
        return None
    for end in sorted(set(annual.columns)&set(cashflow.columns),reverse=True):
        revenue=get(annual,end,(revenue_key,))
        if revenue is None or revenue<=0:continue
        prior=next((d for d in annual.columns if 350<=(pd.Timestamp(end)-pd.Timestamp(d)).days<=380),None)
        if prior is None:continue
        old=get(annual,prior,(revenue_key,))
        fcf=get(cashflow,end,('FreeCashFlow','Free Cash Flow'))
        if fcf is None:
            cfo=get(cashflow,end,('OperatingCashFlow','Operating Cash Flow'))
            capex=get(cashflow,end,('CapitalExpenditure','Capital Expenditure'))
            if cfo is not None and capex is not None:fcf=cfo-abs(capex)
        if old is None or old<=0 or fcf is None:continue
        growth=(revenue/old-1)*100;margin=fcf/revenue*100;score=growth+margin
        return {'score':score,'status':'≥40' if score>=40 else '<40','period':str(pd.Timestamp(end).date()),
            'growth':growth,'margin':margin}
    return unavailable


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
