# -*- coding: utf-8 -*-
"""Skyline's Live TV banner, as Sky's: Left and Right step through the
programmes of the channel it shows, browsed (Up/Down, Kodi's channel
preview) or playing (Skyline opens the banner as they're pressed), earlier ones (catch-up plays them) and later ones (a reminder);
OK on one plays it or sets its reminder. The programme shown is published as
silokodi.banner.* for the skin; at the programme on now, or once browsing
ends or moves to another channel (the service's clear_if_stale), they're
cleared and the banner shows Kodi's own again. The quick guide (Left, as
TiviMate's) is gone from the keys: Sky has none."""
import time

from . import channels, kodi, tvrows

KEYS = ('title', 'times', 'plot', 'picture', 'live', 'when', 'archive', 'broadcastid', 'channelid', 'start',
        'offset', 'channel', 'hint')


def props():
    return {key: kodi.get_property('banner.' + key) for key in KEYS}


def clear():
    for key in KEYS:
        kodi.set_property('banner.' + key, '')


def shown_channel():
    """The channel the banner shows (browsed or playing), from Kodi's channels: by name."""
    import xbmc
    name = xbmc.getInfoLabel('VideoPlayer.ChannelName')
    answer = kodi.jsonrpc('PVR.GetChannels', channelgroupid='alltv', properties=['hasarchive']) or {}
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
    return ''


def step(direction, now=None):
    """Left (-1) or Right (+1) while browsing: the shown channel's programme
    before or after the one the banner shows."""
    channel = shown_channel()
    if not channel:
        return
    now = now or time.time()
    before = props()
    offset = int(before['offset'] or 0) if before['channel'] == channel.get('label') else 0
    show, offset = programme(channels.channel_broadcasts(channel), now, offset + direction)
    if show is None or offset == 0:
        clear()
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
              'channel': channel.get('label') or '', 'hint': hint(when, archive, reminded)}
    for key, value in values.items():
        kodi.set_property('banner.' + key, value)


def play():
    """OK on a programme the banner stepped to: an earlier one from catch-up,
    a later one's reminder set or removed (the TV page's reminders)."""
    shown = props()
    if shown['when'] == 'past' and shown['archive'] and shown['broadcastid'].isdigit():
        clear()
        kodi.jsonrpc('Player.Open', item={'broadcastid': int(shown['broadcastid'])})
    elif shown['when'] == 'future' and shown['start']:
        on = tvrows.toggle_reminder(shown['start'], shown['channelid'], shown['title'])
        kodi.set_property('banner.hint', hint('future', False, on))
        kodi.set_property('tv.refresh', '1')  # the TV page's cards say so
    elif shown['when'] == 'past':
        kodi.notify('This programme isn\'t on catch-up')


IDLE = 8  # seconds without a key before the banner leaves a stepped-to programme


def clear_if_stale(idle, channel_name):
    """The service's: no key for IDLE seconds, or another channel shown. The
    skin keeps the banner up while a programme is stepped to (Kodi's own
    banner and preview time out sooner, and closed it mid-step)."""
    shown = kodi.get_property('banner.channel')
    if shown and (idle or shown != channel_name):
        clear()
