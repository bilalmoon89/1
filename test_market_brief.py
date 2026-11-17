"""Offline tests for the market brief: RSS parsing and ranking, calendar selection, earnings."""
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import market_brief as mb
from brief_cards import brief_html
from xml.sax.saxutils import escape as xml

ET = ZoneInfo('America/New_York')
NOW = datetime(2026, 11, 17, 17, 0, tzinfo=ET)


def rss(items):
    body = ''.join(
        f'<item><title>{xml(t)} - {xml(s)}</title><link>https://news.google.com/rss/articles/{i}</link>'
        f'<pubDate>{(NOW - timedelta(hours=h)).astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")}</pubDate>'
        f'<description>&lt;ol&gt;&lt;li&gt;x&lt;/li&gt;&lt;/ol&gt;</description><source url="https://x">{xml(s)}</source></item>'
        for i, (t, s, h) in enumerate(items))
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>{body}</channel></rss>'.encode()


def test_rss_parse_strips_source_suffix():
    items = mb.parse_rss(rss([('Dow drops more than 800 points as Nvidia earnings loom', 'CNBC', 2)]), 'Business', 2.5)
    assert items[0]['title'] == 'Dow drops more than 800 points as Nvidia earnings loom'
    assert items[0]['source'] == 'CNBC' and items[0]['position'] == 0 and items[0]['published'] is not None


def test_ranking_clusters_outlets_and_drops_noise():
    business = mb.parse_rss(rss([
        ('Dow sinks 850 points, S&P 500 and Nasdaq drop with focus on Nvidia earnings', 'Yahoo Finance', 1),
        ('How to Tell If It is a Cyberattack or Just an Outage', 'WIRED', 1),
        ('3 Dividend Stocks to Buy Now Before the Fed Cuts Rates', 'The Motley Fool', 1),
        ('Fed Chair Warsh says AI could disappoint the economy', 'CNBC', 3),
    ]), 'Business', 2.5)
    markets = mb.parse_rss(rss([
        ('Dow sinks 850 points as S&P 500 and Nasdaq drop ahead of Nvidia earnings', 'Reuters', 1),
        ('Dow drops 850 points, S&P 500 Nasdaq fall before Nvidia earnings', 'Bloomberg.com', 2),
    ]), 'Markets', 1.0)
    world = mb.parse_rss(rss([('Missile strike hits Kyiv as Russia rejects ceasefire talks', 'AP News', 4),
                              ('Old missile strike story', 'BBC', 40)]), 'World', 2.0)
    top = mb.rank_headlines(business + markets + world, NOW.astimezone(timezone.utc))
    titles = [s['title'] for s in top]
    assert titles[0].startswith('Dow') and top[0]['outlets'] == 3 and top[0]['category'] == 'Markets'
    assert not any('Cyberattack' in t for t in titles)          # not market related
    assert not any('Dividend Stocks' in t for t in titles)      # listicle from a low-tier source
    assert not any('Old missile' in t for t in titles)          # older than 30 hours
    assert {'Fed & rates', 'Geopolitics'} <= {s['category'] for s in top}


def tv(title, when, country='US', importance=1, forecast=None, previous=None, actual=None, unit='%'):
    return {'title': title, 'country': country, 'currency': 'USD', 'importance': importance, 'unit': unit,
            'date': when.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'forecast': forecast, 'previous': previous, 'actual': actual}


def test_calendar_keeps_top_families_one_line_each():
    d = lambda days, h, m=0: (NOW + timedelta(days=days)).replace(hour=h, minute=m)
    payload = {'status': 'ok', 'result': [
        tv('Inflation Rate MoM', d(2, 8, 30), forecast=0.3, previous=0.2),
        tv('Inflation Rate YoY', d(2, 8, 30), forecast=3.1, previous=3.0),
        tv('Core Inflation Rate YoY', d(2, 8, 30), forecast=3.0, previous=3.0),
        tv('FOMC Minutes', d(1, 14), unit=''),
        tv('Non Farm Payrolls', d(3, 8, 30), forecast=120, previous=150, unit='', ),
        tv('Unemployment Rate', d(3, 8, 30), forecast=4.4, previous=4.4),
        tv('Initial Jobless Claims', d(2, 8, 30), forecast=225, previous=230, unit=''),
        tv('NAHB Housing Market Index', d(0, 10), unit=''),
        tv('Building Permits', d(4, 8, 30), importance=0, unit=''),
        tv('Interest Rate Decision', d(5, 7, 45), country='EU', forecast=2.0, previous=2.0),
        tv('Retail Sales MoM', d(-3, 8, 30), forecast=0.4),
        tv('ISM Manufacturing PMI', d(0, 10), forecast=49.0, previous=48.7, actual=49.4, unit=''),
    ]}
    events = mb.top_events(mb.parse_tv_calendar(payload), NOW)
    labels = [e['label'] for e in events]
    assert labels.count('CPI inflation') == 1 and labels.count('Jobs report') == 1
    cpi = next(e for e in events if e['label'] == 'CPI inflation')
    assert cpi['indicator'] == 'Inflation Rate YoY' and cpi['forecast'] == '3.1%' and cpi['previous'] == '3%'
    assert next(e for e in events if e['label'] == 'Jobs report')['indicator'] == 'Non Farm Payrolls'
    assert 'Retail sales' not in labels                         # before today
    assert 'Building Permits' not in labels and 'NAHB Housing Market Index' not in labels
    assert 'ECB rate decision' in labels
    ism = next(e for e in events if e['label'] == 'ISM PMI')
    assert ism['released'] and ism['actual'] == '49.4'
    assert [e['when'] for e in events] == sorted(e['when'] for e in events)
    assert len(mb.top_events(mb.parse_tv_calendar(payload), NOW, limit=3)) == 3
    assert {e['label'] for e in mb.top_events(mb.parse_tv_calendar(payload), NOW, limit=3)} == {'FOMC minutes', 'CPI inflation', 'Jobs report'}


def test_forex_factory_fallback_parser():
    rows = mb.parse_ff_calendar([{'title': 'CPI y/y', 'country': 'USD', 'date': '2026-11-19T08:30:00-05:00',
                                  'impact': 'High', 'forecast': '3.1%', 'previous': '3.0%'}])
    assert rows[0]['country'] == 'US' and rows[0]['importance'] == 1
    assert mb.top_events(rows, NOW)[0]['label'] == 'CPI inflation'


def test_earnings_time_of_day_and_largest_first():
    stamp = lambda days, h, m=0: (NOW + timedelta(days=days)).replace(hour=h, minute=m).timestamp()
    midnight_utc = datetime(2026, 11, 20, tzinfo=timezone.utc).timestamp()
    frame = pd.DataFrame([
        {'name': 'NVDA', 'description': 'NVIDIA Corporation', 'market_cap_basic': 4.6e12, 'earnings_release_next_date': stamp(2, 16, 20),
         'earnings_per_share_forecast_next_fq': 1.26},
        {'name': 'WMT', 'description': 'Walmart Inc.', 'market_cap_basic': 8e11, 'earnings_release_next_date': stamp(2, 7, 0)},
        {'name': 'SMALL', 'description': 'Small Co', 'market_cap_basic': 2.1e10, 'earnings_release_next_date': stamp(1, 16, 5)},
        {'name': 'DATE', 'description': 'Date Only', 'market_cap_basic': 3e11, 'earnings_release_next_date': midnight_utc},
        {'name': 'LATE', 'description': 'Too Late', 'market_cap_basic': 9e11, 'earnings_release_next_date': stamp(20, 16, 5)},
    ])
    rows = mb.top_earnings(frame, NOW, limit=3)
    assert [r['symbol'] for r in rows] == ['WMT', 'NVDA', 'DATE']      # 3 largest in window, by day then time
    assert rows[0]['timing'] == 'Before open' and rows[1]['timing'] == 'After close'
    assert rows[2]['timing'] == '' and str(rows[2]['when'].date()) == '2026-11-20'


def test_brief_html_renders_and_escapes():
    story = {'title': 'Stocks <slide>', 'link': 'https://x/?a=1&b=2', 'source': 'CNBC', 'category': 'Markets',
             'outlets': 3, 'published': None, 'age_hours': 2.0, 'score': 5}
    html = brief_html([story], [], [], NOW, 'note')
    assert 'Stocks &lt;slide&gt;' in html and 'a=1&amp;b=2' in html and '3 outlets' in html
    assert 'Key data' in html and 'Earnings' in html and 'unavailable' in html


def test_reported_today_stays_on_the_list():
    reported = (NOW.replace(hour=16, minute=20)).timestamp()
    next_q = datetime(2027, 2, 25, 21, 20, tzinfo=timezone.utc).timestamp()
    frame = pd.DataFrame([{'name': 'NVDA', 'description': 'NVIDIA', 'market_cap_basic': 4.6e12,
                           'earnings_release_date': reported, 'earnings_release_next_date': next_q,
                           'earnings_per_share_forecast_next_fq': 1.5}])
    rows = mb.top_earnings(pd.concat([frame, frame]), NOW)
    assert len(rows) == 1 and rows[0]['reported'] and rows[0]['timing'] == 'After close' and rows[0]['eps'] is None
    html = brief_html([], [], rows, NOW)
    assert 'After close · reported' in html


def test_category_comes_from_the_shown_headline():
    assert mb.classify('Oil Futures Rise as Middle East Shipping Risks Persist')[0] == 'Energy'
    assert mb.classify('Wall Street falters ahead of Nvidia earnings')[0] == 'Markets'
    assert mb.classify('Nvidia posts Q3 beat; board keeps interim CEO')[0] == 'Companies'
