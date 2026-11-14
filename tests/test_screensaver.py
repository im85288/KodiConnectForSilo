# -*- coding: utf-8 -*-
import random

from resources.lib.silokodi import screensaver


def test_titles_with_a_backdrop_only(monkeypatch):
    answers = {'VideoLibrary.GetMovies': {'movies': [
        {'title': 'Heat', 'art': {'fanart': 'f1', 'clearlogo': 'l1'}},
        {'title': 'No art', 'art': {}}]},
        'VideoLibrary.GetTVShows': {'tvshows': [{'title': 'Severance', 'art': {'fanart': 'f2'}}]}}
    monkeypatch.setattr(screensaver.kodi, 'jsonrpc', lambda method, **params: answers[method])
    found = screensaver.titles(random.Random(0))
    assert sorted(t['name'] for t in found) == ['Heat', 'Severance']
    assert {t['name']: t['logo'] for t in found} == {'Heat': 'l1', 'Severance': ''}


def test_a_backdrop_on_the_bottom_layer_loads_before_the_top_fades_out():
    from resources.lib.silokodi import screensaver

    class Layer(object):
        def __init__(self, name, log):
            self.name, self.log = name, log

        def setImage(self, image, use_cache):
            self.log.append((self.name, 'image', image))

        def setVisible(self, shown):
            self.log.append((self.name, 'visible', shown))

    log = []
    window = screensaver.Screensaver.__new__(screensaver.Screensaver)
    window.layers = [Layer('bottom', log), Layer('top', log)]
    window.logo, window.name = Layer('logo', log), Layer('name', log)
    window.name.setLabel = lambda text: None
    window.top_shown = True  # the next goes on the bottom layer
    waited = []
    window.show_title({'fanart': 'f2', 'logo': '', 'name': 'B'}, lambda s: waited.append((s, len(log))) or False)
    # The bottom gets its picture and shows (under the top) before the wait; the top fades out only after.
    assert log[:2] == [('bottom', 'image', 'f2'), ('bottom', 'visible', True)]
    assert waited == [(screensaver.PRELOAD, 2)] and log[2] == ('top', 'visible', False)
    # Ending during the wait leaves the top as it is.
    log[:], window.top_shown = [], True
    window.show_title({'fanart': 'f3', 'logo': '', 'name': 'C'}, lambda s: True)
    assert ('top', 'visible', False) not in log
