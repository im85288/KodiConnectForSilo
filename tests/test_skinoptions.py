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
    settings = {skinoptions.SCREENSAVER: 'screensaver.xbmc.builtin.dim', skinoptions.UNWATCHED: [0, 1, 2],
                'screensaver.time': 3}
    saved, builtins = {}, []

    def jsonrpc(method, **params):
        if method == 'Settings.GetSettingValue':
            return {'value': settings[params['setting']]}
        settings[params['setting']] = params['value']
    monkeypatch.setattr(skinoptions.kodi, 'jsonrpc', jsonrpc)
    monkeypatch.setattr(skinoptions.kodi, 'setting', lambda key: saved.get(key, ''))
    monkeypatch.setattr(skinoptions.kodi, 'set_setting', saved.__setitem__)
    monkeypatch.setattr(skinoptions.kodi, 'setting_int', lambda key: int(saved.get(key) or 0))
    monkeypatch.setattr(skinoptions.xbmc, 'executebuiltin', builtins.append)
    saved['tv_teams'] = 'Newcastle United,England'
    skinoptions.state()
    assert 'Skin.SetString(SkylineTvTeams,Newcastle United · England)' in builtins
    del saved['tv_teams']
    state = skinoptions.state()
    assert state['screensaver'] is False and state['spoilers'] is False
    assert 'Skin.SetString(SkylineScreensaverTime,3 min)' in builtins
    assert 'Skin.SetString(SkylineUnpauseBack,Off)' in builtins and 'Skin.SetString(SkylineTvTeams,None)' in builtins
    assert 'Skin.Reset(SkylineSiloScreensaver)' in builtins
    assert skinoptions.toggle('screensaver')['screensaver'] is True
    assert settings[skinoptions.SCREENSAVER] == skinoptions.ADDON_ID and 'Skin.SetBool(SkylineSiloScreensaver)' in builtins
    assert skinoptions.toggle('spoilers')['spoilers'] and settings[skinoptions.UNWATCHED] == [0]
    assert skinoptions.toggle('screensaver')['screensaver'] is False
    assert settings[skinoptions.SCREENSAVER] == 'screensaver.xbmc.builtin.dim'


def test_a_choice_shows_the_nearest_listed_value_and_keeps_the_one_picked(monkeypatch):
    assert skinoptions.nearest((1, 2, 3, 5, 10), 4) == 3 and skinoptions.nearest((1, 2, 3, 5, 10), 7) == 5
    settings, saved, builtins, offered = {'screensaver.time': 4}, {}, [], []

    def jsonrpc(method, **params):
        if method == 'Settings.GetSettingValue':
            return {'value': settings.get(params['setting'], [0, 1, 2] if 'unwatched' in params['setting'] else '')}
        settings[params['setting']] = params['value']
    monkeypatch.setattr(skinoptions.kodi, 'jsonrpc', jsonrpc)
    monkeypatch.setattr(skinoptions.kodi, 'setting', lambda key: saved.get(key, ''))
    monkeypatch.setattr(skinoptions.kodi, 'setting_int', lambda key: int(saved.get(key) or 0))
    monkeypatch.setattr(skinoptions.kodi, 'set_setting', saved.__setitem__)
    monkeypatch.setattr(skinoptions.kodi, 'string', str)
    monkeypatch.setattr(skinoptions.xbmc, 'executebuiltin', builtins.append)

    class Dialog(object):
        def select(self, heading, labels, preselect=0):
            offered.append((labels, preselect))
            return labels.index('10 min') if 'min' in labels[0] else labels.index('5 s')
    monkeypatch.setattr(skinoptions.xbmcgui, 'Dialog', Dialog)
    skinoptions.choose('screensaver_time')
    assert offered[0][1] == 2 and settings['screensaver.time'] == 10  # 4 min showed as 3
    skinoptions.choose('unpause_back')
    assert saved['unpause_back'] == '5' and 'Skin.SetString(SkylineUnpauseBack,5 s)' in builtins
