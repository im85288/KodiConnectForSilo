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


def test_a_backdrop_and_its_logo_load_unseen_before_they_show():
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
    window.loader, window.logo_loader = Layer('loader', log), Layer('logo_loader', log)
    window.logo, window.name = Layer('logo', log), Layer('name', log)
    window.name.setLabel = lambda text: None
    window.top_shown = False
    waited = []

    def wait(seconds):
        waited.append((seconds, len(log)))
        return False
    window.show_title({'fanart': 'f1', 'logo': 'l1', 'name': 'A'}, wait)
    # The loaders get the pictures first; nothing visible changes until after the wait.
    assert log[:2] == [('loader', 'image', 'f1'), ('logo_loader', 'image', 'l1')]
    assert waited == [(screensaver.PRELOAD, 2)]
    assert log[2:] == [('top', 'image', 'f1'), ('top', 'visible', True),
                       ('logo', 'image', 'l1'), ('logo', 'visible', True)]
    # The next goes on the bottom layer, revealed as the top fades out.
    log[:] = []
    window.show_title({'fanart': 'f2', 'logo': '', 'name': 'B'}, lambda s: False)
    assert log[2:5] == [('bottom', 'image', 'f2'), ('bottom', 'visible', True), ('top', 'visible', False)]
    assert ('logo', 'visible', False) in log
    # Ending during the wait changes nothing on screen.
    log[:] = []
    window.show_title({'fanart': 'f3', 'logo': 'l3', 'name': 'C'}, lambda s: True)
    assert [entry[0] for entry in log] == ['loader', 'logo_loader']


def test_the_layout_fits_kodis_window_grid():
    from resources.lib.silokodi import screensaver
    # Kodi's add-on windows are 1280x720: everything inside it, the logo above the bottom edge.
    rects = screensaver.layout(1280, 720)
    assert rects['backdrop'] == (0, 0, 1280, 720)
    for x, y, w, h in rects.values():
        assert x + w <= 1280 and y + h <= 720
    assert rects['logo'] == (80, 493, 426, 146)
    assert screensaver.layout(1920, 1080)['logo'] == (120, 740, 640, 220)
    assert screensaver.layout(0, 0)['backdrop'] == (0, 0, 1280, 720)  # unknown size: Kodi's grid
