# -*- coding: utf-8 -*-
import random

from resources.lib.silokodi import shuffle


def test_shuffle_picks_unwatched_first_then_anything():
    rand = random.Random(1)
    items = [{'movieid': 1, 'playcount': 1}, {'movieid': 2, 'playcount': 0}, {'movieid': 3}]
    assert all(shuffle.pick(items, rand)['movieid'] in (2, 3) for _ in range(20))
    watched = [{'movieid': 1, 'playcount': 2}]
    assert shuffle.pick(watched, rand)['movieid'] == 1
    assert shuffle.pick([], rand) is None


def test_a_shows_next_episode_skips_specials_and_watched():
    episodes = [{'episodeid': 9, 'season': 0, 'episode': 1, 'playcount': 0},
                {'episodeid': 2, 'season': 1, 'episode': 2, 'playcount': 0},
                {'episodeid': 1, 'season': 1, 'episode': 1, 'playcount': 1}]
    assert shuffle.next_episode(episodes)['episodeid'] == 2
    assert shuffle.next_episode([e for e in episodes if e['episodeid'] == 1]) is None


def test_a_collection_shuffles_its_own_titles_unwatched_first(monkeypatch):
    library = {
        'VideoLibrary.GetMovies': {'movies': [{'movieid': 1, 'playcount': 1}, {'movieid': 2, 'playcount': 0},
                                              {'movieid': 3, 'playcount': 0}]},
        'VideoLibrary.GetTVShows': {'tvshows': [{'tvshowid': 7, 'episode': 10, 'watchedepisodes': 10}]},
        'VideoLibrary.GetEpisodes': {'episodes': [{'episodeid': 70, 'season': 1, 'episode': 1, 'playcount': 1}]}}
    monkeypatch.setattr(shuffle.kodi, 'jsonrpc', lambda method, **params: library[method])
    rand = random.Random(3)
    titles = [{'type': 'movie', 'kodi_id': 1}, {'type': 'movie', 'kodi_id': 2}, {'type': 'tvshow', 'kodi_id': 7}]
    # Film 3 isn't in the collection; film 1 and the show are watched.
    assert all(shuffle.from_titles(titles, rand) == {'movieid': 2} for _ in range(10))
    # Everything watched: any of them; a show plays one of its episodes.
    assert shuffle.from_titles([{'type': 'tvshow', 'kodi_id': 7}], rand) == {'episodeid': 70}
    assert shuffle.from_titles([], rand) is None
