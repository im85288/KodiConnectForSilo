# -*- coding: utf-8 -*-
"""Shuffle, as Netflix's "Play something": a random title to play from a
scope a skin names (mode=shuffle&scope=...&id=...).

    movies   a random film not yet watched (any film once all are)
    tvshows  a random show with episodes left, at its next one
    tvshow   a random episode of one show (id: its library id), unwatched
             first: for the sitcoms one dips into
    set      a random film of a box set (id: the movie set), unwatched first
    collection  a random title of a Silo collection (id: library:collection),
             unwatched first; a show plays its next episode (from_titles)

Kodi plays what's chosen as any library item, through the add-on's own
play route, so a Silo session, resume and Up Next work as usual.
"""
import random

from . import kodi

FIELDS = ['playcount', 'title']


def pick(items, rand=random):
    """A random item, from the unwatched ones while there are any."""
    unwatched = [i for i in items if not i.get('playcount')]
    pool = unwatched or items
    return rand.choice(pool) if pool else None


def next_episode(episodes):
    """A show's next episode: the first unwatched in order, specials aside."""
    ordered = sorted((e for e in episodes if e.get('season')), key=lambda e: (e['season'], e['episode']))
    return next((e for e in ordered if not e.get('playcount')), None)


def from_titles(titles, rand=random):
    """A pick from a collection's titles ([{'type', 'kodi_id'}], as the
    service lists them): an unwatched film or a show with episodes left
    first, as {'movieid': n} or {'episodeid': n}; None if nothing plays."""
    films = dict((f['movieid'], f) for f in (kodi.jsonrpc('VideoLibrary.GetMovies', properties=FIELDS)
                                             or {}).get('movies') or [])
    shows = dict((s['tvshowid'], s) for s in (kodi.jsonrpc('VideoLibrary.GetTVShows',
                                                           properties=['episode', 'watchedepisodes'])
                                              or {}).get('tvshows') or [])
    candidates = []
    for title in titles:
        if title.get('type') == 'movie' and title.get('kodi_id') in films:
            candidates.append({'kind': 'movie', 'id': title['kodi_id'],
                               'playcount': films[title['kodi_id']].get('playcount')})
        elif title.get('type') == 'tvshow' and title.get('kodi_id') in shows:
            show = shows[title['kodi_id']]
            left = (show.get('episode') or 0) > (show.get('watchedepisodes') or 0)
            candidates.append({'kind': 'tvshow', 'id': title['kodi_id'], 'playcount': 0 if left else 1})
    chosen = pick(candidates, rand)
    if not chosen:
        return None
    if chosen['kind'] == 'movie':
        return {'movieid': chosen['id']}
    episodes = (kodi.jsonrpc('VideoLibrary.GetEpisodes', tvshowid=chosen['id'],
                             properties=FIELDS + ['season', 'episode']) or {}).get('episodes') or []
    episode = next_episode(episodes) or pick([e for e in episodes if e.get('season')], rand)
    return {'episodeid': episode['episodeid']} if episode else None


def choose(scope, item_id=None, rand=random):
    """{'movieid': n} or {'episodeid': n} to play, or None."""
    if scope == 'movies':
        films = (kodi.jsonrpc('VideoLibrary.GetMovies', properties=FIELDS) or {}).get('movies') or []
        film = pick(films, rand)
        return {'movieid': film['movieid']} if film else None
    if scope == 'set':
        found = (kodi.jsonrpc('VideoLibrary.GetMovieSetDetails', setid=int(item_id),
                              movies={'properties': FIELDS}) or {}).get('setdetails') or {}
        film = pick(found.get('movies') or [], rand)
        return {'movieid': film['movieid']} if film else None
    if scope == 'tvshow':
        episodes = (kodi.jsonrpc('VideoLibrary.GetEpisodes', tvshowid=int(item_id),
                                 properties=FIELDS + ['season', 'episode']) or {}).get('episodes') or []
        episode = pick([e for e in episodes if e.get('season')], rand)
        return {'episodeid': episode['episodeid']} if episode else None
    if scope == 'tvshows':
        shows = (kodi.jsonrpc('VideoLibrary.GetTVShows', properties=['episode', 'watchedepisodes']) or {}).get(
            'tvshows') or []
        started = [s for s in shows if (s.get('episode') or 0) > (s.get('watchedepisodes') or 0)]
        rand.shuffle(started)
        for show in started[:5]:  # a show whose unwatched episodes are all specials: the next one
            episodes = (kodi.jsonrpc('VideoLibrary.GetEpisodes', tvshowid=show['tvshowid'],
                                     properties=FIELDS + ['season', 'episode']) or {}).get('episodes') or []
            episode = next_episode(episodes)
            if episode:
                return {'episodeid': episode['episodeid']}
        return None
    return None
