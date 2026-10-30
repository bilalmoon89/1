"""Small, interactive chart without rebuilding the user's full TradingView terminal."""
from __future__ import annotations
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from crescent_engine import normalise


def candles(frame,plan=None,title='Daily structure',n=85):
    f=normalise(frame).tail(n)
    if f.empty:return None
    fig=make_subplots(rows=2,cols=1,shared_xaxes=True,vertical_spacing=.025,row_heights=[.78,.22])
    fig.add_trace(go.Candlestick(x=f.index,open=f.Open,high=f.High,low=f.Low,close=f.Close,
                                increasing_line_color='#51c3a0',decreasing_line_color='#e7848b',name='Price'),row=1,col=1)
    for span,color in [(9,'#e2ae5e'),(21,'#6db0e6'),(50,'#aa99e0')]:
        fig.add_trace(go.Scatter(x=f.index,y=f.Close.ewm(span=span,adjust=False,min_periods=span).mean(),
                                 mode='lines',line=dict(color=color,width=1.65),name=f'EMA {span}'),row=1,col=1)
    if plan is not None:
        p=plan.to_dict() if hasattr(plan,'to_dict') else plan
        for name,value,color,dash in [('Trigger',p.get('trigger'),'#d6b16f','dash'),('Invalid',p.get('stop'),'#f28b94','dot'),('Next',p.get('target'),'#78c7c7','dot')]:
            if value is not None:
                fig.add_hline(y=float(value),line_color=color,line_dash=dash,line_width=1.1,
                              annotation_text=f'{name} {float(value):.2f}',annotation_font_color=color,
                              row=1,col=1)
    fig.add_trace(go.Bar(x=f.index,y=f.Volume,marker_color='#4f7998',name='Volume',opacity=.7),row=2,col=1)
    fig.update_layout(title=dict(text=title,font=dict(size=15)),height=440,margin=dict(l=10,r=14,t=35,b=5),
                      paper_bgcolor='#0e1d30',plot_bgcolor='#13263c',font=dict(color='#dfe7f3',size=11),
                      xaxis_rangeslider_visible=False,hovermode='x unified',legend=dict(orientation='h',y=1.03,x=0),
                      dragmode='pan',uirevision='cx7')
    fig.update_xaxes(showgrid=False,rangebreaks=[dict(bounds=['sat','mon'])])
    fig.update_yaxes(gridcolor='#31445a',zeroline=False)
    return fig
