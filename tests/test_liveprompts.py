# -*- coding: utf-8 -*-
import pytest

from resources.lib.silokodi import kodi, liveprompts

NOW = 1_800_000_000


@pytest.fixture
def props(monkeypatch):
    store = {}
    monkeypatch.setattr(kodi, 'get_property', lambda key: store.get(key, ''))
    monkeypatch.setattr(kodi, 'set_property', lambda key, value: store.__setitem__(key, value))
    monkeypatch.setattr(kodi, 'log', lambda *a, **k: None)
    return store


def show(title, start, end, thumbnail=''):
    return {'title': title, 'start': start, 'end': end, 'thumbnail': thumbnail}


def prompts(now_show, next_show, archive=True, channel=7):
    calls = []

    def fetcher(channelid):
        calls.append(channelid)
        return now_show, next_show, archive
    p = liveprompts.Prompts(fetcher=fetcher, playing=lambda: channel)
    return p, calls


def test_coming_up_next_shows_once_near_the_end(props):
    p, _ = prompts(show('Match', NOW - 60, NOW + 500), show('News', NOW + 500, NOW + 900, 'pic.jpg'))
    p.tick(True, NOW)
    assert not props.get('next.title')
    p.tick(True, NOW + 500 - liveprompts.NEXT_BEFORE)
    assert props['next.title'] == 'News' and props['next.picture'] == 'pic.jpg' and props['next.time']
    p.tick(True, NOW + 500 - liveprompts.NEXT_BEFORE + liveprompts.NEXT_SHOW)
    assert props['next.title'] == ''
    p.tick(True, NOW + 499)
    assert props['next.title'] == ''


def test_kodi_is_asked_again_only_as_the_programme_or_channel_changes(props):
    p, calls = prompts(show('Match', NOW - 60, NOW + 500), None)
    for second in range(10):
        p.tick(True, NOW + second)
    assert calls == [7]
    p.tick(True, NOW + 500)
    assert calls == [7, 7]
    for second in range(501, 510):  # the guide still has nothing newer: not each second
        p.tick(True, NOW + second)
    assert calls == [7, 7]
    p.changed()
    p.tick(True, NOW + 511)
    assert calls == [7, 7, 7]


def test_leaving_full_screen_clears_coming_up_next_and_catch_up_is_left_alone(props):
    p, _ = prompts(show('Match', NOW - 60, NOW + 100), show('News', NOW + 100, NOW + 900))
    p.tick(True, NOW)
    assert props['next.title'] == 'News'
    p.tick(False, NOW + 1)
    assert props['next.title'] == ''
    q, calls = prompts(show('Match', NOW - 60, NOW + 100), None, channel=None)
    q.tick(True, NOW)
    q.tick(True, NOW + 1)
    assert calls == [] and not props.get('startover.title')
