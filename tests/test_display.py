# -*- coding: utf-8 -*-
"""Asking once what the TV shows (display.py)."""
import pytest

from resources.lib.silokodi import display
from resources.lib.silokodi.store import Store


@pytest.mark.parametrize('hdr_types, height, expected', [
    ('HDR10, HLG, Dolby Vision', '2160', ('2160p', 'dv')),
    ('HDR10, HLG', '1080', ('2160p', 'hdr10')),  # menus at 1080p on a 4K HDR TV
    ('', '2160', ('2160p', 'sdr')),
    ('', '1080', ('1080p', 'sdr')),
    ('', '', ('1080p', 'sdr')),                  # before Kodi 20
])
def test_it_suggests_what_kodi_reports_for_the_display(hdr_types, height, expected):
    assert display.suggest(hdr_types, height) == expected


@pytest.fixture
def kodi_settings(monkeypatch):
    settings = {}
    monkeypatch.setattr(display.kodi, 'setting', lambda key: settings.get(key, ''))
    monkeypatch.setattr(display.kodi, 'set_setting', settings.__setitem__)
    monkeypatch.setattr(display.kodi, 'string', lambda string_id: str(string_id))
    monkeypatch.setattr(display.kodi, 'notify', lambda *a, **k: None)
    return settings


def dialog_answering(monkeypatch, picks):
    asked = []

    class Dialog(object):
        def select(self, heading, labels, preselect=-1):
            asked.append((heading, preselect))
            return picks.pop(0)
    monkeypatch.setattr(display.xbmcgui, 'Dialog', Dialog)
    return asked


def test_it_asks_once_starting_on_what_the_tv_reports(tmp_path, monkeypatch, kodi_settings):
    labels = {'System.SupportedHDRTypes': 'HDR10, HLG, Dolby Vision', 'System.ScreenHeight': '2160'}
    monkeypatch.setattr(display.xbmc, 'getInfoLabel', lambda label: labels.get(label, ''))
    asked = dialog_answering(monkeypatch, [1, 3])
    store = Store(str(tmp_path))
    assert display.ask_once(store)
    assert asked == [('30021', 1), ('30022', 2)]  # 4K, Dolby Vision 5/8 preselected
    assert kodi_settings == {'max_resolution': '2160p', 'dynamic_range': 'dv7'}
    assert not display.ask_once(store)
    assert len(asked) == 2


def test_backing_out_keeps_the_settings_and_is_not_asked_again(tmp_path, monkeypatch, kodi_settings):
    dialog_answering(monkeypatch, [-1])
    store = Store(str(tmp_path))
    assert not display.ask_once(store)
    assert kodi_settings == {}
    assert not display.needs_asking(Store(str(tmp_path)))


def test_someone_who_already_chose_is_never_asked(tmp_path, kodi_settings):
    kodi_settings['max_resolution'] = '2160p'
    store = Store(str(tmp_path))
    assert not display.needs_asking(store)
    assert store.get(display.ASKED)


def test_the_service_asks_only_on_home_with_nothing_playing(monkeypatch):
    from resources.lib.silokodi import service
    runs, conditions = [], {'home': False}
    monkeypatch.setattr(service.xbmc, 'executebuiltin', runs.append)
    monkeypatch.setattr(service.xbmc, 'getCondVisibility', lambda condition: conditions['home'])
    monkeypatch.setattr(service.display, 'needs_asking', lambda store: True)
    svc = service.Service.__new__(service.Service)
    svc.display_checked = False
    svc.store = None
    svc.playing = lambda: False
    svc.ask_about_display(service.DISPLAY_ASK_AFTER)
    assert runs == []
    conditions['home'] = True
    svc.ask_about_display(service.DISPLAY_ASK_AFTER + 1)  # only every 5 s
    assert runs == []
    svc.ask_about_display(service.DISPLAY_ASK_AFTER + 5)
    svc.ask_about_display(service.DISPLAY_ASK_AFTER + 10)
    assert runs == ['RunPlugin(plugin://plugin.video.kodiconnectforsilo/?mode=display)']
