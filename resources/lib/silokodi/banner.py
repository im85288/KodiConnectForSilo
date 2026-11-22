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
KEYS = ('title', 'times', 'plot', 'picture', 'live', 'when', 'archive', 'broadcastid', 'channelid', 'start',
        'offset', 'channel', 'number', 'logo', 'hint')


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
    show, offset = programme(channels.channel_broadcasts(channel), now, offset + direction)
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
