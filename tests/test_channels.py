# -*- coding: utf-8 -*-
import sqlite3

from resources.lib.silokodi import channels

CHANNELS = [{'channelid': 1, 'label': 'BBC News'}, {'channelid': 2, 'label': 'Sky Sports'},
            {'channelid': 3, 'label': 'Never watched'}, {'channelid': 4, 'label': 'Hidden', 'hidden': True},
            {'channelid': 5, 'label': 'Premier Sports'}]
WATCHED = {1: 1000, 2: 3000, 4: 4000, 5: 2000}


def test_recent_channels_are_newest_first_without_the_playing_one():
    assert [c['channelid'] for c in channels.recent(CHANNELS, WATCHED)] == [2, 5, 1]
    assert [c['channelid'] for c in channels.recent(CHANNELS, WATCHED, playing=2)] == [5, 1]


def test_a_removed_channel_comes_back_once_watched_again():
    removed = {'5': 2000}
    assert [c['channelid'] for c in channels.recent(CHANNELS, WATCHED, removed=removed)] == [2, 1]
    assert [c['channelid'] for c in channels.recent(CHANNELS, {**WATCHED, 5: 5000}, removed=removed)] == [5, 2, 1]


def test_previous_is_the_last_channel_before_the_playing_one():
    assert channels.previous(CHANNELS, WATCHED, playing=2)['channelid'] == 5
    assert channels.previous([], WATCHED, playing=2) is None


def test_last_watched_times_come_from_the_newest_tv_database(tmp_path, monkeypatch):
    for name, rows in (('TV9.db', [(1, 50)]), ('TV46.db', [(1, 1000), (2, 0), (5, 2000)])):
        db = sqlite3.connect(str(tmp_path / name))
        db.execute('CREATE TABLE channels (idChannel INTEGER, iLastWatched INTEGER)')
        db.executemany('INSERT INTO channels VALUES (?, ?)', rows)
        db.commit()
        db.close()
    monkeypatch.setattr(channels.kodi, 'database_dir', lambda: str(tmp_path))
    assert channels.last_watched() == {1: 1000, 5: 2000}


def _schedule():
    import datetime
    day = lambda d, h: datetime.datetime(2026, 10, d, h).timestamp()
    broadcasts = [{'broadcastid': 1, 'title': 'Late', 'start': day(27, 22), 'end': day(27, 23)},
                  {'broadcastid': 2, 'title': 'Breakfast', 'start': day(28, 7), 'end': day(28, 8)},
                  {'broadcastid': 3, 'title': 'Cricket', 'start': day(28, 8), 'end': day(28, 16)},
                  {'broadcastid': 4, 'title': 'Desk', 'start': day(28, 16), 'end': day(28, 19)},
                  {'broadcastid': 5, 'title': 'Football', 'start': day(28, 19), 'end': day(28, 22)},
                  {'broadcastid': 6, 'title': 'Old', 'start': day(10, 9), 'end': day(10, 10)},
                  {'broadcastid': 7, 'title': 'Tomorrow', 'start': day(29, 9), 'end': day(29, 10)}]
    return channels.schedule_rows(broadcasts, day(28, 20), archive=True), day


def test_guide_times_parse_without_strptime():
    import calendar
    import time
    from resources.lib.silokodi.channels import utc_seconds
    for stamp in ('2026-11-01 20:00:00', '2026-01-31 00:05:09'):
        assert utc_seconds(stamp) == calendar.timegm(time.strptime(stamp, '%Y-%m-%d %H:%M:%S'))


def test_a_preview_isnt_watching(tmp_path, monkeypatch):
    from resources.lib.silokodi import channels
    monkeypatch.setattr(channels.kodi, 'profile_dir', lambda: str(tmp_path))
    channels.note_preview(7, now=1000, kodi_watched={7: 500})
    channels.note_preview(8, now=1000, kodi_watched={})
    channels.note_preview(7, now=1100, kodi_watched={7: 1000})  # again: its time from before stays
    previews = channels.load_previews()
    assert channels.without_previews({7: 1100, 8: 1001, 9: 900}, previews) == {7: 500, 9: 900}
    # Kodi's time from before the preview (the file outlived a reset): Kodi's
    assert channels.without_previews({7: 900}, {'7': {'at': 1100, 'before': 500}}) == {7: 900}
    channels.note_watched(7)  # full screen
    assert channels.without_previews({7: 1100, 8: 1001}, channels.load_previews()) == {7: 1100}


def test_restart_offers_catch_up_channels_well_into_a_programme_recent_first():
    from resources.lib.silokodi import plugin
    now = 1_800_000_000
    import time as _t
    def at(epoch):
        return _t.strftime('%Y-%m-%d %H:%M:%S', _t.gmtime(epoch))
    def channel(cid, number, archive, start, end, hidden=False):
        return {'channelid': cid, 'channelnumber': number, 'hasarchive': archive, 'hidden': hidden,
                'broadcastnow': {'title': 'P%d' % cid, 'starttime': at(start), 'endtime': at(end)}}
    found = [channel(1, 1, True, now - 1800, now + 1800),     # in
             channel(2, 2, False, now - 1800, now + 1800),    # no catch-up
             channel(3, 3, True, now - 60, now + 3600),       # only just begun
             channel(4, 4, True, now - 3000, now + 300),      # nearly over
             channel(5, 5, True, now - 900, now + 1800),      # in, watched more recently
             channel(6, 6, True, now - 900, now + 1800)]      # filler: left out
    found[-1]['broadcastnow']['title'] = 'This is TNT Sports Ultimate'
    picked = plugin.restart_choices(found, {5: 2000, 1: 1000}, now)
    assert [c['channelid'] for c, *_ in picked] == [5, 1]


def test_left_or_right_plays_the_channel_watched_before(monkeypatch):
    from resources.lib.silokodi import kodi, plugin
    opened, notes = [], []
    monkeypatch.setattr(plugin, 'tv_channels', lambda: [{'channelid': 1, 'label': 'Sky News'},
                                                        {'channelid': 2, 'label': 'CNN'}, {'channelid': 3, 'label': 'F1'}])
    monkeypatch.setattr(plugin, 'playing_channel', lambda: 1)
    monkeypatch.setattr(plugin.channels, 'last_watched', lambda: {1: 300, 2: 200, 3: 100})
    monkeypatch.setattr(kodi, 'jsonrpc', lambda method, **kw: opened.append((method, kw)))
    monkeypatch.setattr(kodi, 'notify', notes.append)
    plugin.last_channel()
    assert opened == [('Player.Open', {'item': {'channelid': 2}})]
    monkeypatch.setattr(plugin, 'tv_channels', lambda: [{'channelid': 1, 'label': 'Sky News'}])
    plugin.last_channel()
    assert len(opened) == 1 and notes
