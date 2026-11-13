# -*- coding: utf-8 -*-
from resources.lib.silokodi import playersubs
from tests.test_subtitleprefs import TRACKS, rule


def test_a_shows_remembered_choice_comes_first():
    pref = {'subtitle_mode': 'always', 'subtitle_language': 'fr'}
    assert playersubs.target_for(pref, rule('auto', 'en'), TRACKS, 'eng') == 3


def test_remembered_off_still_shows_the_forced_track():
    off = {'subtitle_mode': 'off'}
    assert playersubs.target_for(off, rule(), TRACKS, 'eng') == 0
    assert playersubs.target_for(off, rule(forced=False), TRACKS, 'eng') == 'off'
    assert playersubs.target_for(off, None, TRACKS, 'eng') == 'off'


def test_without_a_remembered_choice_the_profiles_rules_apply():
    assert playersubs.target_for(None, rule('auto', 'en'), TRACKS, 'eng') == 0
    assert playersubs.target_for(None, None, TRACKS, 'eng') is None
