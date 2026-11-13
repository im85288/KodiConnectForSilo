# -*- coding: utf-8 -*-
"""Subtitle choices as Silo's apps make them.

A show's remembered choice: Silo stores one per profile and series
(subtitle-prefs); its own apps apply it when an episode starts and save it
when the viewer changes track, so a choice made on one device follows to the
next episode on any of them.

The profile's rules, for any title: a subtitle mode (auto, always, off), a
subtitle language and "show forced subtitles", which the title's details
resolve (effective_*, library overrides included). Silo's playback plan
applies neither; the client does, here with Kodi's subtitle tracks (JSON-RPC
Player.GetProperties' subtitles), as Silo's web player does
(resolveSubtitleAutoSelect).
"""
import re

# Sidecar codecs Kodi reads, and the extension a sidecar's name gets.
SIDECAR_EXTENSIONS = {'srt': 'srt', 'subrip': 'srt', 'vtt': 'vtt', 'webvtt': 'vtt', 'ass': 'ass', 'ssa': 'ssa'}
# Words Kodi takes as flags in a subtitle's file name, kept out of its label.
KODI_FLAG_WORDS = ('forced', 'default', 'none')


def language_key(code):
    """A language as one comparable key: Kodi's tracks say 'eng', Silo 'en'."""
    code = (code or '').strip().lower().split('-')[0]
    return {'eng': 'en', 'fre': 'fr', 'fra': 'fr', 'ger': 'de', 'deu': 'de', 'spa': 'es', 'ita': 'it',
            'dut': 'nl', 'nld': 'nl', 'por': 'pt', 'swe': 'sv', 'nor': 'no', 'nob': 'no', 'dan': 'da',
            'fin': 'fi', 'pol': 'pl', 'rus': 'ru', 'jpn': 'ja', 'chi': 'zh', 'zho': 'zh', 'kor': 'ko',
            'ara': 'ar', 'heb': 'he', 'tur': 'tr', 'gre': 'el', 'ell': 'el', 'cze': 'cs', 'ces': 'cs',
            'hun': 'hu', 'rum': 'ro', 'ron': 'ro', 'hin': 'hi'}.get(code, code)


def pick(pref, tracks):
    """What the remembered choice means for this episode's tracks: 'off', a
    track's index, or None (no choice, or no track in its language: Kodi's
    own default stands). A track like the remembered one (forced and
    hearing-impaired flags, then its label) wins over others in its language."""
    if not pref:
        return None
    if pref.get('subtitle_mode') == 'off' or pref.get('subtitle_track_index') == -1:
        return 'off'
    signature = pref.get('track_signature') or {}
    wanted = language_key(pref.get('subtitle_language') or signature.get('language'))
    if not wanted:
        return None
    same = [t for t in tracks if language_key(t.get('language')) == wanted]
    if not same:
        return None

    def likeness(track):
        return ((bool(track.get('isforced')) == bool(signature.get('forced'))) * 4
                + (bool(track.get('isimpaired')) == bool(signature.get('hearing_impaired'))) * 2
                + (bool(signature.get('label')) and track.get('name') == signature.get('label')))
    return max(same, key=likeness)['index']


def choice(enabled, track):
    """The preference to store for the track now showing (None when off)."""
    if not enabled or not track:
        return {'subtitle_mode': 'off', 'subtitle_track_index': -1}
    return {'subtitle_mode': 'always', 'subtitle_language': language_key(track.get('language')) or '',
            'subtitle_track_index': int(track.get('index') or 0),
            'track_signature': {'language': track.get('language') or '', 'label': track.get('name') or '',
                                'forced': bool(track.get('isforced')),
                                'hearing_impaired': bool(track.get('isimpaired'))}}


def rules(item):
    """The profile's subtitle rules for a title, from its details: mode
    (auto when unset, as Silo's apps take it), language (None when unset, ''
    for "no subtitles") and whether forced subtitles show (on by default)."""
    forced = item.get('effective_show_forced_subtitles')
    return {'mode': item.get('effective_subtitle_mode') or 'auto',
            'language': item.get('effective_subtitle_language'),
            'forced': True if forced is None else bool(forced)}


def _best(tracks, language):
    """The best track in a language: full before forced, then not SDH."""
    same = [t for t in tracks if language_key(t.get('language')) == language]
    if not same:
        return None
    return min(same, key=lambda t: (bool(t.get('isforced')), bool(t.get('isimpaired')), t.get('index', 0)))['index']


def _forced_for(tracks, audio):
    """The forced track in the audio's language, if there is one."""
    if not audio or audio == 'und':
        return None
    forced = [t for t in tracks if t.get('isforced') and language_key(t.get('language')) == audio]
    return min(forced, key=lambda t: (bool(t.get('isimpaired')), t.get('index', 0)))['index'] if forced else None


def profile_pick(rule, tracks, audio_language):
    """The track the profile's rules put on (an index), or None: then
    Kodi's own choice stands. As Silo's apps: Off shows only a forced track in
    the audio's language; Always the subtitle language's best track; Auto the
    subtitle language's track when the audio is in another language, else
    the audio's forced track. Forced tracks only with forced subtitles on."""
    if not rule:
        return None
    audio = language_key(audio_language)
    wanted = language_key(rule.get('language'))

    def forced():
        return _forced_for(tracks, audio) if rule.get('forced') else None
    mode = rule.get('mode')
    if mode == 'off':
        return forced()
    if mode == 'always':
        return _best(tracks, wanted) if wanted else None
    if mode == 'auto':
        if rule.get('language') == '':
            return None
        if not wanted or wanted == audio:
            return forced()
        return _best(tracks, wanted)
    return None


def sidecar_name(entry):
    """A file name for a sidecar from Silo's inventory, which Kodi reads for
    its language and forced flag (name.en.forced.srt): Silo's sidecar links
    end in a bare number."""
    label = re.sub(r'[^A-Za-z0-9]+', ' ', entry.get('label') or '').split()
    words = [w for w in label if w.lower() not in KODI_FLAG_WORDS] or ['Silo']
    if entry.get('hearing_impaired') and 'SDH' not in words:
        words.append('SDH')
    parts = ['-'.join(words)]
    language = language_key(entry.get('language'))
    if language and language != 'und':
        parts.append(language)
    if entry.get('forced'):
        parts.append('forced')
    parts.append(SIDECAR_EXTENSIONS.get((entry.get('codec') or '').lower(), 'srt'))
    return '.'.join(parts)
