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


def test_tuning_partway_into_a_catch_up_programme_offers_its_start_for_a_while(props):
    p, _ = prompts(show('Match', NOW - 600, NOW + 3000), show('News', NOW + 3000, NOW + 4800))
    p.tick(True, NOW)
    assert props['startover.title'] == 'Match'
    p.tick(True, NOW + liveprompts.STARTOVER_SHOW)
    assert props['startover.title'] == ''


@pytest.mark.parametrize('now_show, archive', [
    (show('Just begun', NOW - 30, NOW + 3000), True),
    (show('Nearly over', NOW - 3000, NOW + 100), True),
    (show('No catch-up', NOW - 600, NOW + 3000), False),
])
def test_no_start_offered_when_just_begun_nearly_over_or_without_catch_up(props, now_show, archive):
    p, _ = prompts(now_show, None, archive)
    p.tick(True, NOW)
    assert not props.get('startover.title')


def test_ok_on_the_offer_ends_it_and_no_coming_up_next_after(props):
    p, _ = prompts(show('Match', NOW - 600, NOW + 300), show('News', NOW + 300, NOW + 900))
    p.tick(True, NOW)
    props['startover.done'] = '1'  # Skyline, as OK seeks to the start
    p.tick(True, NOW + 1)
    assert props['startover.title'] == '' and props['startover.done'] == ''
    p.tick(True, NOW + 250)
    assert not props.get('next.title')


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


def test_leaving_full_screen_clears_the_notes_and_catch_up_is_left_alone(props):
    p, _ = prompts(show('Match', NOW - 600, NOW + 3000), None)
    p.tick(True, NOW)
    p.tick(False, NOW + 1)
    assert props['startover.title'] == ''
    q, calls = prompts(show('Match', NOW - 600, NOW + 3000), None, channel=None)
    q.tick(True, NOW)
    q.tick(True, NOW + 1)
    assert calls == [] and not props.get('startover.title')
