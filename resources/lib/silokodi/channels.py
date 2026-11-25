# -*- coding: utf-8 -*-
"""Live TV's recently watched channels for a Silo-style skin, as TiviMate
keeps them: newest first, not the one playing, and without any the viewer
removed (until they watch it again; Kodi itself can't forget a channel)."""
import calendar
import glob
import json
import os
import re
import sqlite3
import time

from . import fileio, kodi

REMOVED_FILE = 'recent_channels_removed.json'
LIMIT = 20


def recent(channels, watched, playing=None, removed=None):
    """channels: Kodi's PVR.GetChannels items; watched: {channel id: when it
    was last watched, epoch seconds} (Kodi's JSON-RPC gives only the day).
    The watched ones, newest first, leaving out the playing channel and the
    removed ones (removed: {channel id: when last watched as removed})."""
    removed = removed or {}
    seen = [c for c in channels
            if watched.get(c.get('channelid'), 0) > removed.get(str(c.get('channelid')), 0)
            and not c.get('hidden') and c.get('channelid') != playing]
    return sorted(seen, key=lambda c: watched[c['channelid']], reverse=True)[:LIMIT]


def previous(channels, watched, playing=None):
    """The channel watched before the playing one, or None."""
    seen = recent(channels, watched, playing)
    return seen[0] if seen else None


def last_watched():
    """{channel id: when last watched}: Kodi's, but a channel that only
    played as Skyline's TV page preview keeps its time from before."""
    return without_previews(kodi_last_watched(), load_previews())


def kodi_last_watched():
    """{channel id: when last watched} from Kodi's TV database (read only)."""
    paths = sorted(glob.glob(os.path.join(kodi.database_dir(), 'TV*.db')),
                   key=lambda path: int(re.sub(r'\D', '', os.path.basename(path)) or 0))
    if not paths:
        return {}
    connection = sqlite3.connect('file:%s?mode=ro' % paths[-1], uri=True)
    try:
        return dict(connection.execute('SELECT idChannel, iLastWatched FROM channels WHERE iLastWatched > 0'))
    finally:
        connection.close()


PREVIEWS_FILE = 'tv_previews.json'
PREVIEW_SLACK = 60  # seconds: Kodi's time for a channel starting may be a little before ours


def previews_path():
    return os.path.join(kodi.profile_dir(), PREVIEWS_FILE)


def load_previews():
    try:
        with open(previews_path()) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def save_previews(previews):
    fileio.write_json(previews_path(), previews)


def note_preview(channel_id, now=None, kodi_watched=None):
    """A channel about to play as the TV page's preview (Kodi then counts it
    watched): kept with when, and when it was last watched before (the
    first preview's, if it's previewed again)."""
    previews = load_previews()
    before = (kodi_watched if kodi_watched is not None else kodi_last_watched()).get(int(channel_id), 0)
    entry = previews.get(str(channel_id))
    previews[str(channel_id)] = {'at': int(now or time.time()), 'before': entry['before'] if entry else before}
    save_previews(previews)


def note_watched(channel_id):
    """The channel is watched now (full screen): no longer only previewed."""
    previews = load_previews()
    if previews.pop(str(channel_id), None) is not None:
        save_previews(previews)


def without_previews(watched, previews):
    """watched, a previewed channel's time from before its preview, for as
    long as Kodi's time is the preview's (none if it hadn't been watched)."""
    adjusted = dict(watched)
    for key, entry in (previews or {}).items():
        channel_id = int(key) if str(key).isdigit() else None
        if channel_id in adjusted and adjusted[channel_id] >= entry.get('at', 0) - PREVIEW_SLACK:
            if entry.get('before'):
                adjusted[channel_id] = entry['before']
            else:
                del adjusted[channel_id]
    return adjusted


def removed_path():
    return os.path.join(kodi.profile_dir(), REMOVED_FILE)


def load_removed():
    try:
        with open(removed_path()) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def remove(channel_id, watched):
    """Leave a channel out of the recent list until it is watched again."""
    removed = load_removed()
    removed[str(channel_id)] = watched.get(int(channel_id), 0)
    fileio.write_json(removed_path(), removed)




def is_live(genre):
    """Whether a Kodi broadcast's genre ([text] or text) says it's shown live."""
    texts = genre if isinstance(genre, list) else [genre or '']
    return any(part.strip().lower() == 'live' for text in texts for part in str(text).split('/'))


def utc_seconds(stamp):
    """Kodi's guide time ('2026-11-01 20:00:00', UTC) as epoch seconds. Not
    time.strptime: Kodi's embedded Python can lose _strptime after its first
    use ("'NoneType' object is not callable")."""
    day, _, clock = stamp.partition(' ')
    return calendar.timegm(tuple(int(part) for part in day.split('-') + (clock or '0:0:0').split(':')) + (0, 0, 0))


def channel_broadcasts(channel):
    """The channel's programmes from Kodi's guide, with start and end as epoch seconds."""
    broadcasts = (kodi.jsonrpc('PVR.GetBroadcasts', channelid=channel['channelid'],
                               properties=['title', 'starttime', 'endtime', 'plot', 'thumbnail', 'genre'])
                  or {}).get('broadcasts') or []
    for broadcast in broadcasts:
        broadcast['start'], broadcast['end'] = (utc_seconds(broadcast[key]) for key in ('starttime', 'endtime'))
    return broadcasts
