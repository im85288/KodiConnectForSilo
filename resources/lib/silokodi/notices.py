# -*- coding: utf-8 -*-
"""Silo's notifications as Kodi notices.

Silo tells a profile when an episode becomes its Next Up, when a request or a
watchlist title arrives, and when a request is approved or declined
(notification.created on the notifications channel, silo-server #4409). The
wording follows Silo's own native notifications (internal/notifications/
display.go); other kinds (an admin's webhook failing, say) aren't shown.
"""

SHOW_FOR = 8000  # milliseconds

PLACEHOLDER_TITLES = ('tba', 'tbd', 'to be announced')


def episode_code(data):
    season, episode = data.get('season_number'), data.get('episode_number')
    if isinstance(season, int) and isinstance(episode, int):
        return 'S%02dE%02d' % (season, episode)
    return ''


def text(data):
    """(heading, message) for a notification, or None to leave it unshown."""
    kind = data.get('type') or ''
    title = (data.get('series_title') or '').strip()
    flags = data.get('reason_flags') if isinstance(data.get('reason_flags'), dict) else {}
    if kind == 'episode.available':
        episode = (data.get('episode_title') or '').strip()
        if episode.lower() in PLACEHOLDER_TITLES or episode.lower().startswith('episode '):
            episode = ''
        parts = [part for part in ('New episode', episode_code(data), episode) if part]
        return (title or 'New episode available'), ' · '.join(parts)
    if kind in ('request.fulfilled', 'watchlist.available'):
        return ('%s is now available' % title if title else 'Now in your library'), 'In your library now'
    if kind in ('request.approved', 'request.declined'):
        verb = 'approved' if kind == 'request.approved' else 'declined'
        name = (flags.get('title') or title or '').strip()
        heading = '%s was %s' % (name, verb) if name else 'Your request was %s' % verb
        reason = (flags.get('reason') or '').strip()
        return heading, ('Reason: %s' % reason[:120]) if reason and verb == 'declined' else 'Your request was %s' % verb
    return None


def picture_id(data):
    """The title whose poster the notice shows: the series (or film)."""
    return data.get('series_id') or data.get('episode_id') or ''
