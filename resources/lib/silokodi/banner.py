# -*- coding: utf-8 -*-
"""Skyline's Live TV banner window (1183), as Sky's banner: Left and Right
step through the programmes of the channel the banner showed as they were
first pressed (browsed with Up/Down, or playing), earlier ones (catch-up
plays them) and later ones (a reminder); OK on one plays it or sets its
reminder. Skyline notes that channel's name (Home's silo.live.for) and opens
the window, which holds the keys; the programme is published as
silokodi.banner.* for it. The service clears them once the window closes
(clear_if_stale). The quick guide (Left, as TiviMate's) is gone from the
keys: Sky has none."""
import time

from . import channels, kodi, tvrows

WINDOW = 1183  # Skyline's banner window
NEXT = 2  # the programmes after it, alongside, as Sky Stream's banner
NEXT_KEYS = tuple('next%d.%s' % (n, key) for n in range(1, NEXT + 1) for key in ('title', 'time', 'picture'))
KEYS = ('title', 'times', 'plot', 'picture', 'live', 'when', 'archive', 'broadcastid', 'channelid', 'start',
        'offset', 'channel', 'number', 'logo', 'hint') + NEXT_KEYS
BROADCASTS_KEEP = 300  # seconds a channel's programmes are kept for the banner
_broadcasts = {}       # channel id: (when read, its programmes)


def props():
    return {key: kodi.get_property('banner.' + key) for key in KEYS}


def clear():
    for key in KEYS:
        kodi.set_property('banner.' + key, '')


def shown_name():
    """The channel Skyline noted as it opened the banner window, else the one Kodi shows."""
    import xbmc
    import xbmcgui
    return xbmcgui.Window(10000).getProperty('silo.live.for') or xbmc.getInfoLabel('VideoPlayer.ChannelName')


def shown_channel(name):
    """The channel by its name, from Kodi's channels."""
    answer = kodi.jsonrpc('PVR.GetChannels', channelgroupid='alltv',
                          properties=['hasarchive', 'icon', 'channelnumber']) or {}
    return next((c for c in answer.get('channels') or [] if c.get('label') == name), None)


def broadcasts(channel, now=None):
    """The channel's programmes (channels.channel_broadcasts), kept BROADCASTS_KEEP."""
    now = now or time.time()
    kept = _broadcasts.get(channel['channelid'])
    if kept and now - kept[0] < BROADCASTS_KEEP:
        return kept[1]
    found = channels.channel_broadcasts(channel)
    _broadcasts[channel['channelid']] = (now, found)
    return found


def following(shows, after, count=NEXT):
    """The count programmes starting after after (epoch seconds), in order."""
    return sorted((b for b in shows if b.get('start') and b['start'] > after), key=lambda b: b['start'])[:count]


def publish_next(prefix, shows, after):
    """prefix + nextN.title/time/picture for the programmes after after."""
    found = following(shows, after)
    for n in range(1, NEXT + 1):
        show = found[n - 1] if len(found) >= n else {}
        kodi.set_property('%snext%d.title' % (prefix, n), tvrows.without_marks(show.get('title') or ''))
        kodi.set_property('%snext%d.time' % (prefix, n),
                          time.strftime('%H:%M', time.localtime(show['start'])) if show else '')
        kodi.set_property('%snext%d.picture' % (prefix, n), show.get('thumbnail') or '')


def publish_playing_next(name, now=None):
    """The banner's next programmes for the channel Kodi's banner shows (tv.nextN.*):
    those after the one on now. The service's, as the channel or programme changes."""
    channel = shown_channel(name) if name else None
    if not channel:
        publish_next('tv.', [], 0)
        return
    now = now or time.time()
    shows = broadcasts(channel, now)
    on = next((b for b in shows if b.get('start') and b.get('end') and b['start'] <= now < b['end']), None)
    publish_next('tv.', shows, on['start'] if on else now)


NEIGHBOUR_KEYS = ('name', 'logo', 'title', 'picture', 'left', 'live')


def publish_neighbours(name, found=None, now=None):
    """Skyline's Live TV overlay: the channels its previous and next buttons
    play (channels.neighbour, by number) and what's on them, as
    tv.chprev.* and tv.chnext.* (NEIGHBOUR_KEYS), for the card it shows
    above the selected button."""
    import datetime
    if found is None:
        found = (kodi.jsonrpc('PVR.GetChannels', channelgroupid='alltv',
                              properties=['channelnumber', 'icon', 'broadcastnow', 'hidden']) or {}).get('channels') or []
    playing = next((c for c in found if name and c.get('label') == name), None)
    moment = datetime.datetime.fromtimestamp(now or time.time(), datetime.timezone.utc)
    for prefix, step in (('tv.chprev.', -1), ('tv.chnext.', 1)):
        channel = channels.neighbour(found, playing.get('channelid'), step) if playing else None
        on = (channel or {}).get('broadcastnow') or {}
        stop = tvrows.broadcast_stop(on) if on else None
        values = {'name': (channel or {}).get('label') or '', 'logo': (channel or {}).get('icon') or '',
                  'title': tvrows.without_marks(on.get('title') or ''), 'picture': on.get('thumbnail') or '',
                  'left': tvrows.left(stop, moment) if stop else '',
                  'live': '1' if channels.is_live(on.get('genre')) else ''}
        for key in NEIGHBOUR_KEYS:
            kodi.set_property(prefix + key, values[key])


def at(epoch, today):
    moment = time.localtime(epoch)
    clock = time.strftime('%H:%M', moment)
    return clock if moment[:3] == today else time.strftime('%a ', moment) + clock


def programme(broadcasts, now, offset):
    """(the programme offset from the one on now, its offset after clamping to
    what the guide has), or (None, 0)."""
    shows = sorted((b for b in broadcasts if b.get('start') and b.get('end')), key=lambda b: b['start'])
    if not shows:
        return None, 0
    here = next((i for i, b in enumerate(shows) if b['start'] <= now < b['end']), None)
    if here is None:
        here = next((i for i, b in enumerate(shows) if b['start'] > now), len(shows) - 1)
    target = max(0, min(len(shows) - 1, here + offset))
    return shows[target], target - here


def hint(when, archive, reminded):
    if when == 'past':
        return 'OK  Watch from the start' if archive else 'Not on catch-up'
    if when == 'future':
        return 'Reminder set  ·  OK to remove' if reminded else 'OK  Remind me'
    return 'OK  Watch'


def step(direction, now=None):
    """Left (-1) or Right (+1): the noted channel's programme before or after
    the one the window shows (from the one on now, as it opens)."""
    name = shown_name()
    channel = shown_channel(name)
    if not channel:
        kodi.log('Banner: step %+d: no channel for "%s"' % (direction, name))
        return
    now = now or time.time()
    before = props()
    offset = int(before['offset'] or 0) if before['channel'] == channel.get('label') else 0
    shows = broadcasts(channel, now)
    show, offset = programme(shows, now, offset + direction)
    kodi.log('Banner: step %+d on %s: %s' % (direction, channel.get('label'),
                                             '%s (%+d)' % (show.get('title'), offset) if show else 'nothing'))
    if show is None:
        return
    when = 'past' if show['end'] <= now else 'now' if show['start'] <= now else 'future'
    archive = when == 'past' and bool(channel.get('hasarchive'))
    today = time.localtime(now)[:3]
    title = tvrows.without_marks(show.get('title') or show.get('label') or '')
    reminded = when == 'future' and str(int(show['start'])) in tvrows.load_reminders()
    values = {'title': title, 'times': '%s – %s' % (at(show['start'], today), at(show['end'], today)),
              'plot': show.get('plot') or '', 'picture': show.get('thumbnail') or '',
              'live': '1' if channels.is_live(show.get('genre')) else '', 'when': when,
              'archive': '1' if archive else '', 'broadcastid': str(show.get('broadcastid') or ''),
              'channelid': str(channel['channelid']), 'start': str(int(show['start'])), 'offset': str(offset),
              'channel': channel.get('label') or '', 'number': str(channel.get('channelnumber') or ''),
              'logo': channel.get('icon') or '', 'hint': hint(when, archive, reminded)}
    for key, value in values.items():
        kodi.set_property('banner.' + key, value)
    publish_next('banner.', shows, show['start'])


def play():
    """OK in the banner window: an earlier programme from catch-up, the one on
    now its channel live, a later one's reminder set or removed (the TV
    page's reminders). Whether the window should close."""
    shown = props()
    if shown['when'] == 'past' and shown['archive'] and shown['broadcastid'].isdigit():
        kodi.jsonrpc('Player.Open', item={'broadcastid': int(shown['broadcastid'])})
        return True
    if shown['when'] == 'now' and shown['channelid'].isdigit():
        kodi.jsonrpc('Player.Open', item={'channelid': int(shown['channelid'])})
        return True
    if shown['when'] == 'future' and shown['start']:
        on = tvrows.toggle_reminder(shown['start'], shown['channelid'], shown['title'])
        kodi.set_property('banner.hint', hint('future', False, on))
        kodi.set_property('tv.refresh', '1')  # the TV page's cards say so
        return False
    if shown['when'] == 'past':
        kodi.notify('This programme isn\'t on catch-up')
    return False


def clear_if_stale(window_open):
    """The service's: the banner window has closed."""
    if not window_open and kodi.get_property('banner.channel'):
        kodi.log('Banner: closed')
        clear()
