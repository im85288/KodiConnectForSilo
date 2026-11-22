# -*- coding: utf-8 -*-
"""Sky's two notes over full-screen Live TV, for Skyline to draw:

* Start from the beginning: tuning to a channel with catch-up partway through
  a programme offers its start for STARTOVER_SHOW seconds (OK in the player,
  Skyline's window 1196, seeks to it and says so with startover.done).
* Coming up next: in a programme's last NEXT_BEFORE seconds, the next one's
  title, start and picture for NEXT_SHOW seconds.

The service calls tick() each second. The channel's programmes are asked of
Kodi only as the channel or its programme changes. Once a programme has been
started over, the channel plays behind live, so no Coming up next shows on it
(the guide's times would be early) until the channel changes."""
import time

from . import channels, kodi

STARTOVER_AFTER = 120  # seconds into a programme before its start is offered
STARTOVER_LEFT = 300   # not when less than this is left
STARTOVER_SHOW = 10
NEXT_BEFORE = 120      # seconds before the programme ends
NEXT_SHOW = 20
REFETCH = 30           # at most this often while the guide has nothing on now
KEYS = ('startover.title', 'next.title', 'next.time', 'next.picture')
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


def offers_start(show, archive, now):
    return bool(show and archive and now - show['start'] >= STARTOVER_AFTER and show['end'] - now >= STARTOVER_LEFT)


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
        self.started_over = False
        self.next_noted = None  # the next programme's start, once noted
        self.startover_until = self.next_until = 0

    def clear(self):
        for key in KEYS:
            if kodi.get_property(key):
                kodi.set_property(key, '')
        self.startover_until = self.next_until = 0

    def tick(self, watching, now=None):
        """watching: full-screen Live TV, not browsing (WATCHING)."""
        now = now or time.time()
        if not watching:
            if self.tuned:
                if kodi.get_property('startover.title') or kodi.get_property('next.title'):
                    kodi.log('Live TV: notes cleared: left full-screen Live TV')
                self.tuned, self.channel = False, None
                self.clear()
            return
        if kodi.get_property('startover.done'):
            kodi.set_property('startover.done', '')
            kodi.set_property('startover.title', '')
            self.startover_until, self.started_over = 0, True
        if not self.tuned:
            self.tune(now)
        if self.channel is None:
            return
        if (self.now is None or now >= self.now['end']) and now - self.fetched_at >= REFETCH:
            self.now, self.next, self.archive = self.fetcher(self.channel)
            self.fetched_at = now
        if self.startover_until and now >= self.startover_until:
            kodi.set_property('startover.title', '')
            self.startover_until = 0
        if self.next_until and now >= self.next_until:
            for key in ('next.title', 'next.time', 'next.picture'):
                kodi.set_property(key, '')
            self.next_until = 0
        if not self.started_over and shows_next(self.now, self.next, now) and self.next_noted != self.next['start']:
            self.next_noted = self.next['start']
            self.next_until = now + NEXT_SHOW
            kodi.set_property('next.title', self.next.get('title') or self.next.get('label') or '')
            kodi.set_property('next.time', time.strftime('%H:%M', time.localtime(self.next['start'])))
            kodi.set_property('next.picture', self.next.get('thumbnail') or '')
            kodi.log('Live TV: coming up next: %s' % self.next.get('title'))

    def tune(self, now):
        """Full-screen Live TV has started or changed channel (the service says so)."""
        self.clear()
        self.started_over, self.next_noted, self.tuned = False, None, True
        channel = self.playing() if self.playing else None
        self.channel = channel
        if channel is None:  # catch-up, or not a channel Kodi knows
            return
        self.now, self.next, self.archive = self.fetcher(channel)
        self.fetched_at = now
        if offers_start(self.now, self.archive, now):
            self.startover_until = now + STARTOVER_SHOW
            kodi.set_property('startover.title', self.now.get('title') or self.now.get('label') or '')
            kodi.log('Live TV: offering the start of %s' % self.now.get('title'))

    def changed(self):
        """The channel playing has changed: tune again on the next tick."""
        self.tuned = False
