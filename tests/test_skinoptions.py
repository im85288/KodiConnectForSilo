# -*- coding: utf-8 -*-
"""The Kodi settings a skin's settings screen switches through the add-on:
its screensaver, and hiding unwatched episodes' plots and pictures."""
from resources.lib.silokodi import skinoptions


def test_the_screensaver_toggle_chooses_ours_and_puts_the_last_one_back():
    assert skinoptions.next_screensaver('screensaver.xbmc.builtin.black', '') == \
        (skinoptions.ADDON_ID, 'screensaver.xbmc.builtin.black')
    assert skinoptions.next_screensaver(skinoptions.ADDON_ID, 'screensaver.xbmc.builtin.black') == \
        ('screensaver.xbmc.builtin.black', 'screensaver.xbmc.builtin.black')
    # Nothing (or ours) remembered: Kodi's Dim.
    assert skinoptions.next_screensaver(skinoptions.ADDON_ID, '')[0] == skinoptions.DIM
    assert skinoptions.next_screensaver('', '') == (skinoptions.ADDON_ID, '')


def test_spoilers_hide_episodes_plots_and_pictures_and_leave_films_alone():
    assert not skinoptions.spoilers_hidden([0, 1, 2])
    assert skinoptions.spoilers_hidden([0]) and skinoptions.spoilers_hidden([])
    assert not skinoptions.spoilers_hidden([2])  # an episode's picture still shows
    assert skinoptions.without_spoilers([0, 1, 2], hide=True) == [0]
    assert skinoptions.without_spoilers([1, 2], hide=True) == []
    assert skinoptions.without_spoilers([0], hide=False) == [0, 1, 2]
    assert skinoptions.without_spoilers([], hide=False) == [1, 2]


def test_state_tells_the_skin_and_toggle_switches(monkeypatch):
    settings = {skinoptions.SCREENSAVER: 'screensaver.xbmc.builtin.dim', skinoptions.UNWATCHED: [0, 1, 2]}
    saved, builtins = {}, []

    def jsonrpc(method, **params):
        if method == 'Settings.GetSettingValue':
            return {'value': settings[params['setting']]}
        settings[params['setting']] = params['value']
    monkeypatch.setattr(skinoptions.kodi, 'jsonrpc', jsonrpc)
    monkeypatch.setattr(skinoptions.kodi, 'setting', lambda key: saved.get(key, ''))
    monkeypatch.setattr(skinoptions.kodi, 'set_setting', saved.__setitem__)
    monkeypatch.setattr(skinoptions.xbmc, 'executebuiltin', builtins.append)
    assert skinoptions.state() == {'screensaver': False, 'spoilers': False}
    assert 'Skin.Reset(SkylineSiloScreensaver)' in builtins
    assert skinoptions.toggle('screensaver') == {'screensaver': True, 'spoilers': False}
    assert settings[skinoptions.SCREENSAVER] == skinoptions.ADDON_ID and 'Skin.SetBool(SkylineSiloScreensaver)' in builtins
    assert skinoptions.toggle('spoilers')['spoilers'] and settings[skinoptions.UNWATCHED] == [0]
    assert skinoptions.toggle('screensaver')['screensaver'] is False
    assert settings[skinoptions.SCREENSAVER] == 'screensaver.xbmc.builtin.dim'
