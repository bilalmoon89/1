"""Pure HTML for the Rotation page: theme cards, group strips and tables. No Streamlit."""
from html import escape
import numpy as np
import pandas as pd

PERIODS={'Today':1,'2 days':2,'1 week':5,'1 month':21}
PANELS=(('Leading','Sustained strength',('Leading','Leading + heating'),'#D4A840'),
    ('Heating','New money in the last two sessions',('Heating',),'#45D6A0'),
    ('Cooling','Leaders losing pace',('Cooling',),'#B7A5EF'))

CSS='''<style>
.rot-status{font-size:12px;color:#A9B6C6;margin:0 0 6px}.rot-status b{color:#E1E8F0;font-weight:600}
.rot-strip{display:flex;flex-wrap:wrap;align-items:center;gap:4px;margin:0 0 6px}
.rot-strip>small{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:#A9B6C6;min-width:54px}
.rot-pill{font:500 11.5px var(--sans,sans-serif);border-radius:4px;padding:2px 7px;color:#fff;white-space:nowrap}
.rot-pill b{font-family:var(--mono,monospace);font-weight:600;margin-left:5px}
.rot-panels{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:8px 0}
.rot-panel h3{display:flex;align-items:baseline;gap:7px;font:600 12px var(--sans,sans-serif)!important;letter-spacing:.07em;text-transform:uppercase;margin:0 0 5px!important;padding:0!important}
.rot-panel h3 span{font:600 10.5px var(--mono,monospace);color:#0A101A;border-radius:10px;padding:0 7px}
.rot-panel h3 small{font:400 11px var(--sans,sans-serif);letter-spacing:0;text-transform:none;color:#A9B6C6}
.rot-card{border:1px solid #2C3A4C;border-left:3px solid var(--tone);border-radius:5px;background:var(--fill);padding:5px 9px;margin:0 0 4px}
.rot-top{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.rot-top b{font:600 12.5px var(--sans,sans-serif);color:#F0EDE6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rot-top strong{font:600 13.5px var(--mono,monospace);color:var(--move,var(--tone));white-space:nowrap}
.rot-card small{display:block;margin-top:1px;font-size:11px;line-height:1.35;color:#C9D3DF;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rot-card small i{font-style:normal;font-family:var(--mono,monospace);color:#F0EDE6}
.rot-empty{border:1px dashed #2C3A4C;border-radius:5px;padding:6px 9px;font-size:11.5px;color:#A9B6C6}
@media(max-width:900px){.rot-panels{grid-template-columns:1fr}.rot-card small{white-space:normal}}
</style>'''


def heat(value):
    """Background colour for a percentage: deeper green or red as the move grows."""
    if value is None or pd.isna(value):return '#1B2634'
    value=float(value)
    if abs(value)<.05:return '#16263d'
    if value>0:return '#17463b' if value<2 else '#1d5b46' if value<5 else '#246c50'
    return '#492d38' if value>-2 else '#65303d' if value>-5 else '#7a3442'


def signed(value,unit='%'):
    if value is None or pd.isna(value):return '—'
    return ('↑ ' if value>.05 else '↓ ' if value<-.05 else '→ ')+f'{value:+.2f}{unit}'


def theme_card(row,horizon,leaders=''):
    value=row.get(f'{horizon}D %',np.nan)
    tone='#45D6A0' if pd.notna(value) and value>.05 else '#F47F8E' if pd.notna(value) and value<-.05 else '#C5CEDA'
    state=str(row.get('State',''))
    accent,fill=(('#D4A840','#252116') if state.startswith('Leading') else
                 ('#45D6A0','#102B27') if state=='Heating' else
                 ('#B7A5EF','#231F35') if state=='Cooling' else (tone,heat(value)))
    rs=row.get(f'RS {horizon}D pp',np.nan);breadth=row.get(f'Breadth {horizon}D %',np.nan)
    parts=['RS '+('—' if pd.isna(rs) else f'{rs:+.1f} pp')]
    if pd.notna(breadth):parts.append(f'{breadth:.0f}% rising')
    parts.append(f"{int(row.get('Valid',0))}/{int(row.get('Members',0))}")
    lift=row.get('Rank lift 10D → 2D',np.nan)
    if pd.notna(lift) and abs(lift)>=5:parts.append(f"rank {'↑' if lift>0 else '↓'}{abs(int(lift))}")
    title=f"{row.get('State','')} · {int(row.get('Valid',0))} of {int(row.get('Members',0))} members covered"
    return (f'<article class="rot-card" title="{escape(title)}" style="--fill:{fill};--tone:{accent};--move:{tone}"><div class="rot-top"><b>{escape(str(row.get("Theme","")))}</b>'
        f'<strong>{signed(value)}</strong></div><small>{escape(" · ".join(parts))}'
        +(f' · <i>{escape(leaders)}</i>' if leaders else '')+'</small></article>')


def theme_panels(themes,stocks,catalog,horizon,limit=8):
    """Three columns: Leading, Heating, Cooling. One state per theme, taken from the engine."""
    if themes is None or themes.empty:return ''
    eligible=themes[themes['Rank eligible'].eq(True)]
    ok=stocks[stocks.Data.eq('OK')] if not stocks.empty else stocks
    panels=[]
    for title,note,states,tone in PANELS:
        group=eligible[eligible.State.isin(states)].sort_values(f'RS {horizon}D pp',ascending=title=='Cooling',na_position='last')
        cards=[]
        for _,row in group.head(limit).iterrows():
            members=catalog.get(row.Theme,{}).get('symbols',[])
            best=ok[ok.Symbol.isin(members)].sort_values(f'{horizon}D %',ascending=False).head(3).Symbol if not ok.empty else []
            cards.append(theme_card(row,horizon,' '.join(best)))
        more=f'<div class="rot-empty">+ {len(group)-limit} more in the table view</div>' if len(group)>limit else ''
        panels.append(f'<section class="rot-panel"><h3 style="color:{tone}">{title}<span style="background:{tone}">{len(group)}</span><small>{note}</small></h3>'
            +(''.join(cards) or '<div class="rot-empty">No theme in this state</div>')+more+'</section>')
    return '<div class="rot-panels">'+''.join(panels)+'</div>'


def strip(label,items):
    """Row of heat pills: [(name, percent)], strongest first."""
    items=[(n,v) for n,v in items if v is not None and pd.notna(v)]
    if not items:return ''
    pills=''.join(f'<span class="rot-pill" style="background:{heat(v)}">{escape(str(n))}<b>{v:+.2f}%</b></span>' for n,v in sorted(items,key=lambda x:-x[1]))
    return f'<div class="rot-strip"><small>{escape(label)}</small>{pills}</div>'


def group_returns(themes,horizon):
    """Average return of each market group across its rank-eligible themes."""
    if themes is None or themes.empty:return []
    eligible=themes[themes['Rank eligible'].eq(True)]
    return list(eligible.groupby('Group')[f'{horizon}D %'].mean().items())


def theme_table(themes,horizon):
    """Flat ranking for the table view."""
    if themes is None or themes.empty:return pd.DataFrame()
    f=themes.sort_values(['Rank eligible',f'RS {horizon}D pp'],ascending=[False,False],na_position='last')
    out=pd.DataFrame({'Theme':f.Theme,'Group':f.Group,'State':f.State,
        '1D %':f['1D %'],'2D %':f['2D %'],'5D %':f['5D %'],'21D %':f['21D %'],
        f'RS {horizon}D pp':f[f'RS {horizon}D pp'],
        'Rising':f[f'Breadth {horizon}D %'].map(lambda v:'—' if pd.isna(v) else f'{v:.0f}%'),
        'Covered':f.Valid.astype(int).astype(str)+'/'+f.Members.astype(int).astype(str),
        'Rank vs 10D':f['Rank lift 10D → 2D'].map(lambda v:'—' if pd.isna(v) or v==0 else f"{'↑' if v>0 else '↓'}{abs(int(v))}"),
        'Top movers':f['Top movers']})
    return out.reset_index(drop=True)


def leaders_view(leaders):
    """Member table for one theme, with the columns a trader needs first."""
    if leaders is None or leaders.empty:return pd.DataFrame()
    cols=['Symbol','Review','Setup','Leader score','1D %','5D %','21D %','RS 5D pp','Vs 21 EMA %','Extension ATR','Avg $ volume 20D','Data']
    out=leaders.reindex(columns=[c for c in cols if c in leaders.columns]).copy()
    for c in ('Leader score','Extension ATR'):
        if c in out:out[c]=out[c].map(lambda v:'—' if pd.isna(v) else f'{v:.1f}')
    return out.reset_index(drop=True)
