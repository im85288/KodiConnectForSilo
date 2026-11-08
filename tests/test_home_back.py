# -*- coding: utf-8 -*-
"""Back on Skyline's Home: the TV page's preview doesn't take it full screen."""
import xbmc

from resources.lib.silokodi import context


def back(monkeypatch, true):
    ran = []
    monkeypatch.setattr(xbmc, 'getCondVisibility', lambda condition: condition in true)
    monkeypatch.setattr(xbmc, 'executebuiltin', ran.append)
    context.home_back()
    return ran


def test_back_on_the_tv_pages_rows_goes_to_its_tab(monkeypatch):
    assert back(monkeypatch, {context.TV_PREVIEWING}) == ['SetFocus(9006)']


def test_back_on_the_bar_with_the_preview_goes_full_screen_as_before(monkeypatch):
    assert back(monkeypatch, {context.TV_PREVIEWING, 'ControlGroup(9000).HasFocus()'}) == ['Action(Back)']


def test_back_elsewhere_is_kodis(monkeypatch):
    assert back(monkeypatch, set()) == ['Action(Back)']
