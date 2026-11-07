# -*- coding: utf-8 -*-
"""Skyline's TV page: My teams, On now and Live sport now, as cards.

The guide and the playlist are the ones Kodi's IPTV Simple add-on reads (its
instance settings say where): the playlist ties each guide id to a channel's
name, and Kodi's channels (JSON-RPC) give that name's channel id, logo, what's
on and when it was last watched.

A programme is live when its title says so (ᴸᶦᵛᵉ, "Live") or the guide marks
it <category>Live</category> (the event entries iptv-playlist writes from an
event channel's name); replays and highlights have neither. A team's match is
its live programmes and events, grouped across channels: one card, kicking off
within MATCH_WINDOW of each other, with every channel showing it, the English
and UHD feeds first.
"""
import datetime
import glob
import io
import os
import re
import xml.etree.ElementTree as ET

from . import kodi

TEAMS_ROW, ON_NOW_ROW, SPORT_ROW = 'teams', 'onnow', 'sport'
ROWS = ((TEAMS_ROW, 'My teams'), (ON_NOW_ROW, 'On now'), (SPORT_ROW, 'Live sport now'))
CARDS = 12
AHEAD = datetime.timedelta(days=7)
MATCH_WINDOW = datetime.timedelta(minutes=75)
LIVE_MARKS = re.compile(r'ᴸᶦᵛᵉ|\bLIVE\b|\bLive\b')
NOT_LIVE = re.compile(r'^(Next|Next Game|Coming up|Highlights|Replay)\b|\b(Highlights|Replay|Classic|Greatest)\b', re.I)
FIXTURE = re.compile(r'\s(v\.?|vs\.?|@)\s', re.I)
PLUGIN = 'plugin://plugin.video.kodiconnectforsilo/'
SETTING = re.compile(r'<setting id="(m3uPathType|m3uPath|m3uUrl|epgPathType|epgPath|epgUrl)"(?: default="true")?>([^<]*)</setting>')


# ----- where Kodi's Live TV comes from -----

def sources(addon_data):
    """(playlist, guide) locations of IPTV Simple's enabled instance with
    channels: a path or a URL each, or None."""
    for path in sorted(glob.glob(os.path.join(addon_data, 'pvr.iptvsimple', 'instance-settings-*.xml'))):
        try:
            with open(path, encoding='utf-8') as handle:
                settings = dict(SETTING.findall(handle.read()))
        except OSError:
            continue
        playlist = settings.get('m3uUrl') if settings.get('m3uPathType') == '1' else settings.get('m3uPath')
        guide = settings.get('epgUrl') if settings.get('epgPathType') == '1' else settings.get('epgPath')
        if playlist:
            return playlist, guide
    return None, None


def read(location, timeout=60):
    """The bytes at a path or URL (http, or Kodi's special:// paths),
    unpacked if gzipped (a provider's xmltv.php)."""
    if not location:
        return b''
    if location.startswith(('http://', 'https://')):
        import requests
        response = requests.get(location, timeout=timeout)
        response.raise_for_status()
        data = response.content
    else:
        import xbmcvfs
        with open(xbmcvfs.translatePath(location), 'rb') as handle:
            data = handle.read()
    if data[:2] == b'\x1f\x8b':
        import gzip
        data = gzip.decompress(data)
    return data


def playlist_names(text):
    """{guide id: channel name} from an M3U playlist."""
    names = {}
    for line in text.splitlines():
        if line.startswith('#EXTINF'):
            match = re.search(r'tvg-id="([^"]*)"', line)
            name = line.rpartition(',')[2].strip()
            if match and match.group(1) and name:
                names.setdefault(match.group(1), name)
    return names


def playlist_groups(text):
    """{channel name: its group} from an M3U playlist (group-title)."""
    groups = {}
    for line in text.splitlines():
        if line.startswith('#EXTINF'):
            match = re.search(r'group-title="([^"]*)"', line)
            name = line.rpartition(',')[2].strip()
            if match and match.group(1) and name:
                groups.setdefault(name, match.group(1))
    return groups


def guide_time(value):
    """An XMLTV time ("20261107150000 +0000") as an aware datetime, or None."""
    try:
        moment = datetime.datetime.strptime(value[:14], '%Y%m%d%H%M%S')
        offset = value[14:].strip() or '+0000'
        sign = -1 if offset.startswith('-') else 1
        delta = datetime.timedelta(hours=int(offset[1:3]), minutes=int(offset[3:5]))
        return moment.replace(tzinfo=datetime.timezone(sign * delta))
    except (ValueError, IndexError, TypeError):
        return None


def live(title, categories):
    """Whether a programme is shown as it happens (not a replay or a trailer)."""
    if NOT_LIVE.search(title or ''):
        return False
    return bool(LIVE_MARKS.search(title or '')) or any((c or '').strip().lower() == 'live' for c in categories)


def programmes(data, names, now, pictures=None):
    """The live programmes of the playlist's channels on now or in AHEAD:
    [{name, title, desc, start, stop, icon}]; and into pictures (if given),
    {channel name: the picture of what it shows now}, live or not."""
    out = []
    for _, element in ET.iterparse(io.BytesIO(data), events=('end',)):
        if element.tag != 'programme':
            continue
        name = names.get(element.get('channel'))
        start, stop = guide_time(element.get('start') or ''), guide_time(element.get('stop') or '')
        title = element.findtext('title') or ''
        if pictures is not None and name and start and stop and start <= now < stop:
            picture = element.find('icon')
            if picture is not None and picture.get('src'):
                pictures[name] = picture.get('src')
        if name and start and stop and stop > now and start < now + AHEAD \
                and live(title, [c.text for c in element.findall('category')]):
            icon = element.find('icon')
            out.append({'name': name, 'title': title, 'desc': element.findtext('desc') or '',
                        'start': start, 'stop': stop, 'icon': icon.get('src') if icon is not None else ''})
        element.clear()
    return out


# ----- matches -----

def team_names(setting):
    """The teams in the add-on's setting: one a line, or comma or semicolon separated."""
    return [t.strip() for t in re.split(r'[,;\n]', setting or '') if t.strip()]


def mentions(title, team, teams=()):
    """Whether title names the team: as a whole word, and not as the start
    of another team's name ("Newcastle" in "Newcastle Jets", or "Newcastle
    United Women"), unless that longer name is one of the teams too."""
    for found in re.finditer(r'(?<!\w)%s(?!\w)' % re.escape(team), title, re.I):
        following = re.match(r'\s+([A-Z][\w.]*)', title[found.end():])
        if following:
            longer = (team + ' ' + following.group(1)).lower()
            if not any(t.lower() == longer or t.lower().startswith(longer + ' ') for t in teams):
                continue  # another team's name
        return True
    return False


def clean(title):
    """A programme's title as a card shows it: no live marks, competition
    prefixes, round or season tails, or a feed's language."""
    text = LIVE_MARKS.sub('', title)
    if ' : ' in text or ': ' in text:
        head, _, tail = text.rpartition(' : ') if ' : ' in text else text.rpartition(': ')
        if FIXTURE.search(tail):
            text = tail
    text = re.sub(r'\s*\((?:MW|GW|Round|R)\s*\d+\)', '', text)
    text = re.sub(r'\s+-\s+[^-]*\d{4}(?:/\d{2,4})?\s*$', '', text)
    return ' '.join(text.split()).strip(' -:')


def feed_rank(name):
    """Lower first: UHD feeds, then English, then other languages last."""
    upper = name.upper()
    rank = 0
    if 'UHD' in upper or '4K' in upper:
        rank -= 2
    if re.search(r'ESPAÑOL|SPANISH|\(ES\)|FRANÇAIS|DEUTSCH|ITALIANO|PORTUGU', upper):
        rank += 5
    if upper.startswith(('NOWHK', 'HK:', 'SG:', 'MY|', 'ASTRO')):
        rank += 1
    return rank


def same_title(entry):
    return re.sub(r'[^a-z0-9]', '', clean(entry['title']).lower())


def group(entries, same=None):
    """Entries for the same match as one: a team's kicking off within
    MATCH_WINDOW of each other, or (same) those with the same key."""
    matches = []
    for entry in sorted(entries, key=lambda e: e['start']):
        for match in matches:
            if (same(match['entries'][0]) == same(entry)) if same else \
                    abs(match['start'] - entry['start']) <= MATCH_WINDOW:
                match['entries'].append(entry)
                break
        else:
            matches.append({'start': entry['start'], 'entries': [entry]})
    for match in matches:
        names = []
        ranked = sorted(match['entries'], key=lambda e: (feed_rank(e['name']), e['start'], e['name']))
        for entry in ranked:
            if entry['name'] not in names:
                names.append(entry['name'])
        match['channels'] = names
        # Its times are the best feed's (an event channel's end is a guess).
        match['start'], match['stop'] = ranked[0]['start'], ranked[0]['stop']
        titles = [clean(e['title']) for e in match['entries']]
        fixtures = [t for t in titles if FIXTURE.search(t)] or titles
        match['title'] = min(fixtures, key=len)
        match['desc'] = next((e['desc'] for e in match['entries'] if e['desc']), '')
        match['icon'] = next((e['icon'] for e in match['entries'] if e['icon']), '')
    return matches


def team_matches(entries, teams):
    """Every match naming any of the teams (a team's names all count as it:
    "Newcastle United", "Newcastle Utd"), kick-off order."""
    return group([e for e in entries if any(mentions(e['title'], t, teams) or mentions(e['desc'], t, teams)
                                            for t in teams)])


# ----- TheSportsDB (sportsdb.py): a card's backdrop -----

def team_in(title, known):
    """The known team (sportsdb.team_record) a title names, the home side's
    first: "Newcastle United @ Fulham" is Fulham's, "Fulham v Newcastle" too."""
    if not known or not title:
        return None
    text = clean(title)
    parts = FIXTURE.split(text, maxsplit=1)
    sides = [text]
    if len(parts) == 3:
        left, sep, right = parts
        sides = [right, left] if sep.strip() == '@' else [left, right]
    every = [name for team in known for name in team['names']]
    for side in sides:
        for team in known:
            if any(mentions(side, name, every) for name in team['names']):
                return team
    return None


def team_art(team, title):
    """A team's backdrop (one of its fanart, the same for a title each time),
    as card fields."""
    import zlib
    fanart = team.get('fanart') or []
    return {'art.fanart': fanart[zlib.crc32(title.encode('utf-8')) % len(fanart)]} if fanart else {}


def league_in(title, leagues):
    """The league (sportsdb.league_record) a title names ("Premier League :
    Fulham v Newcastle"), or None."""
    for league in leagues or ():
        if league['fanart'] and any(re.search(r'(?<!\w)%s(?!\w)' % re.escape(name), title or '', re.I)
                                    for name in league['names']):
            return league
    return None


def backdrop(card, title, known=(), leagues=()):
    """A card's backdrop, best first: a known team's fanart, else the
    programme's own picture, else its league's fanart."""
    team = team_in(title, known)
    if team:
        card.update(team_art(team, title))
    elif not card.get('art.fanart'):
        league = league_in(title, leagues)
        if league:
            import zlib
            card['art.fanart'] = league['fanart'][zlib.crc32(title.encode('utf-8')) % len(league['fanart'])]
    return card


def reminded_near(start, reminded):
    """Whether a reminder is set for a match kicking off at start (seconds):
    a fixture's kick-off and its channel's start may differ a little."""
    for key in reminded:
        try:
            if abs(int(key) - start) <= MATCH_WINDOW.total_seconds():
                return True
        except (TypeError, ValueError):
            continue
    return False


# ----- cards -----

def when(moment, now):
    local = moment.astimezone()
    today = now.astimezone().date()
    if local.date() == today:
        return 'Today %s' % local.strftime('%H:%M')
    if local.date() == today + datetime.timedelta(days=1):
        return 'Tomorrow %s' % local.strftime('%H:%M')
    return local.strftime('%a %d %b %H:%M')


def percent(start, stop, now):
    span = (stop - start).total_seconds()
    return str(int(max(0, min(100, (now - start).total_seconds() * 100 / span)))) if span > 0 else ''


def match_card(match, channels, now, reminded=(), known=(), thumb='', leagues=()):
    """A match's card: watch it when it's on, else a reminder; its backdrop
    (backdrop()), and thumb (its fixture's picture) for a card without one."""
    card = guide_match_card(match, channels, now, reminded)
    if card:
        backdrop(card, match['title'], known, leagues)
        if not card['art.landscape'] and thumb:
            card['art.landscape'] = thumb
    return card


def guide_match_card(match, channels, now, reminded=()):
    ids = [str(channels[n]['channelid']) for n in match['channels'] if n in channels]
    if not ids:
        return None
    on = match['start'] <= now < match['stop']
    count = len(ids)
    feeds = '%d channel%s' % (count, '' if count == 1 else 's')
    key = '%d' % int(match['start'].timestamp())
    if on:
        sub = 'LIVE · %s' % feeds
        action = ('%s?mode=play_channel&id=%s' % (PLUGIN, ids[0]) if count == 1 else
                  '%s?mode=tv_watch&ids=%s' % (PLUGIN, ','.join(ids)))
    else:
        sub = '%s · %s' % (when(match['start'], now), feeds)
        if key in reminded or reminded_near(int(key), reminded):
            sub += ' · reminder set'
        action = '%s?mode=tv_remind&start=%s&ids=%s&title=%s' % (PLUGIN, key, ','.join(ids), quote(match['title']))
    logo = channels[match['channels'][0]].get('icon', '') if match['channels'][0] in channels else ''
    art = match.get('icon') or ''
    # label and type: a skin's list item shows only with them (rows.py's cards
    # have both); Skyline doesn't pass type on for the TV page's cards.
    return {'type': 'tv', 'label': match['title'], 'card.title': match['title'], 'card.sub': sub, 'card.wide_sub': sub,
            'hero.title': match['title'], 'hero.meta': '%s – %s' % (when(match['start'], now),
                                                                   match['stop'].astimezone().strftime('%H:%M')),
            'hero.facts': '  ·  '.join(part for part in (
                '%s – %s' % (when(match['start'], now), match['stop'].astimezone().strftime('%H:%M')),
                match['channels'][0] if match['channels'][0] in channels else '') if part),
            'hero.detail': '  ·  '.join(n for n in match['channels'] if n in channels),
            'plot': match.get('desc', ''), 'percent': percent(match['start'], match['stop'], now) if on else '',
            'art.landscape': art, 'art.fanart': art, 'tv.logo': logo, 'tv.play': action}


def times(on):
    """'17:30 – 20:15' from a Kodi broadcast's start and end (UTC), or ''."""
    try:
        start, stop = (datetime.datetime.strptime(on[key], '%Y-%m-%d %H:%M:%S').replace(tzinfo=datetime.timezone.utc)
                       for key in ('starttime', 'endtime'))
    except (KeyError, TypeError, ValueError):
        return ''
    return '%s – %s' % (start.astimezone().strftime('%H:%M'), stop.astimezone().strftime('%H:%M'))


def channel_card(channel, now, picture='', known=(), leagues=()):
    """A channel's card: what's on it, and its backdrop (backdrop())."""
    card = plain_channel_card(channel, now, picture)
    return backdrop(card, (channel.get('broadcastnow') or {}).get('title') or '', known, leagues)


def fixture_card(fixture, team, now, reminded=(), unknown='channel not known yet'):
    """A known team's next fixture the guide doesn't list yet: a reminder
    (no channels to offer: when it's due, the guide opens)."""
    start = datetime.datetime.fromtimestamp(fixture['start'], datetime.timezone.utc)
    sub = '%s · %s' % (when(start, now), unknown)
    if reminded_near(fixture['start'], reminded):
        sub += ' · reminder set'
    facts = '  ·  '.join(part for part in (when(start, now), fixture.get('league'), fixture.get('venue')) if part)
    card = {'type': 'tv', 'label': fixture['title'], 'card.title': fixture['title'], 'card.sub': sub,
            'card.wide_sub': sub, 'hero.title': fixture['title'], 'hero.meta': when(start, now), 'hero.facts': facts,
            'plot': '', 'percent': '', 'art.landscape': fixture.get('thumb') or '', 'art.fanart': '',
            'tv.logo': team.get('badge') or '',
            'tv.play': '%s?mode=tv_remind&start=%d&ids=&title=%s' % (PLUGIN, fixture['start'], quote(fixture['title']))}
    card.update(team_art(team, fixture['title']))
    return card


def without_marks(title):
    """A programme's title without its live mark ("ᴸᶦᵛᵉ", which Kodi's fonts
    draw badly)."""
    return ' '.join(LIVE_MARKS.sub('', title or '').split())


def plain_channel_card(channel, now, picture=''):
    on = channel.get('broadcastnow') or {}
    title = on.get('title') or ''
    progress = on.get('progresspercentage')
    # The hero: the programme's whole title, as the guide gives it ("Saturday
    # Night Football : Nottingham Forest v Manchester City"), as the TV page's
    # hero shows what's playing (without_marks, the service's tv.playing_title).
    return {'type': 'tv', 'label': channel.get('label') or '', 'card.title': channel.get('label') or '', 'card.sub': title,
            'card.wide_sub': title,
            'hero.title': without_marks(title) or channel.get('label') or '',
            'hero.meta': channel.get('label') or '',
            'hero.facts': '  ·  '.join(part for part in (channel.get('label') or '', times(on)) if part),
            'plot': on.get('plot') or '',
            'percent': str(int(progress)) if progress else '',
            # The programme's picture, else (tv.logo) the channel's logo, which a
            # skin centres: a logo cropped to fill a landscape card is a mess.
            'art.landscape': picture, 'art.fanart': picture, 'tv.logo': channel.get('icon') or '',
            'tv.play': '%s?mode=play_channel&id=%s' % (PLUGIN, channel.get('channelid'))}


def quote(text):
    from urllib.parse import quote as url_quote
    return url_quote(text, safe='')


def rows(channel_list, entries, teams, now, reminded=(), pictures=None, known=(), fixtures=(),
         unknown='channel not known yet', leagues=(), sport_groups=(), groups=None):
    """{row: [card]} for the TV page. known: TheSportsDB's teams (theirs and
    the viewer's); fixtures: [(team, fixture)], the viewer's teams' next ones,
    a card each until the guide lists them. sport_groups: the playlist groups
    (groups: {channel name: group}) Live sport now keeps to, if any; My teams
    looks in every group, so a team's match is never missed."""
    pictures = pictures or {}
    channels = {c.get('label'): c for c in channel_list if not c.get('hidden')}
    window = MATCH_WINDOW.total_seconds()
    team_cards = []
    for match in team_matches(entries, teams):
        start = match['start'].timestamp()
        thumb = next((f.get('thumb') or '' for _, f in fixtures if abs(f['start'] - start) <= window), '')
        card = match_card(match, channels, now, reminded, known, thumb, leagues)
        if card:
            team_cards.append((start, card))
    listed = [start for start, _ in team_cards]
    seen = set()
    for team, fixture in fixtures:
        if fixture['title'] in seen or any(abs(fixture['start'] - start) <= window for start in listed):
            continue
        seen.add(fixture['title'])
        team_cards.append((fixture['start'], fixture_card(fixture, team, now, reminded, unknown)))
    team_cards = [card for _, card in sorted(team_cards, key=lambda pair: pair[0])]
    team_titles = {c['card.title'] for c in team_cards}
    recent = sorted((c for c in channels.values() if c.get('lastplayed')), key=lambda c: c['lastplayed'],
                    reverse=True)
    on_now = [channel_card(c, now, pictures.get(c.get('label'), ''), known, leagues) for c in recent[:CARDS]]
    airing = [e for e in entries if e['start'] <= now < e['stop']]
    if sport_groups:
        wanted = set(sport_groups)
        airing = [e for e in airing if (groups or {}).get(e['name']) in wanted]
    sport = [c for c in (match_card(m, channels, now, known=known, leagues=leagues) for m in group(airing, same_title))
             if c and c['card.title'] not in team_titles]
    sport.sort(key=lambda card: card['card.title'])
    return {TEAMS_ROW: team_cards[:CARDS], ON_NOW_ROW: on_now, SPORT_ROW: sport[:CARDS]}


# ----- gathering it -----

CHANNEL_PROPERTIES = ['channel', 'icon', 'lastplayed', 'hidden', 'broadcastnow']


def kodi_channels():
    """Kodi's TV channels, each's lastplayed when it was last watched (epoch
    seconds, from Kodi's database: JSON-RPC's lacks the preview's fix)."""
    answer = kodi.jsonrpc('PVR.GetChannels', channelgroupid='alltv', properties=CHANNEL_PROPERTIES) or {}
    found = answer.get('channels') or []
    from . import channels
    try:
        watched = channels.last_watched()
    except Exception as error:  # Kodi's own times, then
        kodi.log_warning('TV page: last watched: %s' % error)
        return found
    for channel in found:
        channel['lastplayed'] = watched.get(channel.get('channelid'), 0)
    return found


FIXTURES_AHEAD = 30 * 86400  # a next fixture further off than this isn't shown


def sports(teams, now, path):
    """From TheSportsDB: the setting's teams, their next fixtures ([(team,
    fixture)]) and the leagues it knows; none if it can't be asked."""
    from . import sportsdb
    try:
        db = sportsdb.SportsDB(path, now.timestamp())
        known = db.teams(teams)
        fixtures = [(team, fixture) for team in known for fixture in db.next_fixtures(team)
                    if fixture['start'] < now.timestamp() + FIXTURES_AHEAD]
        leagues = db.leagues()
        db.keep()
        return known, fixtures, leagues
    except Exception as error:  # the rows don't need it
        kodi.log_warning('TheSportsDB: %s' % error)
        return [], [], []


def gather(teams, reminded=(), now=None, sport_groups=()):
    """The TV page's cards, from Kodi's channels and IPTV Simple's playlist and guide."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    channel_list = kodi_channels()
    if not channel_list:
        return {row: [] for row, _ in ROWS}
    playlist, guide = sources(kodi.addon_data_dir())
    entries, pictures, groups = [], {}, {}
    if playlist and guide:
        text = read(playlist).decode('utf-8', 'replace')
        names, groups = playlist_names(text), playlist_groups(text)
        entries = programmes(read(guide), names, now, pictures)
    known, fixtures, leagues = sports(teams, now, os.path.join(kodi.profile_dir(), 'sportsdb.json'))
    return rows(channel_list, entries, teams, now, reminded, pictures, known, fixtures, kodi.string(30228), leagues,
                sport_groups, groups)


def fill_reminders(cards, path=None):
    """A reminder set on a fixture before the guide listed it has no
    channels: given them once a My teams card for it has some."""
    from urllib.parse import parse_qs, urlparse
    reminders = load_reminders(path)
    missing = [start for start, reminder in reminders.items() if not [i for i in reminder.get('ids') or [] if i]]
    if not missing:
        return
    changed = False
    for card in cards.get(TEAMS_ROW) or []:
        query = parse_qs(urlparse(card.get('tv.play') or '').query)
        ids = [i for i in (query.get('ids') or [''])[0].split(',') if i]
        start = (query.get('start') or [''])[0]
        if (query.get('mode') or [''])[0] != 'tv_remind' or not ids or not start.isdigit():
            continue
        for key in missing:
            if key.isdigit() and abs(int(key) - int(start)) <= MATCH_WINDOW.total_seconds():
                reminders[key]['ids'] = ids
                changed = True
    if changed:
        save_reminders(reminders, path)


# ----- reminders and choosing a feed (the plugin's tv_remind and tv_watch) -----

REMINDERS = 'tv_reminders.json'
REMIND_EARLY = 60  # seconds before kick-off
REMIND_LATE = 15 * 60  # still worth saying after kick-off


def reminders_path():
    return os.path.join(kodi.profile_dir(), REMINDERS)


def load_reminders(path=None):
    import json
    try:
        with open(path or reminders_path(), encoding='utf-8') as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def save_reminders(reminders, path=None):
    import json
    path = path or reminders_path()
    with open(path + '.tmp', 'w', encoding='utf-8') as handle:
        json.dump(reminders, handle)
    os.replace(path + '.tmp', path)


def toggle_reminder(start, ids, title, path=None):
    """Set a match's reminder, or remove it if set; whether it's set now."""
    reminders = load_reminders(path)
    # Set on the fixture (TheSportsDB's kick-off), removed from the guide's
    # card (its channel's start), or the other way round: the same match.
    near = [key for key in reminders if key == start or (key.isdigit() and start.isdigit() and
                                                         abs(int(key) - int(start)) <= MATCH_WINDOW.total_seconds())]
    if near:
        for key in near:
            del reminders[key]
        save_reminders(reminders, path)
        return False
    reminders[start] = {'title': title, 'ids': ids}
    save_reminders(reminders, path)
    return True


def due_reminders(now_seconds, path=None):
    """Reminders whose kick-off is now (taken out of the file), and any
    long past (dropped)."""
    reminders = load_reminders(path)
    due, keep = [], {}
    for start, reminder in reminders.items():
        offset = now_seconds - int(start)
        if offset >= -REMIND_EARLY and offset <= REMIND_LATE:
            due.append(dict(reminder, start=start))
        elif offset < -REMIND_EARLY:
            keep[start] = reminder
    if keep != reminders:
        save_reminders(keep, path)
    return due


def channel_names(ids):
    names = []
    for channel_id in ids:
        details = (kodi.jsonrpc('PVR.GetChannelDetails', channelid=int(channel_id), properties=['channel']) or {})
        names.append((details.get('channeldetails') or {}).get('label') or channel_id)
    return names


def watch(ids):
    """Choose one of a match's channels (English and UHD first) and play it."""
    import xbmcgui
    ids = [i for i in ids if i.isdigit()]
    if not ids:
        return
    choice = 0 if len(ids) == 1 else xbmcgui.Dialog().select(kodi.string(30227), channel_names(ids))
    if choice >= 0:
        kodi.jsonrpc('Player.Open', item={'channelid': int(ids[choice])})


FULL_SCREEN = 'pvrplayback.switchtofullscreenchanneltypes'
PREVIEW_WAIT = 10  # seconds, for the channel to start before the setting goes back
# A provider allowing one stream at a time refused one opened 8 s after the
# last stopped ("Error in the HTTP2 framing layer"): the preview waits until
# STREAM_GAP after a stop, and tries again once, RETRY_AFTER later.
STREAM_GAP = 12
RETRY_AFTER = 8


def wait_after_stop(now_seconds, stopped_at):
    """Seconds to wait before opening a stream, given when the last stopped."""
    try:
        return max(0, STREAM_GAP - (now_seconds - int(stopped_at)))
    except (TypeError, ValueError):
        return 0


def last_channel(channel_list):
    """The channel watched most recently, or None."""
    watched = [c for c in channel_list if c.get('lastplayed') and not c.get('hidden')]
    return max(watched, key=lambda c: c['lastplayed']) if watched else None


TV_PAGE_SHOWN = 'Window.IsActive(home) + String.IsEqual(Window(Home).Property(silo.page),tv)'


def preview():
    """Skyline's TV page: the last channel watched, playing in the page's
    preview box. Kodi switches to full screen as a channel starts (its PVR
    setting): off for this one start, as it was once the channel plays."""
    import xbmc
    if xbmc.getCondVisibility('Player.HasMedia'):
        kodi.log('TV preview: something is playing already')
        return
    channel = last_channel(kodi_channels())
    if not channel:
        kodi.log('TV preview: no channel watched yet')
        return
    import time
    monitor = xbmc.Monitor()
    wait = wait_after_stop(time.time(), kodi.get_property('stopped_at'))
    kodi.log('TV preview: %s, after %d s' % (channel.get('label'), wait))
    # waitForAbort(0) waits for ever (no timeout): only when there's a wait.
    if wait and monitor.waitForAbort(wait):
        return
    open_windowed(channel['channelid'], attempts=2)


# ----- the preview following focus -----

FOLLOW_AFTER = 3  # seconds on a card before the preview changes to its channel


def card_channel(action):
    """The channel a TV page card plays (its tv.play): a channel's, or a live
    match's first (its best feed); None for a reminder."""
    from urllib.parse import parse_qs, urlparse
    query = parse_qs(urlparse(action or '').query)
    mode = (query.get('mode') or [''])[0]
    if mode == 'play_channel':
        found = (query.get('id') or [''])[0]
    elif mode == 'tv_watch':
        found = (query.get('ids') or [''])[0].split(',')[0]
    else:
        return None
    return int(found) if found.isdigit() else None


def playing_channel():
    """The Live TV channel playing, by its Kodi id, or None."""
    for player in kodi.jsonrpc('Player.GetActivePlayers') or []:
        item = (kodi.jsonrpc('Player.GetItem', playerid=player['playerid'], properties=[]) or {}).get('item') or {}
        if item.get('type') == 'channel':
            return item.get('id')
    return None


class Follower(object):
    """The TV page's preview follows focus (the service's every second): a
    card rested on for FOLLOW_AFTER plays its channel in the backdrop, as
    Netflix's billboard plays the focused title's trailer."""

    def __init__(self):
        self.channel, self.since, self.switching = None, 0, False

    def focused(self):
        """The focused card's channel, while the TV page's preview plays."""
        import xbmc
        if not xbmc.getCondVisibility(TV_PAGE_SHOWN + ' + VideoPlayer.Content(LiveTV) + !Player.Paused'):
            return None
        row = xbmc.getInfoLabel('Window(Home).Property(silo.row)')
        if not row.isdigit() or not xbmc.getCondVisibility('Control.HasFocus(%s)' % row):
            return None
        return card_channel(xbmc.getInfoLabel('Container(%s).ListItem.Property(home.tv.play)' % row))

    def tick(self, now):
        channel = self.focused()
        if channel != self.channel:
            self.channel, self.since = channel, now
            return
        if channel is None or self.switching or now - self.since < FOLLOW_AFTER:
            return
        self.since = float('inf')  # once for this rest
        import threading
        self.switching = True
        thread = threading.Thread(target=self.switch, args=(channel,), name='silokodi-tv-follow')
        thread.daemon = True
        thread.start()

    def switch(self, channel):
        try:
            if playing_channel() != channel:
                kodi.log('TV preview: following focus to channel %d' % channel)
                from . import channels
                channels.note_preview(channel)  # browsing isn't watching (On now's order)
                open_windowed(channel)
        except Exception as error:  # never let it stop the service
            kodi.log_warning('TV preview follow: %s' % error)
        finally:
            self.switching = False


def open_windowed(channel_id, attempts=1):
    """Play a channel behind the TV page (not full screen: Kodi's PVR setting
    off for this start); True once it shows video."""
    import xbmc
    monitor = xbmc.Monitor()
    # Started: video, from another channel than the one playing before (if any).
    was = xbmc.getInfoLabel('VideoPlayer.ChannelName') if xbmc.getCondVisibility('Player.HasMedia') else ''

    def started():
        return xbmc.getCondVisibility('Player.HasVideo') and (not was or xbmc.getInfoLabel('VideoPlayer.ChannelName') != was)
    before = (kodi.jsonrpc('Settings.GetSettingValue', setting=FULL_SCREEN) or {}).get('value')
    try:
        if before:
            kodi.jsonrpc('Settings.SetSettingValue', setting=FULL_SCREEN, value=0)
        for attempt in range(1, attempts + 1):
            if not xbmc.getCondVisibility(TV_PAGE_SHOWN):
                kodi.log('TV preview: the TV page isn\'t showing any more')
                return False  # the viewer moved on meanwhile
            kodi.jsonrpc('Player.Open', item={'channelid': int(channel_id)})
            for _ in range(PREVIEW_WAIT * 2):
                if started() or monitor.waitForAbort(0.5):
                    break
            if started() or attempt == attempts or monitor.waitForAbort(RETRY_AFTER):
                break
        return started()
    finally:
        if before:
            kodi.jsonrpc('Settings.SetSettingValue', setting=FULL_SCREEN, value=before)


SPORT_GROUPS = 'tv_sport_groups.json'


def load_sport_groups(path=None):
    """The playlist groups Live sport now keeps to ([]: every group)."""
    import json
    try:
        with open(path or os.path.join(kodi.profile_dir(), SPORT_GROUPS), encoding='utf-8') as handle:
            groups = json.load(handle)
        return [g for g in groups if isinstance(g, str)] if isinstance(groups, list) else []
    except (OSError, ValueError):
        return []


def save_sport_groups(groups, path=None):
    import json
    path = path or os.path.join(kodi.profile_dir(), SPORT_GROUPS)
    with open(path + '.tmp', 'w', encoding='utf-8') as handle:
        json.dump(list(groups), handle)
    os.replace(path + '.tmp', path)


def choose_sport_groups():
    """Live sport now's groups, from a tick list of the playlist's (the
    plugin's tv_sport_groups, a settings button)."""
    import xbmcgui
    playlist, _ = sources(kodi.addon_data_dir())
    groups = sorted(set(playlist_groups(read(playlist).decode('utf-8', 'replace')).values())) if playlist else []
    if not groups:
        kodi.notify(kodi.string(30233))
        return
    chosen = set(load_sport_groups())
    picked = xbmcgui.Dialog().multiselect(kodi.string(30229), groups,
                                          preselect=[i for i, g in enumerate(groups) if g in chosen])
    if picked is None:
        return  # cancelled
    save_sport_groups([groups[i] for i in picked])
    kodi.set_property('tv.refresh', '1')
