"""Market brief: top headlines, key economic releases and the largest upcoming earnings.

Parsing and ranking are pure functions (tested offline); the fetch_* functions do the
network calls and are wrapped in caches by brief_view.py.

Sources
- Headlines: Google News RSS (Business and World top stories plus topic searches).
- Economic calendar: TradingView's public economic calendar feed, with the Forex
  Factory weekly export as a fallback.
- Earnings: TradingView screener (next earnings date, market cap, estimates).
"""
from __future__ import annotations
import math
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from zoneinfo import ZoneInfo
import pandas as pd

ET = ZoneInfo('America/New_York')
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'

# ------------------------------------------------------------------ headlines
GN = 'https://news.google.com/rss'
TAIL = '&hl=en-US&gl=US&ceid=US:en'
# (name, url, weight of a top position in this feed)
FEEDS = (
    ('Business', f'{GN}/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?{TAIL[1:]}', 2.5),
    ('World', f'{GN}/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB?{TAIL[1:]}', 2.0),
    ('Markets', f'{GN}/search?q=%22stock+market%22+OR+%22Wall+Street%22+OR+%22S%26P+500%22+when:1d{TAIL}', 1.0),
    ('Fed', f'{GN}/search?q=%22Federal+Reserve%22+OR+inflation+OR+%22Treasury+yields%22+when:1d{TAIL}', 1.0),
    ('Policy', f'{GN}/search?q=tariffs+OR+sanctions+OR+%22trade+deal%22+OR+%22export+controls%22+when:1d{TAIL}', 1.0),
    ('Conflict', f'{GN}/search?q=war+OR+missile+OR+ceasefire+OR+invasion+OR+airstrike+when:1d{TAIL}', 1.0),
    ('Energy', f'{GN}/search?q=%22oil+prices%22+OR+OPEC+OR+crude+when:1d{TAIL}', 1.0),
)

# (category, weight, pattern), most specific first: the first match names the category.
# A headline needs at least one match to be shown.
TOPICS = (
    ('Fed & rates', 3.0, r"\b(fed|fomc|federal reserve|fed chair\w*|rate cuts?|rate hikes?|interest rates?|treasuries|treasury (?:yields?|bonds?|notes?|bills?|market|auction)|yields?|bond market)\b"),
    ('Macro data', 3.0, r"\b(inflation|cpi|pce|jobs report|payrolls|unemployment|jobless|gdp|recession|retail sales|consumer (?:spending|confidence|sentiment)|ppi|economy|economic growth)\b"),
    ('Geopolitics', 3.0, r"\b(war|missiles?|airstrikes?|attacks?|invasion|ceasefire|troops|military|nuclear|drones?|ukraine|russia|israel|gaza|iran|taiwan|north korea|houthis?|red sea|nato|hezbollah|venezuela)\b"),
    ('Trade & policy', 2.5, r"\b(tariffs?|trade (?:war|deal|talks)|(?:u\.?s\.?|eu|china|chinese|russia|russian|iran|iranian|venezuela|oil|chip) sanctions?|sanctions? (?:on|against) (?:russia|china|iran|venezuela|oil)|export (?:controls?|curbs|rules|ban)|chip rules|shutdown|debt ceiling|white house|congress|senate|supreme court|antitrust|regulators?|executive order)\b"),
    ('Energy', 2.0, r"\b(oil|crude|opec\+?|brent|natural gas|gasoline|lng)\b"),
    ('Markets', 2.0, r"\b(stocks?|stock market|wall street|s&p 500|s&p|dow|nasdaq|sell-?off|rally|record high|bear market|correction|volatility|vix|futures|dollar)\b"),
    ('Companies', 1.5, r"\b(earnings|guidance|revenue|profit|ipo|merger|acquisition|buyout|takeover|layoffs|ceo|nvidia|apple|microsoft|amazon|alphabet|google|meta|tesla|broadcom|openai|anthropic|jpmorgan)\b"),
    ('Crypto', 1.0, r"\b(bitcoin|crypto(?:currency)?|ether(?:eum)?|stablecoins?)\b"),
)
TOPIC_RE = [(name, weight, re.compile(pattern, re.I)) for name, weight, pattern in TOPICS]
NOISE = re.compile(r"(stocks? to buy|should you|best .{0,30}stocks|\btop \d+\b|how to|here's why|is it time to|could make you|millionaire|dividend stocks|\bquiz\b|horoscope|\bopinion\b|\bpodcast\b|\bsponsored\b)", re.I)
TIER1 = ('reuters', 'bloomberg', 'wall street journal', 'wsj', 'financial times', 'cnbc', 'associated press', 'ap news',
         'marketwatch', "barron's", 'new york times', 'axios', 'politico', 'bbc', 'the economist', 'fortune',
         'yahoo finance', 'washington post', 'fox business', 'nikkei', 'the guardian')
LOW = ('motley fool', 'zacks', 'investorplace', '24/7 wall st', 'benzinga', 'seeking alpha', 'gurufocus', 'simply wall st',
       'tipranks', 'marketbeat', 'insidermonkey', 'insider monkey', 'finbold', 'coincentral', 'federal reserve bank', '.gov', 'oilprice')
STOP = set('the a an and or of to in on for with at by from as is are was were be been it its this that after before over '
           'into about amid says said say new more than up down how why what who will would could can may his her their '
           'they we you our us just not out off amid'.split())


def _source_tier(source):
    s = (source or '').lower()
    if any(x in s for x in LOW): return -2.0
    if any(x in s for x in TIER1): return 1.0
    return 0.0


def clean_title(title, source=''):
    """Google News appends ' - Source' to titles; remove it."""
    title = unescape(re.sub(r'\s+', ' ', title or '')).strip()
    if source and title.endswith(' - ' + source):
        return title[:-len(source) - 3].strip()
    head, sep, tail = title.rpartition(' - ')
    return head.strip() if sep and len(tail) <= 60 and len(head) > 20 else title


def parse_rss(content, feed='', weight=1.0):
    """Items from one Google News RSS document: title, link, source, published (UTC), position."""
    import xml.etree.ElementTree as ET_XML
    root = ET_XML.fromstring(content if isinstance(content, (bytes, str)) else bytes(content))
    items = []
    for position, entry in enumerate(root.iter('item')):
        source = (entry.findtext('source') or '').strip()
        published = None
        try:published = parsedate_to_datetime(entry.findtext('pubDate') or '').astimezone(timezone.utc)
        except (TypeError, ValueError, IndexError):pass
        title = clean_title(entry.findtext('title') or '', source)
        link = (entry.findtext('link') or '').strip()
        if not title or not link:continue
        related = (entry.findtext('description') or '').count('<li>')
        items.append({'title': title, 'link': link, 'source': source, 'published': published,
                      'feed': feed, 'position': position, 'weight': weight, 'related': related})
    return items


def _tokens(text):
    return {w for w in re.findall(r"[a-z0-9&']+", text.lower()) if len(w) >= 3 and w not in STOP}


def classify(title):
    """(category, topic score) for a headline; ('', 0) when it is not market related."""
    hits = [(name, weight) for name, weight, rx in TOPIC_RE if rx.search(title)]
    if not hits:return '', 0.0
    return hits[0][0], min(6.0, sum(w for _, w in hits))


def rank_headlines(items, now=None, limit=8, max_age_hours=30, per_category=2):
    """Cluster the same story across feeds and outlets, score it, and return the top stories.

    score = (topic + outlets + feed position + source tier) x recency; listicles are dropped,
    where outlets = 1.5 x log2(distinct sources), recency halves every 10 hours.
    """
    now = now or datetime.now(timezone.utc)
    fresh = [i for i in items if i['published'] is None or (now - i['published']).total_seconds() <= max_age_hours * 3600]
    clusters = []
    for item in sorted(fresh, key=lambda i: (i['position'], -i['weight'])):
        tokens = _tokens(item['title'])
        if len(tokens) < 3:continue
        home = None
        for c in clusters:
            shared = len(tokens & c['tokens'])
            if shared / len(tokens | c['tokens']) >= 0.4 or (shared >= 4 and shared / min(len(tokens), len(c['tokens'])) >= 0.5):
                home = c;break
        if home is None:clusters.append({'tokens': set(tokens), 'items': [item]})
        else:home['items'].append(item);home['tokens'] |= tokens
    stories = []
    for c in clusters:
        lead = max(c['items'], key=lambda i: (_source_tier(i['source']), -i['position']))
        # The headline that is shown must itself be market related; other outlets' wording only adds weight.
        category, own = classify(lead['title'])
        if not own or NOISE.search(lead['title']):continue  # not market related, or a listicle
        topic = max(own, classify(' '.join(i['title'] for i in c['items']))[1])
        sources = {i['source'] for i in c['items'] if i['source']}
        outlets = max(1, len(sources))
        broad = 0.5 if max(i['related'] for i in c['items']) >= 3 else 0.0  # Google lists related coverage
        position = max(i['weight'] * max(0.0, 1 - i['position'] / 40) for i in c['items'])
        times = [i['published'] for i in c['items'] if i['published']]
        latest = max(times) if times else None
        age = (now - latest).total_seconds() / 3600 if latest else 12.0
        decay = max(0.25, 0.5 ** (max(age, 0) / 10))
        score = (topic + 1.5 * math.log2(outlets) + broad + position + _source_tier(lead['source'])) * decay
        stories.append({'title': lead['title'], 'link': lead['link'], 'source': lead['source'], 'category': category,
                        'outlets': len(sources), 'published': latest, 'age_hours': age, 'score': round(score, 2)})
    stories.sort(key=lambda s: -s['score'])
    picked, per = [], {}
    for s in stories:
        if s['score'] <= 0 or per.get(s['category'], 0) >= per_category:continue
        picked.append(s);per[s['category']] = per.get(s['category'], 0) + 1
        if len(picked) >= limit:break
    return picked


def fetch_headlines(timeout=7):
    """All feeds in parallel; returns (items, failed feed names). Never raises."""
    import requests
    from concurrent.futures import ThreadPoolExecutor
    def one(feed):
        name, url, weight = feed
        try:
            r = requests.get(url, timeout=timeout, headers={'User-Agent': UA})
            r.raise_for_status()
            return parse_rss(r.content, name, weight), None
        except Exception:
            return [], name
    with ThreadPoolExecutor(len(FEEDS)) as pool:
        results = list(pool.map(one, FEEDS))
    return [i for items, _ in results for i in items], [n for _, n in results if n]


# ------------------------------------------------------------ economic calendar
# (priority, label, pattern, country). Lower priority = more important.
FAMILIES = (
    (1, 'Fed rate decision', r'(fed|fomc).*rate decision|^fed interest rate|^interest rate decision', 'US'),
    (2, 'Fed press conference', r'fomc press conference|fed press conference', 'US'),
    (3, 'FOMC minutes', r'fomc minutes', 'US'),
    (4, 'Fed Chair speaks', r'fed chair', 'US'),
    (5, 'CPI inflation', r'^(core )?inflation rate|\bcpi\b', 'US'),
    (6, 'Jobs report', r'non ?farm payrolls|^unemployment rate', 'US'),
    (7, 'PCE inflation', r'\bpce\b', 'US'),
    (8, 'GDP', r'\bgdp\b', 'US'),
    (9, 'Retail sales', r'retail sales', 'US'),
    (10, 'PPI', r'\bppi\b|producer price', 'US'),
    (11, 'ISM PMI', r'\bism\b', 'US'),
    (12, 'JOLTS job openings', r'jolts|job openings', 'US'),
    (13, 'Consumer sentiment', r'michigan consumer sentiment|consumer confidence', 'US'),
    (14, 'ECB rate decision', r'interest rate decision|deposit facility rate|main refinancing rate', 'EU'),
    (14, 'BoE rate decision', r'interest rate decision|bank rate', 'GB'),
    (14, 'BoJ rate decision', r'interest rate decision|policy rate', 'JP'),
    (15, 'Jobless claims', r'initial jobless claims', 'US'),
)
FAMILY_RE = [(p, label, re.compile(rx, re.I), country) for p, label, rx, country in FAMILIES]
# Preferred headline indicator inside a family (first match wins).
LEAD_RE = re.compile(r'^inflation rate yoy|non ?farm payrolls|^core pce price index yoy|^core pce prices? yoy|^pce price index yoy|^gdp growth rate|^retail sales mom|^ppi mom|ism manufacturing pmi|ism services pmi|fomc minutes|rate decision', re.I)
CURRENCY_COUNTRY = {'USD': 'US', 'EUR': 'EU', 'GBP': 'GB', 'JPY': 'JP'}
SKIP_RE = re.compile(r'cleveland|atlanta fed|dallas fed|kansas|richmond|philadelphia fed|chicago fed|ny fed|nahb|auction|redbook|eia|api crude|baker hughes|cftc|speech(?!.*chair)', re.I)


def family(title, country):
    for priority, label, rx, where in FAMILY_RE:
        if where == country and rx.search(title or ''):return priority, label
    return None


def _fmt(value, unit='', scale=''):
    if value is None or (isinstance(value, float) and math.isnan(value)) or value == '':return ''
    if isinstance(value, (int, float)):
        text = f'{value:,.2f}'.rstrip('0').rstrip('.') if abs(value) < 1000 else f'{value:,.0f}'
    else:text = str(value).strip()
    if unit == '%' and not text.endswith('%'):text += '%'
    elif scale and not text.endswith(scale):text += scale
    return text


def parse_tv_calendar(payload):
    """TradingView calendar JSON -> rows: when (ET), country, title, importance, actual, forecast, previous."""
    rows = []
    for e in (payload or {}).get('result', []) or []:
        try:when = datetime.fromisoformat(str(e['date']).replace('Z', '+00:00')).astimezone(ET)
        except (KeyError, ValueError):continue
        country = e.get('country') or CURRENCY_COUNTRY.get(e.get('currency', ''), '')
        unit, scale = e.get('unit') or '', e.get('scale') or ''
        rows.append({'when': when, 'country': country, 'title': str(e.get('title', '')).strip(),
                     'importance': int(e.get('importance') or 0),
                     'actual': _fmt(e.get('actual'), unit, scale), 'forecast': _fmt(e.get('forecast'), unit, scale),
                     'previous': _fmt(e.get('previous'), unit, scale), 'source': 'TradingView'})
    return rows


def parse_ff_calendar(payload):
    """Forex Factory weekly export (fallback): title, country (currency), date, impact, forecast, previous."""
    rows = []
    for e in payload or []:
        try:when = datetime.fromisoformat(str(e['date'])).astimezone(ET)
        except (KeyError, ValueError):continue
        rows.append({'when': when, 'country': CURRENCY_COUNTRY.get(e.get('country', ''), e.get('country', '')),
                     'title': str(e.get('title', '')).strip(), 'importance': 1 if e.get('impact') == 'High' else 0,
                     'actual': str(e.get('actual') or ''), 'forecast': str(e.get('forecast') or ''),
                     'previous': str(e.get('previous') or ''), 'source': 'Forex Factory'})
    return rows


def top_events(rows, now=None, days=14, limit=8):
    """The most important releases from today (ET) to `days` ahead, one line per family and day."""
    now = (now or datetime.now(ET)).astimezone(ET)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=days + 1)
    groups = {}
    for r in rows:
        if not (start <= r['when'] < end) or SKIP_RE.search(r['title']):continue
        match = family(r['title'], r['country'])
        if match is None:
            if r['country'] != 'US' or r['importance'] < 1:continue
            match = (20, r['title'])
        elif r['importance'] < 0:continue
        key = (match[1], r['when'].date())
        g = groups.setdefault(key, {'priority': match[0], 'label': match[1], 'when': r['when'], 'country': r['country'], 'rows': []})
        g['rows'].append(r);g['when'] = min(g['when'], r['when'])
    out = []
    for g in groups.values():
        lead = (next((r for r in g['rows'] if LEAD_RE.search(r['title'])), None)
                or next((r for r in g['rows'] if r['forecast']), None) or min(g['rows'], key=lambda r: len(r['title'])))
        out.append({'label': g['label'], 'when': g['when'], 'country': g['country'], 'priority': g['priority'],
                    'indicator': lead['title'], 'actual': lead['actual'], 'forecast': lead['forecast'],
                    'previous': lead['previous'], 'released': g['when'] <= now, 'source': lead['source']})
    chosen = sorted(out, key=lambda x: (x['priority'], x['when']))[:limit]
    return sorted(chosen, key=lambda x: x['when'])


def fetch_calendar(now=None, days=15, timeout=8):
    """TradingView calendar for the window; Forex Factory this-week export if it fails. Raises if both fail."""
    import requests
    now = now or datetime.now(timezone.utc)
    start = (now - timedelta(days=1)).astimezone(timezone.utc).strftime('%Y-%m-%dT00:00:00.000Z')
    stop = (now + timedelta(days=days + 1)).astimezone(timezone.utc).strftime('%Y-%m-%dT00:00:00.000Z')
    errors = []
    try:
        r = requests.get('https://economic-calendar.tradingview.com/events', timeout=timeout,
            params={'from': start, 'to': stop, 'countries': 'US,EU,GB,JP'},
            headers={'Origin': 'https://www.tradingview.com', 'Referer': 'https://www.tradingview.com/',
                     'User-Agent': UA, 'Accept': 'application/json'})
        r.raise_for_status()
        payload = r.json()
        if payload.get('status') == 'ok' and payload.get('result'):return parse_tv_calendar(payload), 'TradingView'
        errors.append('TradingView: empty response')
    except Exception as exc:
        errors.append(f'TradingView: {type(exc).__name__}')
    try:
        r = requests.get('https://nfs.faireconomy.media/ff_calendar_thisweek.json', timeout=timeout, headers={'User-Agent': UA})
        r.raise_for_status()
        return parse_ff_calendar(r.json()), 'Forex Factory (this week only)'
    except Exception as exc:
        errors.append(f'Forex Factory: {type(exc).__name__}')
    raise RuntimeError('; '.join(errors))


# ---------------------------------------------------------------------- earnings
EARNINGS_FIELDS = ('name', 'description', 'market_cap_basic', 'earnings_release_next_date', 'earnings_release_date',
                   'earnings_per_share_forecast_next_fq', 'revenue_forecast_next_fq')


def release_time(stamp):
    """(ET datetime, 'Before open' | 'After close' | '') from a unix timestamp.
    A timestamp at exactly 00:00 UTC carries a date only, so no time of day is claimed."""
    if stamp is None or (isinstance(stamp, float) and math.isnan(stamp)):return None, ''
    utc = datetime.fromtimestamp(float(stamp), timezone.utc)
    if utc.hour == 0 and utc.minute == 0:return utc.replace(tzinfo=ET, hour=12), ''
    et = utc.astimezone(ET)
    if et.hour < 9 or (et.hour == 9 and et.minute < 30):return et, 'Before open'
    if et.hour >= 16:return et, 'After close'
    return et, ''


def top_earnings(frame, now=None, days=10, limit=12):
    """Largest companies by market cap reporting from today (ET) through `days` ahead.
    A company that already reported today (its next date has rolled forward) is kept, marked reported."""
    if frame is None or len(frame) == 0:return []
    now = (now or datetime.now(ET)).astimezone(ET)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=days + 1)
    rows, seen = [], set()
    for _, r in frame.iterrows():
        symbol = str(r.get('name', '')).upper()
        if symbol in seen:continue
        recent, recent_timing = release_time(r.get('earnings_release_date'))
        when, timing = release_time(r.get('earnings_release_next_date'))
        reported = recent is not None and recent.date() == now.date() and recent <= now + timedelta(hours=1)
        if reported:when, timing = recent, recent_timing
        elif when is None or not (start <= when < end):continue
        seen.add(symbol)
        rows.append({'symbol': symbol, 'company': str(r.get('description') or ''), 'when': when, 'timing': timing,
                     'reported': reported, 'market_cap': r.get('market_cap_basic'),
                     'eps': r.get('earnings_per_share_forecast_next_fq') if not reported else None,
                     'revenue': r.get('revenue_forecast_next_fq')})
    rows = sorted(rows, key=lambda x: -(x['market_cap'] or 0))[:limit]
    return sorted(rows, key=lambda x: (x['when'].date(), x['timing'] != 'Before open', -(x['market_cap'] or 0)))


def fetch_earnings(now=None, days=10, min_market_cap=20e9, timeout=12):
    """Upcoming reports plus reports already out today. Raises on failure so it is not cached."""
    from tradingview_screener import Query, col
    now = now or datetime.now(timezone.utc)
    def query(field, lo, hi):
        _, frame = (Query().set_markets('america').select(*EARNINGS_FIELDS)
            .where(col('type') == 'stock', col('is_primary') == True, col('market_cap_basic') > min_market_cap,
                   col(field).between(int(lo.timestamp()), int(hi.timestamp())))
            .order_by('market_cap_basic', ascending=False).limit(60).get_scanner_data(timeout=timeout))
        return frame
    upcoming = query('earnings_release_next_date', now - timedelta(days=1), now + timedelta(days=days + 1))
    try:today = query('earnings_release_date', now - timedelta(hours=30), now + timedelta(hours=2))
    except Exception:today = None
    frames = [f for f in (today, upcoming) if f is not None and len(f)]
    return pd.concat(frames, ignore_index=True) if frames else upcoming
