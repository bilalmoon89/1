"""Color-coded, escaped presentation for daily and intraday liquid leaders."""
from html import escape
import math
import pandas as pd
from rotation_themes import THEMES


def leaders_frame(frame):
    result=frame.drop(columns=['Baseline through'],errors='ignore').copy()
    # Feed details that are identical on every row are shown once above the table (leaders_summary).
    for column in ('Session','Session status','Feed','Source','As of','Retrieved ET'):
        if len(result)>1 and column in result and result[column].nunique(dropna=False)<=1:result=result.drop(columns=column)
    if 'RS rank' in result and result['RS rank'].isna().all():result=result.drop(columns='RS rank')
    if 'Setup' in result and not result['Setup'].astype(str).str.len().any():result=result.drop(columns='Setup')
    if 'Industry' not in result:result['Industry']='Unverified'
    memberships={}
    for theme in THEMES:
        for symbol in theme['symbols']:
            memberships.setdefault(symbol,[]).append(theme['name'])
    result['Theme']=result['Symbol'].map(lambda s:' · '.join(memberships.get(s,[])) or 'Unmapped')
    columns=[c for c in result.columns if c not in ('Industry','Theme')]
    anchor='RVOL' if 'RVOL' in columns else 'Close' if 'Close' in columns else 'Symbol'
    at=columns.index(anchor)+1
    columns[at:at]=['Industry','Theme']
    lead=[c for c in ('RS rank','Setup') if c in columns]
    columns=['Symbol']+lead+[c for c in columns if c!='Symbol' and c not in lead]
    for column in ('Quote ET','Retrieved ET'):
        if column in result:
            def short_time(value):
                try:
                    stamp=pd.Timestamp(value)
                    if pd.isna(stamp):return '—'
                    if stamp.tzinfo is not None:stamp=stamp.tz_convert('America/New_York')
                    return stamp.strftime('%H:%M:%S')
                except (ValueError,TypeError):return '—'
            result[column]=result[column].map(short_time)
    return result[columns]



def leaders_table(frame):
    heads=''.join(f'<th>{escape(str(c))}</th>' for c in frame.columns)
    rows=[]
    for _,row in frame.iterrows():
        cells=[]
        for column,value in row.items():
            color='#dce5f1';background='transparent';body=escape(str(value))
            try:number=float(value)
            except (ValueError,TypeError):number=float('nan')
            if column=='Symbol':color='#D4A840';background='#221B0E';body=f'<b>{body}</b>'
            elif column=='RS rank':
                if math.isfinite(number):color='#D4A840' if number>=80 else '#dce5f1' if number>=50 else '#8f9eaf';body=f'{number:.0f}'
                else:body='—'
            elif column=='Off 52W high':body=f'{number:.1f}%' if math.isfinite(number) else '—'
            elif column=='Setup':
                color='#45D6A0' if 'TIGHT' in str(value) else '#E3C77E';body=escape(str(value)) if str(value) not in ('','nan','None') else ''
            elif column.endswith(' pp') and math.isfinite(number):
                color='#55e1a5' if number>=0 else '#ff7b87';body=f'{number:+.2f}'
            elif '%' in column and math.isfinite(number):
                color='#55e1a5' if number>=0 else '#ff7b87'
                background='#102c26' if number>=0 else '#351d29'
                body=f'{number:+.2f}%'
            elif (column=='Session volume' or column.startswith(('Avg volume','Avg $ volume'))) and math.isfinite(number):
                color='#77cafa';body=('$' if '$' in column else '')+f'{number/1e6:,.2f}M'
            elif column=='RVOL' and math.isfinite(number):
                color='#d7acff' if number>=1 else '#8f9eaf';body=f'{number:.2f}×'
            elif column in ('Last','Close') and math.isfinite(number):body=f'{number:,.2f}'
            elif column in ('Feed','Quote ET','Source'):color='#bda16a'
            elif not math.isfinite(number) and str(value) in ('None','nan','NaT'):body='—'
            cells.append(f'<td style="color:{color};background:{background}">{body}</td>')
        rows.append('<tr>'+''.join(cells)+'</tr>')
    return '<style>.liquid-leaders th{position:sticky;top:0;z-index:2}.liquid-leaders td:first-child,.liquid-leaders th:first-child{position:sticky;left:0;z-index:3;background:#221B0E}.liquid-leaders th:first-child{z-index:4}.liquid-leaders td{font-variant-numeric:tabular-nums}</style><div class="table-scroll"><table class="terminal-table liquid-leaders"><thead><tr>'+heads+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'


def leaders_summary(frame):
    """One status line (session, feed, quote time) and the industries with the most leaders."""
    if frame is None or frame.empty:return ''
    parts=[]
    for column,label in (('Session','Session'),('As of','Completed session'),('Session status',''),('Feed',''),('Source','')):
        if column in frame and frame[column].nunique(dropna=False)==1:
            value=str(frame[column].iloc[0])
            parts.append(f'{label} <b>{escape(value)}</b>' if label else f'<b>{escape(value)}</b>')
    if 'Quote ET' in frame:
        try:parts.append('latest quote <b>'+pd.to_datetime(frame['Quote ET']).max().strftime('%H:%M:%S')+' ET</b>')
        except (ValueError,TypeError):pass
    html='<div class="lu-status">'+' · '.join(parts)+'</div>' if parts else ''
    if 'Industry' in frame:
        counts=frame.loc[~frame['Industry'].isin(['','Unverified']),'Industry'].value_counts().head(8)
        if len(counts):html+='<div class="lu-groups"><small>Leading groups</small>'+''.join(f'<span>{escape(str(k))} <b>{int(v)}</b></span>' for k,v in counts.items())+'</div>'
    style='<style>.lu-status{font-size:12px;color:#A9B6C6;margin:2px 0 6px}.lu-status b{color:#E1E8F0;font-weight:600}.lu-groups{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:0 0 8px}.lu-groups small{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:#A9B6C6;margin-right:4px}.lu-groups span{font-size:12px;border:1px solid #2C3A4C;border-radius:20px;padding:4px 9px;color:#C9D3DF;background:#121C29}.lu-groups b{color:#D4A840}</style>'
    return style+html if html else ''
