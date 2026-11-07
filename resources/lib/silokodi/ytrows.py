# -*- coding: utf-8 -*-
"""Skyline's YouTube page: rows of the YouTube add-on's lists (Recommended,
the subscriptions' newest, Trending, Watch later, History) as cards, fetched
in the background and published, so the page shows at once.

Each list is a run of the YouTube add-on (Files.GetDirectory on its plugin
path): about 4 s to start on a SHIELD before it asks YouTube, and several at
once lock its cache database ("database is locked", retried for up to 10 s),
which is what kept the old page black for 11 s. So: one list at a time, every
REFRESH, while the remote is left alone (IDLE), watching something included:
a list Kodi waits on for 1.5 s brings up its
modal "Loading directory" dialog, which takes the remote's keys. Skyline hides
that dialog while youtube.fetching is set; a key pressed stops the fetch after
the list it's on, and the rest come next time.
"""
import datetime
import json
import re

from . import kodi

ADDON = 'plugin.video.youtube'
YT = 'plugin://%s/' % ADDON
# Videos only, no "Next page" (the rows end, as the app's).
HIDE = 'hide_folders=true&hide_next_page=true'
ROWS = (('recommended', 'Recommended', 'special/recommendations/'),
        ('subscriptions', 'Subscriptions', 'special/my_subscriptions/'),
        ('trending', 'Trending', 'special/popular_right_now/'),
        ('watch_later', 'Watch later', 'special/playlist/WL/'),
        ('history', 'History', 'special/playlist/HL/'),
        ('liked', 'Liked', 'channel/mine/playlist/LL/'))
CARDS = 12  # what Skyline shows on a page other than Home (build_home.OTHER_CARDS)
# Skyline's YouTube Subscriptions screen, drawn from these at once: the
# subscribed channels (their list, a run of its own) and the subscriptions'
# newest videos (Subscriptions' row, more of them).
# YouTube pages it unevenly (36 of 41 on the first, the rest scattered through
# the alphabet on the next): its pages are followed, up to CHANNEL_PAGES.
CHANNELS_PATH = 'subscriptions/list/'
CHANNEL_PAGES = 6
NEXT_PAGE = re.compile(r'[?&]page=\d')
CHANNELS = 100
RECENT = 30
# Channels YouTube leaves out of the add-on's subscriptions (the app has them):
# the add-on's setting youtube_extra_channels, handles (@BrianMenard) or ids,
# their channel found on its YouTube page and kept for EXTRA_TTL; each one's
# newest EXTRA_VIDEOS join the subscriptions' newest.
EXTRA_TTL = 7 * 86400
EXTRA_VIDEOS = 8
HANDLE = re.compile(r'^(@[\w.-]+|UC[\w-]{22})$')
REFRESH = 30 * 60  # seconds between fetches
FIRST_IDLE, IDLE = 30, 60  # seconds without a key before the first fetch, and later ones
# A video's length comes as runtime (duration is a song's).
PROPERTIES = ['title', 'plot', 'studio', 'artist', 'premiered', 'runtime', 'duration', 'art', 'thumbnail', 'file',
              'resume']
VIDEO_ID = re.compile(r'video_id=([\w-]{11})')


def directory(path, properties=PROPERTIES):
    """The YouTube add-on's list at path ([] if it fails, logged)."""
    request = {'jsonrpc': '2.0', 'id': 1, 'method': 'Files.GetDirectory',
               'params': {'directory': path, 'media': 'video', 'properties': properties}}
    import xbmc
    answer = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    if 'error' in answer:
        kodi.log_warning('YouTube rows: %s: %s' % (path.split('?')[0], answer['error']))
        return []
    return (answer.get('result') or {}).get('files') or []


def channel_of(item):
    """The video's channel: the add-on names it as the studio (or the artist)."""
    for field in ('studio', 'artist'):
        names = item.get(field) or []
        if isinstance(names, str):
            names = [names]
        names = [n for n in names if n and n != 'Untitled']
        if names:
            return names[0]
    return ''


def ago(premiered, today):
    """'Today', '3 days ago', '2 weeks ago'... from 'YYYY-MM-DD' (as YouTube's)."""
    match = re.match(r'(\d{4})-(\d\d)-(\d\d)', premiered or '')
    if not match:
        return ''
    days = (today - datetime.date(*(int(part) for part in match.groups()))).days
    if days < 0:
        return ''
    if days == 0:
        return 'Today'
    if days == 1:
        return 'Yesterday'
    for size, unit in ((365, 'year'), (30, 'month'), (7, 'week'), (1, 'day')):
        if days >= size:
            count = days // size
            return '%d %s%s ago' % (count, unit, '' if count == 1 else 's')
    return ''


def length(seconds):
    """'12:34', '1:02:03' (a video's duration), or ''."""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return ''
    if seconds <= 0:
        return ''
    hours, rest = divmod(seconds, 3600)
    return ('%d:%02d:%02d' % (hours, rest // 60, rest % 60)) if hours else '%d:%02d' % (rest // 60, rest % 60)


# Emoji and pictographs: Skyline's font (Inter) has none, so Kodi draws a box
# for each (its "NO GLYPH"): those outside the BMP, the symbol blocks, and the
# joiners and variation selectors that build them.
EMOJI = re.compile('[\U00010000-\U0010FFFF\u2190-\u21FF\u2300-\u23FF\u2460-\u27BF\u2900-\u297F'
                   '\u2B00-\u2BFF\u3030\u303D\u3297\u3299\uFE00-\uFE0F\u200D\u20E3]')


def plain(text):
    """text without emoji, its spaces tidied, line by line."""
    return '\n'.join(' '.join(EMOJI.sub(' ', line).split()) for line in (text or '').split('\n')).strip()


MARKUP = re.compile(r'\[/?(?:B|I|COLOR[^\]]*|UPPERCASE|LOWERCASE|CAPITALIZE|LIGHT)\]')
VIEWS = re.compile(r'([\d.,]+\s*[KMB]?)\s+views?\b', re.I)
# The stats line: "154 Views | 18 Likes", or "5 Likes" (a stream yet to start has no views).
STATS = re.compile(r'^[\d.,]+\s*[KMB]?\s+\w+(?:\s*\|\s*[\d.,]+\s*[KMB]?\s+\w+)*$', re.I)


# A stream's line in the add-on's details: "Upcoming Live @ 21:00", "Premieres
# @ 08/11/2026, 21:00", "Live broadcast @ 19:32" (on air, or ended: an ended
# one has a length).
STREAM = re.compile(r'^(Upcoming Live|Premieres|Live broadcast)\s*@\s*(.+)$')


STARTS_AT = re.compile(r'(?:(\d{1,2})/(\d{1,2})/(\d{4}),\s*)?(\d{1,2}):(\d{2})')
# A stream yet to start: its rows fetched again LIVE_AFTER after its start,
# then every RECHECK while it still says so, for up to WATCH: streams start
# late, and the YouTube add-on keeps a video's details a while.
LIVE_AFTER = 120
RECHECK = 300
WATCH = 3600


def starts_at(status, today):
    """When a 'Starts 21:00' or 'Premieres 08/11/2026, 18:00' begins, in epoch
    seconds (local time), or None."""
    found = STARTS_AT.search(status or '') if status.startswith(('Starts', 'Premieres')) else None
    if not found:
        return None
    day, month, year, hour, minute = found.groups()
    import time
    try:
        date = datetime.date(int(year), int(month), int(day)) if year else today
        return time.mktime(datetime.datetime(date.year, date.month, date.day, int(hour), int(minute)).timetuple())
    except ValueError:
        return None


def next_start(rows, now):
    """The soonest start of the rows' streams still to start (WATCH at most
    overdue), so they're fetched again once it's live, or None."""
    starts = [card.get('yt.starts') for cards in rows.values() if isinstance(cards, list)
              for card in cards if isinstance(card, dict) and card.get('yt.starts')]
    starts = [start for start in starts if start + WATCH > now]
    return min(starts) if starts else None


def stream_due(stream_at, fetched_at, now):
    """Whether a stream's start (next_start) makes the rows due again: from
    LIVE_AFTER after it, RECHECK after the last fetch."""
    return bool(stream_at) and now >= max(stream_at + LIVE_AFTER, fetched_at + RECHECK)


def stream_status(line, has_length):
    """'Starts 21:00', 'Premieres 21:00', 'LIVE', or '' (not a stream's line, or ended)."""
    found = STREAM.match(line)
    if not found:
        return None
    kind, when = found.group(1), found.group(2).strip()
    if kind == 'Live broadcast':
        return '' if has_length else 'LIVE'
    return '%s %s' % ('Starts' if kind == 'Upcoming Live' else 'Premieres', when)


def description(plot, channel, has_length=True):
    """(views, the description, a stream's status) from the YouTube add-on's
    plot: with its "show details" on, it's the channel (bold), its stats ("154
    Views | 18 Likes"), a stream's start (stream_status), the description,
    then "--------" and the video's link."""
    lines = [l.strip() for l in MARKUP.sub('', (plot or '').replace('[CR]', '\n')).split('\n')]
    views, status = '', ''
    kept = []
    for line in lines:
        if not kept:  # the add-on's details come first
            if not line or line == channel:
                continue
            if STATS.match(line):
                found = VIEWS.search(line)
                if found and not views:
                    views = '%s views' % found.group(1).replace(' ', '')
                continue
            stream = stream_status(line, has_length)
            if stream is not None:
                status = stream
                continue
        kept.append(line)
    # The add-on's footer: a rule and the link.
    while kept and (not kept[-1] or kept[-1].startswith('https://youtu.be/') or set(kept[-1]) == {'-'}):
        kept.pop()
    while kept and not kept[0]:
        kept.pop(0)
    return views, '\n'.join(kept), status


def card(item, today):
    """A video's card, as Skyline's published cards (rows.FIELDS)."""
    file = item.get('file') or ''
    match = VIDEO_ID.search(file)
    if not match:
        return None
    video = match.group(1)
    title = plain(item.get('title') or item.get('label') or '')
    channel = plain(channel_of(item))
    duration = length(item.get('runtime') or item.get('duration'))
    views, plot, status = description(item.get('plot'), channel, bool(duration))
    # A stream: when it starts, or that it's on now, for its age.
    when = status or ago(item.get('premiered') or '', today)
    plot = plain(plot)
    art = item.get('art') or {}
    # The card: YouTube's 4:3 picture every video has (its bars cropped by the
    # card); the backdrop: the add-on's 16:9 (hq720), which older videos lack.
    resume = item.get('resume') or {}
    percent = ''
    if resume.get('total') and resume.get('position'):
        percent = str(int(min(100, resume['position'] * 100 / resume['total'])))
    return {'type': 'youtube', 'yt.date': (item.get('premiered') or '')[:10], 'yt.starts': starts_at(status, today), 'label': title, 'card.title': title, 'card.sub': channel,
            'yt.when': when, 'yt.length': duration,  # the Subscriptions screen's (recent_properties)
            'card.wide_sub': '  ·  '.join(part for part in (channel, when) if part),
            'hero.title': title,
            'hero.facts': '  ·  '.join(part for part in (channel, views, when, duration) if part),
            'plot': plot[:600], 'percent': percent,
            'art.landscape': 'https://i.ytimg.com/vi/%s/hqdefault.jpg' % video,
            'art.fanart': art.get('thumb') or art.get('fanart') or item.get('thumbnail') or
            'https://i.ytimg.com/vi/%s/hqdefault.jpg' % video,
            'yt.play': file}


CHANNEL_ID = re.compile(r'/channel/(UC[\w-]{22})/')


def uploads(channel_id):
    """A channel's every upload, newest first: its uploads playlist (UU...).
    The add-on's channel listing leaves out live streams' recordings."""
    return '%splaylist/UU%s/' % (YT, channel_id[2:])


def channel(item):
    """A subscribed channel as the Subscriptions screen lists it: its videos'
    path is its uploads playlist."""
    art = item.get('art') or {}
    path = item.get('file') or ''
    found = CHANNEL_ID.search(path)
    return {'label': plain(item.get('label') or item.get('title') or ''),
            'path': uploads(found.group(1)) if found else path,
            'thumb': art.get('thumb') or art.get('icon') or item.get('thumbnail') or ''}


def extra_handles(setting):
    """The handles (or channel ids) in the setting, one a line or comma separated."""
    return [h for h in (part.strip() for part in re.split(r'[,;\s]+', setting or '')) if HANDLE.match(h)]


def channel_page(handle, get=None):
    """{id, label, thumb} of a channel from its YouTube page, or None."""
    if get is None:
        import requests

        def get(url):
            # YouTube's consent page otherwise, in the EU and the UK.
            response = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'en-GB'},
                                    cookies={'CONSENT': 'YES+1', 'SOCS': 'CAI'})
            response.raise_for_status()
            return response.text
    url = 'https://www.youtube.com/%s' % (handle if handle.startswith('@') else 'channel/' + handle)
    try:
        page = get(url)
    except Exception:  # noqa: BLE001 - a network or HTTP failure: try again next time
        return None

    def meta(pattern):
        found = re.search(pattern, page)
        return found.group(1) if found else ''
    channel_id = meta(r'<meta itemprop="identifier" content="(UC[\w-]{22})"')
    if not channel_id:
        return None
    import html
    return {'id': channel_id, 'label': plain(html.unescape(meta(r'<meta property="og:title" content="([^"]*)"'))),
            'thumb': html.unescape(meta(r'<meta property="og:image" content="([^"]*)"'))}


def extra_channels(setting, path, now, get=None):
    """The setting's channels, found on their pages (kept at path, a JSON
    file, for EXTRA_TTL): [{id, label, thumb}]."""
    kept = {}
    try:
        with open(path, encoding='utf-8') as handle:
            kept = json.load(handle)
    except (OSError, ValueError):
        pass
    found, changed = [], False
    for handle in extra_handles(setting):
        entry = kept.get(handle)
        if not entry or now - entry.get('at', 0) >= EXTRA_TTL:
            channel = channel_page(handle, get)
            if channel:
                entry = dict(channel, at=now)
                kept[handle] = entry
                changed = True
        if entry:
            found.append({key: entry[key] for key in ('id', 'label', 'thumb')})
    if changed:
        import os
        with open(path + '.tmp', 'w', encoding='utf-8') as out:
            json.dump(kept, out)
        os.replace(path + '.tmp', path)
    return found


def newest_first(cards):
    """Cards by their date, newest first (a stable sort: the add-on's order
    within a day stays)."""
    return sorted(cards, key=lambda card: card.get('yt.date') or '', reverse=True)


def gather(today=None, fetch=directory, idle=lambda: True, extras=(), refresh=False):
    """{row: [card]}, one list after another, while idle() (the rows not
    fetched are left out); and, with Subscriptions', 'recent' (more of its
    cards) and 'channels' (the subscribed channels, a list of its own).
    extras (extra_channels): channels to add to both, with their videos.
    refresh: the subscriptions' and extras' lists with fresh details (a
    stream's start: the YouTube add-on keeps a video's details for a month,
    an upcoming stream's "upcoming" too)."""
    today = today or datetime.date.today()
    lists = [(key, '%s%s?%s' % (YT, path, HIDE)) for key, _, path in ROWS]
    lists.insert(2, ('channels', YT + CHANNELS_PATH))  # after Subscriptions' row
    lists[2:2] = [('extra:%s' % extra['id'], '%s?%s' % (uploads(extra['id']), HIDE)) for extra in extras]
    if refresh:
        lists = [(key, path + '&refresh=1' if key == 'subscriptions' or key.startswith('extra:') else path)
                 for key, path in lists]
    rows, logged = {}, False
    for key, path in lists:
        if rows and not idle():
            break  # a key was pressed: the rest next time
        items = fetch(path)
        if key.startswith('extra:'):
            extra = [c for c in (card(item, today) for item in items) if c][:EXTRA_VIDEOS]
            if 'subscriptions' in rows:
                rows['subscriptions'] = newest_first(rows['subscriptions'] + extra)[:CARDS]
                rows['recent'] = newest_first(rows['recent'] + extra)[:RECENT]
            continue
        if key == 'channels':
            found = []
            for _ in range(CHANNEL_PAGES):
                pages = [i for i in items if NEXT_PAGE.search(i.get('file') or '')]
                found += [i for i in items if i not in pages]
                if not pages or not idle():
                    break
                items = fetch(pages[0]['file'])
            found += [{'file': '%schannel/%s/' % (YT, extra['id']), 'label': extra['label'],
                       'art': {'thumb': extra['thumb']}} for extra in extras]
            seen = set()
            rows[key] = sorted((c for c in (channel(item) for item in found)
                                if c['label'] and c['path'] and not (c['path'] in seen or seen.add(c['path']))),
                               key=lambda c: c['label'].lower())[:CHANNELS]
            continue
        if items and not logged:
            logged = True
            sample = dict(items[0])
            sample['plot'] = (sample.get('plot') or '')[:80]
            kodi.log('YouTube rows: an item has %s' % sorted(sample))
        cards = [c for c in (card(item, today) for item in items) if c]
        rows[key] = cards[:CARDS]
        if key == 'subscriptions':
            rows['recent'] = cards[:RECENT + EXTRA_VIDEOS * len(extras)]  # extras may push some out
    return rows


RECENT_FIELDS = (('label', 'card.title'), ('thumb', 'art.landscape'), ('channel', 'card.sub'), ('when', 'yt.when'),
                 ('length', 'yt.length'), ('play', 'yt.play'), ('percent', 'percent'))


def screen_properties(rows):
    """The Subscriptions screen's: silo.youtube.channels.N.* and
    silo.youtube.recent.N.* (empty past the last), for those fetched."""
    props = {}
    if 'channels' in rows:
        found = rows['channels']
        for n in range(1, CHANNELS + 1):
            item = found[n - 1] if n <= len(found) else {}
            for field in ('label', 'thumb', 'path'):
                props['silo.youtube.channels.%d.%s' % (n, field)] = item.get(field, '')
        props['silo.youtube.channels.count'] = str(len(found))
    if 'recent' in rows:
        found = rows['recent']
        for n in range(1, RECENT + 1):
            card = found[n - 1] if n <= len(found) else {}
            for field, source in RECENT_FIELDS:
                props['silo.youtube.recent.%d.%s' % (n, field)] = card.get(source, '')
        props['silo.youtube.recent.count'] = str(len(found))
    return props
