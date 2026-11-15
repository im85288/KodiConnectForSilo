# -*- coding: utf-8 -*-
"""Kodi settings a skin's settings screen switches through this add-on, as a
skin can neither change Kodi's own settings nor read a non-boolean one:
this add-on's screensaver, and hiding unwatched episodes' plots and pictures.

state() tells the skin how they stand, as skin booleans (Skyline reads
SkylineSiloScreensaver and SkylineHideSpoilers); toggle(name) switches one
and tells it again. The skin runs state() as its settings screen opens, and
the service at start, so a change made in Kodi's own settings shows too."""
import xbmc
import xbmcgui

from . import kodi

ADDON_ID = 'plugin.video.kodiconnectforsilo'
SCREENSAVER = 'screensaver.mode'
DIM = 'screensaver.xbmc.builtin.dim'
# Kodi's "Show information for unwatched items": 0 a film's plot, 1 an
# episode's plot, 2 an episode's picture. Spoilers hidden: 1 and 2 off.
UNWATCHED = 'videolibrary.showunwatchedplots'
EPISODE_SPOILERS = (1, 2)
# Where the screensaver chosen before ours is kept, to put it back.
PREVIOUS = 'previous_screensaver'
SKIN_BOOLS = {'screensaver': 'SkylineSiloScreensaver', 'spoilers': 'SkylineHideSpoilers'}
# The list's heading for each choice.
STRINGS = {'screensaver_time': 30250, 'unpause_back': 30251, 'theme_volume': 30252}


def get(setting):
    return (kodi.jsonrpc('Settings.GetSettingValue', setting=setting) or {}).get('value')


def put(setting, value):
    kodi.jsonrpc('Settings.SetSettingValue', setting=setting, value=value)


def screensaver_is_ours(mode):
    return mode == ADDON_ID


def spoilers_hidden(shown):
    """Whether Kodi hides unwatched episodes' plots and pictures (both off)."""
    return not any(value in (shown or []) for value in EPISODE_SPOILERS)


def without_spoilers(shown, hide):
    """Kodi's list of what it shows for unwatched items, with the episodes'
    plot and picture taken out (hide) or put back; a film's plot as it was."""
    films = [value for value in (shown or []) if value not in EPISODE_SPOILERS]
    return sorted(films if hide else films + list(EPISODE_SPOILERS))


def next_screensaver(mode, previous):
    """(the screensaver to choose, the one to remember) when the toggle is pressed."""
    if screensaver_is_ours(mode):
        return (previous if previous and previous != ADDON_ID else DIM), previous
    return ADDON_ID, mode or ''


# Choices a skin's settings screen offers as a list, each shown beside its
# button as a skin string: (where it's kept, its values, how each reads).
# where: ('kodi', setting) for Kodi's own, ('addon', setting) for this add-on's.
CHOICES = {
    'screensaver_time': (('kodi', 'screensaver.time'), (1, 2, 3, 5, 10, 15, 20, 30, 60),
                         lambda minutes: '%d min' % minutes, 'SkylineScreensaverTime'),
    'unpause_back': (('addon', 'unpause_back'), (0, 3, 5, 10),
                     lambda seconds: '%d s' % seconds if seconds else 'Off', 'SkylineUnpauseBack'),
    'theme_volume': (('addon', 'theme_volume'), (25, 50, 75, 100),
                     lambda percent: '%d%%' % percent, 'SkylineThemeVolume'),
}
TEAMS = 'SkylineTvTeams'


def chosen(name):
    (where, setting), values, _, _ = CHOICES[name]
    current = get(setting) if where == 'kodi' else kodi.setting_int(setting)
    return int(current) if current is not None else values[0]


def nearest(values, current):
    """The listed value closest to current (a hand-set 4 minutes shows as 5)."""
    return min(values, key=lambda value: (abs(value - current), value))


def state():
    values = {'screensaver': screensaver_is_ours(get(SCREENSAVER)), 'spoilers': spoilers_hidden(get(UNWATCHED))}
    for name, on in values.items():
        xbmc.executebuiltin('Skin.%s(%s)' % ('SetBool' if on else 'Reset', SKIN_BOOLS[name]))
    for name, (_, _, label, skin_string) in CHOICES.items():
        values[name] = chosen(name)
        xbmc.executebuiltin('Skin.SetString(%s,%s)' % (skin_string, label(values[name])))
    teams = kodi.setting('tv_teams') or ''
    names = [name.strip() for name in teams.split(',') if name.strip()]
    xbmc.executebuiltin('Skin.SetString(%s,%s)' % (TEAMS, ' · '.join(names) or 'None'))
    return values


def choose(name):
    """A list of the choice's values; the one picked is kept and shown."""
    if name == 'tv_teams':
        teams = xbmcgui.Dialog().input(kodi.string(30221), kodi.setting('tv_teams') or '')
        if teams is not None:
            kodi.set_setting('tv_teams', teams.strip())
        return state()
    (where, setting), values, label, _ = CHOICES[name]
    current = nearest(values, chosen(name))
    picked = xbmcgui.Dialog().select(kodi.string(STRINGS[name]), [label(value) for value in values],
                                     preselect=values.index(current))
    if picked >= 0:
        if where == 'kodi':
            put(setting, values[picked])
        else:
            kodi.set_setting(setting, str(values[picked]))
    return state()


def reset():
    """Every Skyline option back to its default, once the viewer says so.
    Kodi's own settings a toggle switches (screensaver, spoilers) stay."""
    if xbmcgui.Dialog().yesno('Skyline', kodi.string(30253)):
        xbmc.executebuiltin('Skin.ResetSettings')
        xbmc.sleep(500)
        state()


def toggle(name):
    if name == 'screensaver':
        mode, remember = next_screensaver(get(SCREENSAVER), kodi.setting(PREVIOUS))
        kodi.set_setting(PREVIOUS, remember)
        put(SCREENSAVER, mode)
    elif name == 'spoilers':
        shown = get(UNWATCHED)
        put(UNWATCHED, without_spoilers(shown, not spoilers_hidden(shown)))
    return state()
