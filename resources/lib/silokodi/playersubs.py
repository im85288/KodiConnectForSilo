# -*- coding: utf-8 -*-
"""Subtitles in the player: Search online's chosen subtitle put on after
its restart, and the subtitle Silo picks (subtitleprefs: a show's remembered
choice, else the profile's rules, forced subtitles among them) put on when a
title starts; a show's choice saved when the viewer changes it. Functions of the
service (its client, its playback sessions)."""
import threading
import time

import requests

from . import kodi, subtitleprefs
from .api import ApiError


def subtitle_languages():
    """Kodi's preferred subtitle language as Silo's search takes it (English
    names are accepted), English as well; English alone without one."""
    setting = (kodi.jsonrpc('Settings.GetSettingValue', setting='locale.subtitlelanguage') or {}).get('value') or ''
    named = setting not in ('', 'original', 'default', 'forced_only', 'none')
    return [setting, 'English'] if named and setting != 'English' else ['English']


def apply_pick(service, player, session):
    """After Search online's restart: back to where it was, the new
    subtitle on (Kodi adds the session's sidecars after the file's own
    tracks, in order, a moment after the video starts)."""
    pick, service.subtitle_pick = service.subtitle_pick, None
    if not pick:
        return False
    stored_id, position = pick
    def apply():
        try:
            if position:
                player.seekTime(position)
            marker = 'downloaded_subtitle_id=%s' % stored_id
            wanted = [i for i, url in enumerate(session.subtitles) if marker in url]
            for _ in range(20):
                streams = player.getAvailableSubtitleStreams()
                if wanted and len(streams) >= len(session.subtitles):
                    player.setSubtitleStream(len(streams) - len(session.subtitles) + wanted[0])
                    player.showSubtitles(True)
                    return
                time.sleep(0.5)
            kodi.log_warning('Downloaded subtitle %s not among the player\'s tracks' % stored_id)
        except RuntimeError:
            pass
    thread = threading.Thread(target=apply, name='silokodi-subtitle')
    thread.daemon = True
    thread.start()
    return True

def player_audio_language():
    """The language of the audio track Kodi plays ('' when unknown)."""
    answer = kodi.jsonrpc('Player.GetProperties', playerid=1, properties=['currentaudiostream']) or {}
    return (answer.get('currentaudiostream') or {}).get('language') or ''


def player_subtitles():
    """(enabled, the current track, every track) from Kodi's video player."""
    answer = kodi.jsonrpc('Player.GetProperties', playerid=1,
                          properties=['subtitles', 'currentsubtitle', 'subtitleenabled']) or {}
    return bool(answer.get('subtitleenabled')), answer.get('currentsubtitle') or {}, answer.get('subtitles') or []

def target_for(pref, rule, tracks, audio_language):
    """What to put on as a title starts: the show's remembered choice first
    ('off' or a track); with none (or none that fits this episode) the
    profile's rules, which only ever put a track on. Remembered 'off' still
    shows the audio's forced track, as Silo's apps do."""
    target = subtitleprefs.pick(pref, tracks)
    if target == 'off':
        forced = subtitleprefs.profile_pick(dict(rule or {}, mode='off'), tracks, audio_language)
        return 'off' if forced is None else forced
    if target is not None:
        return target
    return subtitleprefs.profile_pick(rule, tracks, audio_language)


def apply_pref(service, session):
    """A title starts: the subtitle Silo would pick (target_for), once Kodi
    has added the session's sidecar tracks."""
    if not session.series_id and not session.subtitle_rules:
        return

    def apply():
        pref = None
        if session.series_id:
            try:
                pref = service.client.get('/subtitle-prefs/%s' % session.series_id)
            except (ApiError, requests.RequestException):
                pref = None  # none stored (404), or Silo unreachable: the profile's rules
        tracks, count = [], -1
        for _ in range(10):  # until the sidecars are in (their count stops changing)
            time.sleep(0.5)
            enabled, current, tracks = player_subtitles()
            if len(tracks) == count:
                break
            count = len(tracks)
        target = target_for(pref, session.subtitle_rules, tracks, player_audio_language())
        if target == 'off':
            kodi.jsonrpc('Player.SetSubtitle', playerid=1, subtitle='off')
        elif target is not None and not (enabled and current.get('index') == target):
            kodi.jsonrpc('Player.SetSubtitle', playerid=1, subtitle=target, enable=True)
        enabled, current, _ = player_subtitles()
        session.subtitle_state = (enabled, current.get('index'))
        if target is not None:
            kodi.log('Subtitles for %s as Silo picks them: %s' % (session.content_id, target))
    thread = threading.Thread(target=apply, name='silokodi-subtitle-pref')
    thread.daemon = True
    thread.start()


def save_choice(service, session):
    """Each second while an episode plays: a subtitle change the viewer
    made is saved as the show's choice, once it has settled (3 s), so the
    next episode, here or in Silo's apps, starts the same way."""
    if not session or not session.series_id or session.subtitle_state is None:
        return
    enabled, current, _ = player_subtitles()
    state = (enabled, current.get('index'))
    if state == session.subtitle_state:
        session.subtitle_changed = None
        return
    changed = getattr(session, 'subtitle_changed', None)
    if not changed or changed[0] != state:
        session.subtitle_changed = (state, time.time())
        return
    if time.time() - changed[1] < 3:
        return
    session.subtitle_state, session.subtitle_changed = state, None
    try:
        service.client.request('PUT', '/subtitle-prefs/%s' % session.series_id,
                            body=subtitleprefs.choice(enabled, current))
        kodi.log('Saved the subtitle choice for series %s' % session.series_id)
    except (ApiError, requests.RequestException) as error:
        kodi.log_warning('Could not save the subtitle choice: %s' % error)
