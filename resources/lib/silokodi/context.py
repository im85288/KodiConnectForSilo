# -*- coding: utf-8 -*-
"""Context menu items."""
import xbmc
import xbmcgui

from . import kodi
from .plugin import ask_service


def dismiss(listitem):
    """The context menu's item on a plugin row's card (a library item)."""
    tag = listitem.getVideoInfoTag()
    if _dismiss(tag.getMediaType(), str(tag.getDbId())):
        xbmc.executebuiltin('Container.Refresh')


def home_menu():
    """Home's context menu key. A card of Home's published rows is the
    skin's, not a library item, so Kodi has no menu for it: a library
    title's gets Silo's card menu; anything else Kodi's."""
    kind = xbmc.getInfoLabel('ListItem.Property(home.type)')
    dbid = xbmc.getInfoLabel('ListItem.Property(home.dbid)')
    if kind not in ('movie', 'tvshow', 'episode') or not dbid.isdigit():
        xbmc.executebuiltin('Action(ContextMenu)')
        return
    card_menu(kind, dbid, xbmc.getInfoLabel('ListItem.Property(home.playcount)') not in ('', '0'),
              bool(xbmc.getInfoLabel('ListItem.Property(home.dismiss)')))


HERO_BUTTONS = (4801, 4802)  # Skyline's hero Play and More info (Home, Movies, Series)
LIBRARY_TYPES = ('movie', 'tvshow', 'episode')


def home_title():
    """The library title Skyline's Home, Movies or Series has focused, as
    (type, dbid): the focused card of a row, or the hero's (whose buttons act
    on the card of the row last focused); else (None, None). A card Skyline
    publishes carries home.type and home.dbid; one of Kodi's own lists, its
    DBType and DBID. A title Silo can request has neither."""
    row = xbmc.getInfoLabel('Window(Home).Property(silo.row)')
    if not row.isdigit():
        return None, None
    on_row = xbmc.getCondVisibility('Control.HasFocus(%s)' % row)
    if not on_row and not any(xbmc.getCondVisibility('Control.HasFocus(%d)' % b) for b in HERO_BUTTONS):
        return None, None
    item = 'Container(%s).ListItem.%%s' % row
    if xbmc.getInfoLabel(item % 'Property(home.request.tmdb)'):
        return None, None
    kind, dbid = xbmc.getInfoLabel(item % 'Property(home.type)'), xbmc.getInfoLabel(item % 'Property(home.dbid)')
    if not kind:
        kind, dbid = xbmc.getInfoLabel(item % 'DBType'), xbmc.getInfoLabel(item % 'DBID')
    if kind in LIBRARY_TYPES and dbid.isdigit() and int(dbid) > 0:
        return kind, dbid
    return None, None


def home_play():
    """Skyline's Play/Pause key on Home, Movies and Series (zz_skyline_home.xml):
    a library title's card plays as the hero's Play plays it (a film from where
    it was left, a show at its next episode), so any row can play without the
    hero; anywhere else the key does what it always does."""
    kind, dbid = home_title()
    if not kind:
        xbmc.executebuiltin('Action(PlayPause)')
        return
    from .plugin import play_item
    play_item(kind, dbid)


# Skyline's TV page: its tab, and the condition it's showing with its preview
# playing (build_home.py's TV_TAB and TV_PREVIEWING).
TV_TAB = 9006
TV_PREVIEWING = ('VideoPlayer.Content(LiveTV) + Window.IsActive(home) + '
                 'String.IsEqual(Window(Home).Property(silo.page),tv)')
BAR = 9000  # Skyline's menu bar


def home_back():
    """Back on Home (zz_skyline_home.xml). Kodi's Home goes full screen on Back
    whenever something plays, before the focused control's own Back: on
    Skyline's TV page, whose preview always plays, Back from its rows and
    buttons goes to the TV tab, as on the other pages; from the bar, full
    screen as before. Anywhere else, Back as usual."""
    if xbmc.getCondVisibility(TV_PREVIEWING) and not xbmc.getCondVisibility('ControlGroup(%d).HasFocus()' % BAR):
        xbmc.executebuiltin('SetFocus(%d)' % TV_TAB)
        return
    xbmc.executebuiltin('Action(Back)')


PERSON_GRID = 5301  # Skyline's person page's titles


def person_menu():
    """Skyline's person page's context menu key: a title Not on server offers
    Request (which still asks first) or its Details, as OK opens; anything else
    gets Kodi's own menu."""
    item = 'Container(%d).ListItem.Property(silo.request.%%s)' % PERSON_GRID
    tmdb = xbmc.getInfoLabel(item % 'tmdb')
    if not tmdb or not xbmc.getCondVisibility('Control.HasFocus(%d)' % PERSON_GRID):
        xbmc.executebuiltin('Action(ContextMenu)')
        return
    choice = xbmcgui.Dialog().contextmenu([kodi.string(30219), kodi.string(30220)])
    if choice == 0:
        xbmc.executebuiltin('RunPlugin(plugin://plugin.video.kodiconnectforsilo/?mode=request&type=%s&tmdb=%s)'
                            % (xbmc.getInfoLabel(item % 'type'), tmdb))
    elif choice == 1:
        xbmc.executebuiltin('Action(Select)')


def library_menu(listitem):
    """Kodi's context menu's "Silo" on a library title (Browse, a page's rails)."""
    tag = listitem.getVideoInfoTag()
    card_menu(tag.getMediaType(), str(tag.getDbId()), tag.getPlayCount() > 0,
              bool(listitem.getProperty('silo.dismiss')))


def card_menu(kind, dbid, watched, dismissable):
    """Netflix's card menu, with Silo's lists: Remove from Continue Watching
    (a card there), the watchlist, a rating, watched or not, and Not
    interested (Silo's recommendations then leave the title out). An
    episode's card acts on its show, but for Mark watched."""
    title = ask_service('command/card', timeout=20, type=kind, dbid=dbid)
    if title.get('error'):
        kodi.notify(title['error'])
        return
    content_id, plugin = title['content_id'], 'plugin://plugin.video.kodiconnectforsilo/'
    entries = []
    if dismissable:
        entries.append((kodi.string(30180), lambda: _dismiss(kind, dbid)))
    entries.append((kodi.string(30203 if title.get('watchlist') else 30202),
                    lambda: ask_service('command/watchlist', timeout=20, id=content_id,
                                        add='0' if title.get('watchlist') else '1')))
    entries.append((kodi.string(30204), lambda: xbmc.executebuiltin(
        'RunPlugin(%s?mode=rate&id=%s&current=%s)' % (plugin, content_id, title.get('rating') or 0))))
    entries.append((kodi.string(30206 if watched else 30205), lambda: xbmc.executebuiltin(
        'RunPlugin(%s?mode=mark&type=%s&dbid=%s&action=%s)' % (plugin, kind, dbid,
                                                                'unwatched' if watched else 'watched'))))
    marked = title.get('not_interested')
    entries.append((kodi.string(30208 if marked else 30207), lambda: _not_interested(content_id, not marked)))
    chosen = xbmcgui.Dialog().contextmenu([label for label, _ in entries])
    if chosen >= 0:
        entries[chosen][1]()


def _not_interested(content_id, marked):
    answer = ask_service('command/not_interested', timeout=20, id=content_id, on='1' if marked else '0')
    if answer.get('error'):
        kodi.notify(answer['error'])
    elif marked:
        kodi.notify(kodi.string(30209))


def _dismiss(kind, dbid):
    answer = ask_service('command/dismiss', timeout=20, type=kind, dbid=dbid)
    if answer.get('error'):
        kodi.notify(kodi.string(30181) % answer['error'])
        return False
    return True
