# -*- coding: utf-8 -*-
"""BBC iPlayer on Skyline's TV page and in its guide, played by the iPlayer WWW
add-on (plugin.video.iplayerwww, from Kodi's repository).

This add-on only reads iPlayer's public catalogue (ibl.api.bbc.co.uk: what is
on and its pictures, as the playlist's guide pictures do) and hands playback to
iPlayer WWW, which fetches the stream: it never asks the BBC for a stream itself.

- Highlights: Match of the Day's highlights of each Premier League match
  ("Newcastle United v Arsenal Highlights"), on iPlayer for about a week; the
  user's teams' (the My teams setting) and every match's, newest first.
- Continue watching: the BBC account's list, as iPlayer WWW reads it signed in.
- Watch on iPlayer: a BBC programme the guide has without catch-up, found on
  iPlayer by its channel and start time.
"""
import datetime
import re
import time
from urllib.parse import urlencode

from . import kodi

ADDON = 'plugin.video.iplayerwww'
PLUGIN = 'plugin://plugin.video.kodiconnectforsilo/'
IBL = 'https://ibl.api.bbc.co.uk/ibl/v1/'
MATCH_OF_THE_DAY = 'b007t9y1'
HIGHLIGHTS = re.compile(r'^(?P<match>.+?)\s+Highlights$', re.I)
PICTURE = '832x468'
# The guide's BBC channels (Kodi's names) and the BBC's ids for their schedules.
CHANNELS = {'BBC One': 'bbc_one_london', 'BBC Two': 'bbc_two_england', 'BBC News': 'bbc_news24',
            'BBC Three': 'bbc_three', 'BBC Four': 'bbc_four'}
NEAR = 300  # seconds between the guide's start and the BBC's
KEEP = 15 * 60
AGENT = {'User-Agent': 'Mozilla/5.0 (Linux; Kodi) KodiConnectForSilo'}
CACHE = {}


def installed():
    """Whether iPlayer WWW is installed and enabled (it plays everything here)."""
    try:
        details = kodi.jsonrpc('Addons.GetAddonDetails', addonid=ADDON, properties=['enabled']) or {}
    except Exception:
        return False
    return bool((details.get('addon') or {}).get('enabled'))


def get(path, **query):
    """An ibl answer, kept KEEP; {} when it can't be read."""
    import requests
    url = IBL + path + ('?' + urlencode(query) if query else '')
    kept = CACHE.get(url)
    if kept and time.time() - kept[0] < KEEP:
        return kept[1]
    try:
        answer = requests.get(url, headers=AGENT, timeout=15).json()
    except Exception as error:
        kodi.log_warning('iPlayer: %s: %s' % (path, error))
        answer = {}
    CACHE[url] = (time.time(), answer)
    return answer


def picture(images):
    """An ibl picture (a "{recipe}" address) at the cards' size."""
    found = (images or {}).get('standard') or (images or {}).get('promotional') or ''
    return found.replace('{recipe}', PICTURE) if '{recipe}' in found else found


def episode_path(pid, title, image='', plot=''):
    """iPlayer WWW's own address for an episode, as its lists give it (mode 202
    plays it at once, as its autoplay setting does)."""
    return 'plugin://%s/?%s' % (ADDON, urlencode([
        ('url', 'https://www.bbc.co.uk/iplayer/episode/%s' % pid), ('mode', '202'), ('name', title),
        ('iconimage', image), ('description', plot), ('subtitles_url', ''), ('episode_id', ''),
        ('stream_id', ''), ('resume_time', ''), ('total_time', ''), ('replay_chan_id', '')]))


def play_command(path):
    """This add-on's mode that plays an iPlayer WWW address (cards run it with
    RunPlugin; iPlayer WWW's items need playing, not running)."""
    return '%s?%s' % (PLUGIN, urlencode({'mode': 'iplayer', 'path': path}))


def released(value):
    """ibl's "21 Nov 2026" as a date, or None."""
    try:
        return datetime.datetime.strptime(value or '', '%d %b %Y').date()
    except ValueError:
        return None


def highlights():
    """Match of the Day's match highlights on iPlayer, newest first:
    [{'match', 'pid', 'picture', 'plot', 'day', 'length', 'until'}]."""
    found = []
    elements = (get('programmes/%s/episodes' % MATCH_OF_THE_DAY, per_page=40, rights='web')
                .get('programme_episodes') or {}).get('elements') or []
    for episode in elements:
        match = HIGHLIGHTS.match(episode.get('subtitle') or '')
        if not match or not episode.get('id'):
            continue
        version = (episode.get('versions') or [{}])[0]
        found.append({'match': match.group('match'), 'pid': episode['id'], 'picture': picture(episode.get('images')),
                      'plot': (episode.get('synopses') or {}).get('small') or '',
                      'day': released(episode.get('release_date')),
                      'length': ((version.get('duration') or {}).get('text') or ''),
                      'until': ((version.get('availability') or {}).get('end') or '')})
    return found


def highlight_card(item, today=None):
    today = today or datetime.date.today()
    day = item['day']
    when = '' if day is None else 'Today' if day == today else 'Yesterday' if day == today - datetime.timedelta(1) \
        else day.strftime('%a %-d %b')
    sub = '  ·  '.join(part for part in ('Match of the Day', when) if part)
    path = episode_path(item['pid'], 'Match of the Day - %s Highlights' % item['match'], item['picture'], item['plot'])
    return {'type': 'tv', 'label': item['match'], 'card.title': item['match'], 'card.sub': sub, 'card.wide_sub': sub,
            'hero.title': item['match'], 'hero.meta': 'BBC iPlayer', 'hero.facts': '  ·  '.join(
                part for part in ('Match of the Day highlights', item['length'], when) if part),
            'plot': item['plot'], 'percent': '', 'left': item['length'] or 'Highlights',
            'art.landscape': item['picture'], 'art.fanart': item['picture'], 'tv.logo': '',
            'tv.play': play_command(path)}


def team_highlights(items, teams, mentions):
    """The teams' matches among items (mentions: tvrows.mentions)."""
    return [i for i in items if any(mentions(i['match'], team, teams) for team in teams)]


TAG = re.compile(r'\s*-\s*\[I\](.*?)\[/I\]\s*$')


def continue_watching():
    """The BBC account's Continue watching, as iPlayer WWW lists it signed in:
    [{'title', 'left', 'path', 'picture', 'plot'}]; [] when it can't (not
    installed or not signed in)."""
    listing = kodi.jsonrpc('Files.GetDirectory', directory='plugin://%s/?%s' % (ADDON, urlencode({
        'url': 'url', 'mode': '107', 'name': 'iPlayer: Continue Watching'})), media='files',
        properties=['art', 'thumbnail', 'plot']) or {}
    items = []
    for entry in listing.get('files') or []:
        label = entry.get('label') or ''
        found = TAG.search(label)
        art = entry.get('art') or {}
        items.append({'title': TAG.sub('', label).strip(), 'left': found.group(1).strip() if found else '',
                      'path': entry.get('file') or '', 'plot': entry.get('plot') or '',
                      'picture': art.get('fanart') or art.get('thumb') or entry.get('thumbnail') or ''})
    return [i for i in items if i['title'] and i['path']]


def continue_card(item):
    left = item['left'][:1].upper() + item['left'][1:] if item['left'] else ''
    return {'type': 'tv', 'label': item['title'], 'card.title': item['title'], 'card.sub': 'BBC iPlayer',
            'card.wide_sub': 'BBC iPlayer', 'hero.title': item['title'], 'hero.meta': 'BBC iPlayer',
            'hero.facts': left, 'plot': item['plot'], 'percent': '', 'left': left,
            'art.landscape': item['picture'], 'art.fanart': item['picture'], 'tv.logo': '',
            'tv.play': play_command(item['path'])}


def rows(teams, mentions):
    """{'iplayer_team', 'iplayer_league', 'iplayer_continue'}: the TV page's
    iPlayer rows' cards; all empty without iPlayer WWW."""
    if not installed():
        return {}
    items = highlights()
    try:
        watching = continue_watching()
    except Exception as error:  # the row stays empty
        kodi.log_warning('iPlayer: continue watching: %s' % error)
        watching = []
    return {'iplayer_team': [highlight_card(i) for i in team_highlights(items, teams, mentions)],
            'iplayer_league': [highlight_card(i) for i in items],
            'iplayer_continue': [continue_card(i) for i in watching]}


# ----- a BBC programme from the guide -----

def find_episode(channel, start):
    """The iPlayer episode (pid, title, picture, plot) broadcast on channel
    (Kodi's name) at start (epoch seconds), or None."""
    service = CHANNELS.get(channel)
    if not service:
        return None
    day = datetime.datetime.fromtimestamp(start - 6 * 3600).strftime('%Y-%m-%dT00:00')
    elements = ((get('channels/%s/broadcasts' % service, per_page=200, from_date=day)
                 .get('broadcasts') or {}).get('elements') or [])
    best = None
    for broadcast in elements:
        try:
            when = datetime.datetime.fromisoformat((broadcast.get('scheduled_start') or '').replace('Z', '+00:00'))
        except ValueError:
            continue
        gap = abs(when.timestamp() - start)
        episode = broadcast.get('episode') or {}
        if gap <= NEAR and episode.get('id') and (best is None or gap < best[0]):
            best = (gap, episode)
    if not best:
        return None
    episode = best[1]
    title = ' - '.join(part for part in (episode.get('title'), episode.get('subtitle')) if part)
    return episode['id'], title, picture(episode.get('images')), (episode.get('synopses') or {}).get('small') or ''


def on_iplayer(channel):
    """Whether a channel's earlier programmes can be looked for on iPlayer."""
    return channel in CHANNELS and installed()


def play_programme(channel, start):
    """Play a BBC programme from the guide on iPlayer; False (with a notice)
    when iPlayer doesn't have it."""
    found = find_episode(channel, start)
    if not found:
        kodi.notify('Not on BBC iPlayer')
        kodi.log('iPlayer: nothing on %s at %s' % (channel, time.strftime('%d %b %H:%M', time.localtime(start))))
        return False
    pid, title, image, plot = found
    kodi.log('iPlayer: playing %s (%s) for %s at %s' % (pid, title, channel, time.strftime('%H:%M', time.localtime(start))))
    play(episode_path(pid, title, image, plot))
    return True


def play(path):
    """Play an iPlayer WWW address (its items need playing, not running)."""
    kodi.jsonrpc('Player.Open', item={'file': path})


def guide_start(date_label):
    """The guide's ListItem.Date ("27/11/2026 22:40", day first) as epoch
    seconds, or None."""
    for fmt in ('%d/%m/%Y %H:%M', '%d/%m/%Y %I:%M %p', '%d-%m-%Y %H:%M'):
        try:
            return int(time.mktime(time.strptime(date_label.strip(), fmt)))
        except ValueError:
            continue
    return None
