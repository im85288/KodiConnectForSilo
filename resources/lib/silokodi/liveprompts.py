# -*- coding: utf-8 -*-
"""Sky's Coming up next over full-screen Live TV, for Skyline to draw: in a
programme's last NEXT_BEFORE seconds, the next one's title, start and picture
for NEXT_SHOW seconds. (Its Start from the beginning note went: the TV
guide's "Restart what's on now" row does that, as Sky Stream's.)

The service calls tick() each second. The channel's programmes are asked of
Kodi only as the channel or its programme changes."""
import time

from . import channels, kodi

NEXT_BEFORE = 120      # seconds before the programme ends
NEXT_SHOW = 20
REFETCH = 30           # at most this often while the guide has nothing on now
KEYS = ('next.title', 'next.time', 'next.picture')
WATCHING = 'Window.IsActive(fullscreenvideo) + VideoPlayer.Content(LiveTV) + !Player.ChannelPreviewActive'


def fetch(channelid):
    """(now, next, hasarchive) of the channel: broadcasts with start and end epoch seconds."""
    details = (kodi.jsonrpc('PVR.GetChannelDetails', channelid=channelid,
                            properties=['broadcastnow', 'broadcastnext', 'hasarchive']) or {}).get('channeldetails') or {}
    shows = []
    for key in ('broadcastnow', 'broadcastnext'):
        show = details.get(key) or None
        if show and show.get('starttime') and show.get('endtime'):
            show['start'], show['end'] = (channels.utc_seconds(show[k]) for k in ('starttime', 'endtime'))
        else:
            show = None
        shows.append(show)
    return shows[0], shows[1], bool(details.get('hasarchive'))


def shows_next(show, upcoming, now):
    return bool(show and upcoming and 0 < show['end'] - now <= NEXT_BEFORE)


class Prompts(object):

    def __init__(self, fetcher=fetch, playing=None):
        self.fetcher = fetcher
        self.playing = playing  # the live channel's id, else None (tvrows.playing_channel)
        self.tuned = False      # the channel below is the one playing
        self.channel = None     # watched full screen, by Kodi id (None: catch-up)
        self.now = self.next = None
        self.archive = False
        self.fetched_at = 0
        self.next_noted = None  # the next programme's start, once noted
        self.next_until = 0

    def clear(self):
        for key in KEYS:
            if kodi.get_property(key):
                kodi.set_property(key, '')
        self.next_until = 0

    def tick(self, watching, now=None):
        """watching: full-screen Live TV, not browsing (WATCHING)."""
        now = now or time.time()
        if not watching:
            if self.tuned:
                if kodi.get_property('next.title'):
                    kodi.log('Live TV: notes cleared: left full-screen Live TV')
                self.tuned = False  # the channel is kept, to know it again on coming back
                self.clear()
            return
        if not self.tuned:
            self.tune(now)
        if self.channel is None:
            return
        if (self.now is None or now >= self.now['end']) and now - self.fetched_at >= REFETCH:
            self.now, self.next, self.archive = self.fetcher(self.channel)
            self.fetched_at = now
        if self.next_until and now >= self.next_until:
            for key in ('next.title', 'next.time', 'next.picture'):
                kodi.set_property(key, '')
            self.next_until = 0
        if shows_next(self.now, self.next, now) and self.next_noted != self.next['start']:
            self.next_noted = self.next['start']
            self.next_until = now + NEXT_SHOW
            kodi.set_property('next.title', self.next.get('title') or self.next.get('label') or '')
            kodi.set_property('next.time', time.strftime('%H:%M', time.localtime(self.next['start'])))
            kodi.set_property('next.picture', self.next.get('thumbnail') or '')
            kodi.log('Live TV: coming up next: %s' % self.next.get('title'))

    def tune(self, now):
        """Full-screen Live TV has started, changed channel or come back (from
        the guide, say)."""
        self.clear()
        self.tuned = True
        channel = self.playing() if self.playing else None
        if channel != self.channel:
            self.next_noted = None
        self.channel = channel
        if channel is None:  # catch-up, or not a channel Kodi knows
            return
        self.now, self.next, self.archive = self.fetcher(channel)
        self.fetched_at = now

    def changed(self):
        """The channel playing has changed: tune again on the next tick."""
        self.tuned = False
