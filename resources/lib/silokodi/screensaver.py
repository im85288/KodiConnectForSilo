# -*- coding: utf-8 -*-
"""A screensaver of the library's artwork, as Apple TV's and Infuse's: a
title's backdrop, slowly drifting, with its clear logo (its name without
one), then the next, cross-fading. Silo's films and shows only: their art
comes through the add-on's relay, so it is already on the device's network
and costs no disk. Any skin can use it (Settings > Interface > Screensaver).
"""
import os
import random

import xbmc
import xbmcgui

from . import kodi

SLIDE = 12  # seconds a title stays
FADE = 1500  # ms of cross-fade between titles
PRELOAD = 3  # seconds a backdrop loads, unseen (the loader layer), before it shows
BATCH = 60  # titles fetched at a time, at random
W, H = 1920, 1080  # the layout's design size, scaled to the window's (layout)


def layout(width, height):
    """The controls' rectangles (x, y, w, h) for a window this size. Kodi
    lays add-on windows out on a 1280x720 grid, not 1920x1080: drawn at
    1920x1080 sizes, only the top left of each backdrop showed and the logo
    and name sat below the bottom edge, so no logo ever appeared."""
    sx, sy = float(width or 1280) / W, float(height or 720) / H

    def rect(x, y, w, h):
        return int(x * sx), int(y * sy), int(w * sx), int(h * sy)
    return {'backdrop': rect(0, 0, W, H), 'logo': rect(120, H - 340, 640, 220),
            'name': rect(120, H - 200, 1200, 90)}


def titles(rand=random):
    """Films and shows with a backdrop, in random order: [{'fanart', 'logo', 'name'}]."""
    found = []
    for method, key in (('VideoLibrary.GetMovies', 'movies'), ('VideoLibrary.GetTVShows', 'tvshows')):
        answer = kodi.jsonrpc(method, properties=['art', 'title'], sort={'method': 'random'},
                              limits={'start': 0, 'end': BATCH}) or {}
        found += answer.get(key) or []
    out = [{'fanart': (t.get('art') or {}).get('fanart'), 'logo': (t.get('art') or {}).get('clearlogo') or '',
            'name': t.get('title') or ''} for t in found if (t.get('art') or {}).get('fanart')]
    rand.shuffle(out)
    return out


class Screensaver(xbmcgui.WindowDialog):
    """Two backdrop layers taking turns (one fades in over the other), a logo
    and a name; closes when Kodi ends the screensaver."""

    def __init__(self):
        xbmcgui.WindowDialog.__init__(self)
        rects = layout(self.getWidth(), self.getHeight())
        # Black beneath everything: the home screen never shows through, even
        # before the first backdrop has loaded.
        white = os.path.join(kodi.addon().getAddonInfo('path'), 'resources', 'media', 'white.png')
        self.addControl(xbmcgui.ControlImage(*rects['backdrop'], filename=white, aspectRatio=0,
                                             colorDiffuse='FF000000'))
        # The loader: fully transparent, so it shows nothing, but drawn, so
        # Kodi loads (and caches) each backdrop before a layer shows it.
        self.loader = xbmcgui.ControlImage(*rects['backdrop'], filename='', aspectRatio=2, colorDiffuse='00FFFFFF')
        self.addControl(self.loader)
        self.layers = []
        drift = [('conditional', 'effect=zoom start=100 end=108 center=auto time=%d condition=true' % (SLIDE * 1000 + FADE)),
                 ('visiblechange', 'effect=fade time=%d' % FADE)]
        for _ in range(2):
            layer = xbmcgui.ControlImage(*rects['backdrop'], filename='', aspectRatio=2, colorDiffuse='FFBEBEBE')
            self.addControl(layer)
            layer.setAnimations(drift)
            layer.setVisible(False)
            self.layers.append(layer)
        self.logo_loader = xbmcgui.ControlImage(*rects['logo'], filename='', aspectRatio=2, colorDiffuse='00FFFFFF')
        self.addControl(self.logo_loader)
        self.logo = xbmcgui.ControlImage(*rects['logo'], filename='', aspectRatio=2)
        self.name = xbmcgui.ControlLabel(*rects['name'], label='', font='font_MainMenu', textColor='FFEDEDED')
        for control in (self.logo, self.name):
            self.addControl(control)
            control.setAnimations([('visiblechange', 'effect=fade time=%d' % FADE)])
        self.ended = False
        self.top_shown = False  # which backdrop layer shows: the first goes on top

    def onAction(self, action):
        # Any key ends it (Kodi also says so to Monitor when it's the screensaver).
        self.ended = True
        self.close()

    def show_title(self, title, wait=lambda seconds: False):
        """The next backdrop with its logo, never through a see-through moment
        and never the logo first: it loads on the transparent loader layer
        for PRELOAD seconds, then shows from Kodi's cache, on the top layer
        fading in over the bottom one or on the bottom one (covered by the
        top) as the top fades out. wait(seconds) is True to stop."""
        self.loader.setImage(title['fanart'], True)
        self.logo_loader.setImage(title['logo'], True)
        if wait(PRELOAD):
            return
        bottom, top = self.layers
        self.top_shown = not self.top_shown
        if not self.top_shown:
            bottom.setImage(title['fanart'], True)
            bottom.setVisible(True)
            top.setVisible(False)
        else:
            top.setImage(title['fanart'], True)
            top.setVisible(True)
        self.logo.setImage(title['logo'], True)
        self.logo.setVisible(bool(title['logo']))
        self.name.setLabel(title['name'] if not title['logo'] else '')


class Monitor(xbmc.Monitor):
    def __init__(self, on_end):
        xbmc.Monitor.__init__(self)
        self.on_end = on_end

    def onScreensaverDeactivated(self):
        self.on_end()


def run():
    state = {'running': True}
    window = Screensaver()

    def end():
        state['running'] = False
    monitor = Monitor(end)
    window.show()
    def pause(seconds, monitor=monitor, window=window):
        """Wait; True when the screensaver should end."""
        for _ in range(int(seconds * 4)):
            if monitor.waitForAbort(0.25) or not state['running'] or window.ended:
                return True
        return False
    queue = []
    while state['running'] and not window.ended and not monitor.abortRequested():
        if not queue:
            queue = titles()
            if not queue:
                break  # no artwork (not signed in, or nothing synced): Kodi's black screen
        window.show_title(queue.pop(), pause)
        if pause(SLIDE):
            break
    window.close()
    del window, monitor, pause  # pause holds them too: Kodi frees the window only when all are gone
