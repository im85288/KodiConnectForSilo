# -*- coding: utf-8 -*-
from resources.lib.silokodi import subtitleprefs

TRACKS = [
    {'index': 0, 'language': 'eng', 'name': 'English (Forced)', 'isforced': True, 'isimpaired': False},
    {'index': 1, 'language': 'eng', 'name': 'English', 'isforced': False, 'isimpaired': False},
    {'index': 2, 'language': 'eng', 'name': 'English SDH', 'isforced': False, 'isimpaired': True},
    {'index': 3, 'language': 'fre', 'name': 'Français', 'isforced': False, 'isimpaired': False},
]


def test_no_choice_leaves_kodi_alone():
    assert subtitleprefs.pick(None, TRACKS) is None
    assert subtitleprefs.pick({'subtitle_mode': ''}, TRACKS) is None


def test_off_turns_subtitles_off():
    assert subtitleprefs.pick({'subtitle_mode': 'off'}, TRACKS) == 'off'
    assert subtitleprefs.pick({'subtitle_track_index': -1}, TRACKS) == 'off'


def test_the_track_most_like_the_remembered_one_in_its_language():
    plain = {'subtitle_mode': 'always', 'subtitle_language': 'en',
             'track_signature': {'language': 'eng', 'forced': False, 'hearing_impaired': False}}
    assert subtitleprefs.pick(plain, TRACKS) == 1
    sdh = dict(plain, track_signature={'language': 'eng', 'hearing_impaired': True})
    assert subtitleprefs.pick(sdh, TRACKS) == 2
    assert subtitleprefs.pick({'subtitle_mode': 'always', 'subtitle_language': 'fr'}, TRACKS) == 3
    # A language the episode has no track in: Kodi's own default stands.
    assert subtitleprefs.pick({'subtitle_mode': 'always', 'subtitle_language': 'de'}, TRACKS) is None


def test_the_choice_saved_round_trips():
    saved = subtitleprefs.choice(True, TRACKS[2])
    assert saved['subtitle_mode'] == 'always' and saved['subtitle_language'] == 'en'
    assert saved['track_signature']['hearing_impaired'] is True
    assert subtitleprefs.pick(saved, TRACKS) == 2
    assert subtitleprefs.choice(False, TRACKS[1]) == {'subtitle_mode': 'off', 'subtitle_track_index': -1}


# The profile's rules, as Silo's web player applies them (resolveSubtitleAutoSelect).

def rule(mode='auto', language=None, forced=True):
    return {'mode': mode, 'language': language, 'forced': forced}


def test_rules_come_from_the_titles_effective_settings():
    assert subtitleprefs.rules({}) == rule()
    item = {'effective_subtitle_mode': 'always', 'effective_subtitle_language': 'fr',
            'effective_show_forced_subtitles': False}
    assert subtitleprefs.rules(item) == rule('always', 'fr', False)


def test_forced_track_in_the_audios_language():
    # English audio with Farsi scenes: Auto with English subtitles, or none set, or Off.
    for mode, language in (('auto', 'en'), ('auto', None), ('off', None), ('off', 'en')):
        assert subtitleprefs.profile_pick(rule(mode, language), TRACKS, 'eng') == 0
    assert subtitleprefs.profile_pick(rule('auto', 'en', forced=False), TRACKS, 'eng') is None
    # No forced track in the audio's language, or the audio's language unknown: Kodi's choice stands.
    assert subtitleprefs.profile_pick(rule('off'), TRACKS, 'fre') is None
    assert subtitleprefs.profile_pick(rule('off'), TRACKS, '') is None


def test_auto_shows_full_subtitles_for_audio_in_another_language():
    assert subtitleprefs.profile_pick(rule('auto', 'en'), TRACKS, 'jpn') == 1
    assert subtitleprefs.profile_pick(rule('auto', 'fr'), TRACKS, 'eng') == 3
    assert subtitleprefs.profile_pick(rule('auto', ''), TRACKS, 'jpn') is None  # "no subtitles"


def test_always_shows_the_languages_full_track():
    assert subtitleprefs.profile_pick(rule('always', 'en'), TRACKS, 'eng') == 1
    assert subtitleprefs.profile_pick(rule('always', 'de'), TRACKS, 'eng') is None
    assert subtitleprefs.profile_pick(rule('always'), TRACKS, 'eng') is None
    assert subtitleprefs.profile_pick(None, TRACKS, 'eng') is None


def test_sidecar_names_carry_language_and_forced_flag():
    assert subtitleprefs.sidecar_name({'language': 'en', 'forced': True, 'codec': 'subrip',
                                       'label': 'English (Forced)'}) == 'English.en.forced.srt'
    assert subtitleprefs.sidecar_name({'language': 'pt-BR', 'codec': 'webvtt', 'hearing_impaired': True}) \
        == 'Silo-SDH.pt.vtt'
    assert subtitleprefs.sidecar_name({'language': 'und', 'codec': 'ass', 'label': 'Default'}) == 'Silo.ass'
