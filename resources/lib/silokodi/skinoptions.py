# -*- coding: utf-8 -*-
"""Kodi settings a skin's settings screen switches through this add-on, as a
skin can neither change Kodi's own settings nor read a non-boolean one:
this add-on's screensaver, and hiding unwatched episodes' plots and pictures.

state() tells the skin how they stand, as skin booleans (Skyline reads
SkylineSiloScreensaver and SkylineHideSpoilers); toggle(name) switches one
and tells it again. The skin runs state() as its settings screen opens, and
the service at start, so a change made in Kodi's own settings shows too."""
import xbmc

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


def state():
    values = {'screensaver': screensaver_is_ours(get(SCREENSAVER)), 'spoilers': spoilers_hidden(get(UNWATCHED))}
    for name, on in values.items():
        xbmc.executebuiltin('Skin.%s(%s)' % ('SetBool' if on else 'Reset', SKIN_BOOLS[name]))
    return values


def toggle(name):
    if name == 'screensaver':
        mode, remember = next_screensaver(get(SCREENSAVER), kodi.setting(PREVIOUS))
        kodi.set_setting(PREVIOUS, remember)
        put(SCREENSAVER, mode)
    elif name == 'spoilers':
        shown = get(UNWATCHED)
        put(UNWATCHED, without_spoilers(shown, not spoilers_hidden(shown)))
    return state()
