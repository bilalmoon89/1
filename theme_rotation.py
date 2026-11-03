"""Coverage-aware observations of the existing curated baskets; no new universe."""
import pandas as pd
from crescent_engine import snapshot, finite
from rotation_themes import THEMES


def theme_symbols(loaded):
    loaded=set(loaded)
    out=set()
    for theme in THEMES:
        members=loaded.intersection(theme['symbols'])
        if len(members)>=2:out.update(members)
    return sorted(out)


def analyze_rotation(daily,intraday,themes=None):
    metrics={s:snapshot(f) for s,f in daily.items()}
    spy=metrics.get('SPY')
    if not spy:return pd.DataFrame()
    live=intraday.get('rows',pd.DataFrame())
    current={r['Symbol']:r for _,r in live.iterrows()} if not live.empty else {}
    output=[]
    for theme in themes or THEMES:
        members=list(dict.fromkeys(theme['symbols']))
        observed=[s for s in members if metrics.get(s) and metrics[s]['asof']==spy['asof']]
        if len(observed)<2:continue
        session=[current[s] for s in observed if s in current and finite(current[s]['Vs SPY pp'])]
        coverage=len(observed)/len(members)
        full=len(observed)>=3 and coverage>=.70
        session_full=len(session)>=3 and len(session)/len(members)>=.70
        rs5=sum(metrics[s]['r5']-spy['r5'] for s in observed)/len(observed)
        rs21=sum(metrics[s]['r21']-spy['r21'] for s in observed)/len(observed)
        lifecycle='LEADING' if rs5>0 and rs21>0 else 'EMERGING' if rs5>0 else 'COOLING' if rs21>0 else 'LAGGING'
        vwap=[r for r in session if finite(r['Vs VWAP %'])]
        output.append({'Theme':theme['name'],'Group':theme['group'],
            'Coverage':f'{len(observed)}/{len(members)}','Coverage %':round(coverage*100),
            'Basket':'BROAD COVERAGE' if full else 'PARTIAL BASKET',
            'Lifecycle':lifecycle if full else 'PARTIAL / '+lifecycle,
            'Today %':round(sum(r['Today %'] for r in session)/len(session),2) if session else None,
            'Today vs SPY pp':round(sum(r['Vs SPY pp'] for r in session)/len(session),2) if session else None,
            'Session members':f'{len(session)}/{len(members)}',
            'Session coverage':'BROAD' if session_full else 'PARTIAL' if session else 'UNAVAILABLE',
            'Above VWAP':f'{sum(r["Vs VWAP %"]>0 for r in vwap)}/{len(vwap)}' if vwap else '—',
            'RS 5D pp':round(rs5,2),'RS 21D pp':round(rs21,2),
            'Members':', '.join(observed),'Session status':intraday.get('status','UNAVAILABLE')})
    if not output:return pd.DataFrame()
    return pd.DataFrame(output).sort_values('Today vs SPY pp',ascending=False,na_position='last').reset_index(drop=True)
