"""Color-coded, escaped presentation for daily and intraday liquid leaders."""
from html import escape
import math
import pandas as pd
from rotation_themes import THEMES


def leaders_frame(frame):
    result=frame.drop(columns=['Baseline through'],errors='ignore').copy()
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
            if column=='Symbol':color='#bda16a';background='#2a2418';body=f'<b>{body}</b>'
            elif '%' in column and math.isfinite(number):
                color='#55e1a5' if number>=0 else '#ff7b87'
                background='#102c26' if number>=0 else '#351d29'
                body=f'{number:+.2f}%'
            elif column in ('Session volume','Avg volume 20D','Avg $ volume 50D') and math.isfinite(number):
                color='#77cafa';body=('$' if '$' in column else '')+f'{number/1e6:,.2f}M'
            elif column=='RVOL' and math.isfinite(number):
                color='#d7acff' if number>=1 else '#8f9eaf';body=f'{number:.2f}×'
            elif column in ('Last','Close') and math.isfinite(number):body=f'{number:,.2f}'
            elif column in ('Feed','Quote ET','Source'):color='#bda16a'
            elif not math.isfinite(number) and str(value) in ('None','nan','NaT'):body='—'
            cells.append(f'<td style="color:{color};background:{background}">{body}</td>')
        rows.append('<tr>'+''.join(cells)+'</tr>')
    return '<style>.liquid-leaders th{position:sticky;top:0;z-index:2}.liquid-leaders td:first-child,.liquid-leaders th:first-child{position:sticky;left:0;z-index:3;background:#20231e}.liquid-leaders th:first-child{z-index:4}.liquid-leaders td{font-variant-numeric:tabular-nums}</style><div class="table-scroll"><table class="terminal-table liquid-leaders"><thead><tr>'+heads+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
