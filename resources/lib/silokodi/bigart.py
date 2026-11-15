# -*- coding: utf-8 -*-
"""Kodi's picture cache sized for 4K menus. Kodi keeps a poster at most 720
high and a background at most 1080 (advancedsettings.xml's imageres and
fanartres), so 4K menus (CoreELEC's, for one) showed Silo's 4K pictures soft.
This add-on offers to raise them, once when it finds the menus drawn in 4K,
and to put them back when they no longer are; Kodi reads the file only as it
starts, so a restart follows.

Only these three settings are touched, the rest of the file kept as written:
a value already as large stays, a scaling method already chosen stays, and
what was there before is remembered (kodi setting big_art_before) to put back."""
import json
import os
import re
import shutil

import xbmc
import xbmcgui
import xbmcvfs

from . import kodi

SIZES = (('imageres', 1440), ('fanartres', 2160))  # posters, backgrounds: their height in the cache
SCALING = ('imagescalingalgorithm', 'lanczos')
ROOT = 'advancedsettings'
BEFORE = 'big_art_before'  # JSON {tag: the value before, or null}; '' when nothing was changed
ASKED = 'big_art_asked'  # '4k' or 'hd': the menus' size the last question was about
COMMENT = '  <!-- KodiConnectForSilo: posters and backgrounds kept sharp for 4K menus -->\n'


def path():
    return xbmcvfs.translatePath('special://profile/advancedsettings.xml')


def value(text, tag):
    found = re.search(r'<%s>\s*([^<]*?)\s*</%s>' % (tag, tag), text or '')
    return found.group(1) if found else None


def wanted(text):
    """{tag: value} to write for 4K menus: sizes below ours, a missing scaling method."""
    out = {}
    for tag, size in SIZES:
        current = value(text, tag)
        if current is None or not current.isdigit() or int(current) < size:
            out[tag] = str(size)
    if value(text, SCALING[0]) is None:
        out[SCALING[0]] = SCALING[1]
    return out


def usable(text):
    """Whether the file can be edited: none yet, or one <advancedsettings> element."""
    return not (text or '').strip() or bool(re.search(r'<%s[\s>].*</%s>\s*$' % (ROOT, ROOT), text.strip(), re.S))


def with_values(text, values):
    """text with each tag set to its value (None: taken out), the rest unchanged."""
    if not (text or '').strip():
        text = '<%s version="1.0">\n</%s>\n' % (ROOT, ROOT)
    for tag, new in values.items():
        pattern = re.compile(r'[ \t]*<%s>[^<]*</%s>[ \t]*\n?' % (tag, tag))
        if new is None:
            text = pattern.sub('', text, count=1)
        elif pattern.search(text):
            text = re.sub(r'<%s>[^<]*</%s>' % (tag, tag), '<%s>%s</%s>' % (tag, new, tag), text, count=1)
        else:
            close = text.rindex('</%s>' % ROOT)
            line = '  <%s>%s</%s>\n' % (tag, new, tag)
            if COMMENT not in text:
                line = COMMENT + line
            text = text[:close] + line + text[close:]
    return text


def read():
    try:
        with open(path(), encoding='utf-8') as handle:
            return handle.read()
    except (IOError, OSError):
        return ''


def write(text):
    target = path()
    if os.path.exists(target):
        shutil.copyfile(target, target + '.before-kodiconnectforsilo')
    with open(target + '.tmp', 'w', encoding='utf-8') as handle:
        handle.write(text)
    os.replace(target + '.tmp', target)


def apply():
    """Raise the sizes; False when nothing needed changing or the file can't be edited."""
    text = read()
    change = wanted(text)
    if not change or not usable(text):
        return False
    before = json.loads(kodi.setting(BEFORE) or '{}')
    for tag in change:
        before.setdefault(tag, value(text, tag))
    write(with_values(text, change))
    kodi.set_setting(BEFORE, json.dumps(before))
    return True


def revert():
    """Put back what this add-on changed; False when it changed nothing."""
    before = json.loads(kodi.setting(BEFORE) or '{}')
    text = read()
    if not before or not usable(text):
        return False
    write(with_values(text, before).replace(COMMENT, ''))
    kodi.set_setting(BEFORE, '')
    return True


def changed():
    return bool(kodi.setting(BEFORE))


def offer_restart():
    if xbmcgui.Dialog().yesno('KodiConnectForSilo', kodi.string(30245)):
        xbmc.executebuiltin('RestartApp')


def check(menus_4k):
    """At start: ask once about the menus' size, if there's something to do."""
    size = '4k' if menus_4k else 'hd'
    if kodi.setting(ASKED) == size or xbmc.getCondVisibility('Player.HasMedia'):
        return  # asked already, or not over something playing (asked at the next start)
    if menus_4k and not wanted(read()):
        return  # already sharp (set by hand, or by an earlier yes)
    if not menus_4k and not changed():
        return
    kodi.set_setting(ASKED, size)
    if xbmcgui.Dialog().yesno('KodiConnectForSilo', kodi.string(30242 if menus_4k else 30243)):
        if apply() if menus_4k else revert():
            offer_restart()
        elif menus_4k:
            kodi.notify(kodi.string(30247))


def choose():
    """The settings' button: sharpen, or put back what was changed."""
    if changed() or not wanted(read()):
        if not changed():
            return kodi.notify(kodi.string(30246))  # already set, by hand
        if xbmcgui.Dialog().yesno('KodiConnectForSilo', kodi.string(30243)) and revert():
            offer_restart()
        return
    if xbmcgui.Dialog().yesno('KodiConnectForSilo', kodi.string(30244)):
        if apply():
            offer_restart()
        else:
            kodi.notify(kodi.string(30247))
