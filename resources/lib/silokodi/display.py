# -*- coding: utf-8 -*-
"""Ask once what the TV shows: its highest resolution and HDR.

The add-on tells Silo these (playback.capabilities), and Silo converts
anything above them. They default to 1080p SDR, which is safe but sends
4K TVs 1080p; people changed Silo's own quality setting instead, which
Kodi doesn't use. So the add-on asks, after sign-in or (for those signed
in before this was added) once on Home, starting on what Kodi reports
for the display."""
import xbmc
import xbmcgui

from . import kodi

ASKED = 'display_asked'
DEFAULTS = {'max_resolution': '1080p', 'dynamic_range': 'sdr'}
RESOLUTIONS = (('1080p', 30027), ('2160p', 30028))
RANGES = (('sdr', 30023), ('hdr10', 30024), ('dv', 30025), ('dv7', 30029))


def suggest(hdr_types, screen_height):
    """(resolution, dynamic range) from Kodi's System.SupportedHDRTypes
    ("HDR10, HLG, Dolby Vision"; empty before Kodi 20 or on an SDR TV) and
    System.ScreenHeight. Dolby Vision profile 7 is never suggested: only
    some devices play it, so it's for the person to choose."""
    types = set(part.strip().lower() for part in (hdr_types or '').split(',') if part.strip())
    if 'dolby vision' in types:
        dynamic_range = 'dv'
    elif types:
        dynamic_range = 'hdr10'
    else:
        dynamic_range = 'sdr'
    try:
        height = int(screen_height or 0)
    except ValueError:
        height = 0
    # Kodi's menus often run at 1080p on a 4K TV; an HDR TV is a 4K one.
    resolution = '2160p' if height >= 2160 or dynamic_range != 'sdr' else '1080p'
    return resolution, dynamic_range


def at_defaults():
    return all((kodi.setting(key) or default) == default for key, default in DEFAULTS.items())


def needs_asking(store):
    """True until asked once. Someone who already chose in the settings is
    never asked (and is marked as asked)."""
    if store.get(ASKED):
        return False
    if not at_defaults():
        store.update(**{ASKED: True})
        return False
    return True


def _choose(heading, options, current):
    labels = [kodi.string(label) for _, label in options]
    at = next((i for i, (value, _) in enumerate(options) if value == current), 0)
    pick = xbmcgui.Dialog().select(kodi.string(heading), labels, preselect=at)
    return options[pick][0] if pick >= 0 else None


def ask(store):
    """Ask, starting on what Kodi detects; saves each answer. Marked as
    asked first, so the service doesn't ask too while this is open, and
    backing out isn't asked again (the settings still have it)."""
    store.update(**{ASKED: True})
    resolution, dynamic_range = suggest(xbmc.getInfoLabel('System.SupportedHDRTypes'),
                                        xbmc.getInfoLabel('System.ScreenHeight'))
    chosen_resolution = _choose(30021, RESOLUTIONS, resolution)
    if chosen_resolution is None:
        return False
    chosen_range = _choose(30022, RANGES, dynamic_range)
    if chosen_range is None:
        return False
    # Both at once: from the settings screen, saving closes and reopens it (kodi.save_settings).
    kodi.save_settings({'max_resolution': chosen_resolution, 'dynamic_range': chosen_range})
    kodi.notify(kodi.string(30234))
    return True


def ask_once(store):
    return ask(store) if needs_asking(store) else False
