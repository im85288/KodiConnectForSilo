# -*- coding: utf-8 -*-
"""Skyline's TV page: Recent channels, the guide's groups, Catch up and My teams."""
import datetime

from resources.lib.silokodi import tvrows

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 11, 7, 15, 30, tzinfo=UTC)

PLAYLIST = '''#EXTM3U
#EXTINF:-1 tvg-id="BossSports.EPL.03" group-title="Live | English Premier League - EPL",EPL03: Fulham 15:00 Newcastle Utd 07/11
http://x/1.ts
#EXTINF:-1 tvg-id="NewcastleUnited.epl" group-title="Live | EPL Teams",Newcastle United
http://x/2.ts
#EXTINF:-1 tvg-id="iptv-event.512" group-title="USA | Peacock Events",Peacock 12: Fulham v. Newcastle (Español) @ 7 Nov 10:55 AM ET
http://x/3.ts
#EXTINF:-1 tvg-id="SkyPL.uk" group-title="UK | Sky Sports",Sky Sports Premier League
http://x/4.ts
#EXTINF:-1 tvg-id="TNT1.uk" group-title="UK | TNT Sports",TNT Sports 1
http://x/5.ts
#EXTINF:-1 tvg-id="Jets.au" group-title="Live | Now HK Sports",NowHK SPOTV
http://x/6.ts
'''

GUIDE = '''<?xml version="1.0" encoding="UTF-8"?><tv>
<programme start="20261107150000 +0000" stop="20261107171500 +0000" channel="BossSports.EPL.03"><title>Fulham v Newcastle Utd</title><category>Sports</category><category>Live</category></programme>
<programme start="20261107030000 +0000" stop="20261107150000 +0000" channel="BossSports.EPL.03"><title>Next: Fulham v Newcastle Utd at 15:00</title></programme>
<programme start="20261107150000 +0000" stop="20261107171500 +0000" channel="NewcastleUnited.epl"><title>Newcastle United @ Fulham  ᴸᶦᵛᵉ</title><desc>Matchday 10</desc></programme>
<programme start="20261107155500 +0000" stop="20261107185500 +0000" channel="iptv-event.512"><title>Fulham v. Newcastle (Español)</title><category>Live</category></programme>
<programme start="20261107223000 +0000" stop="20261108003000 +0000" channel="SkyPL.uk"><title>Premier League : Fulham v Newcastle United</title></programme>
<programme start="20261112173000 +0000" stop="20261112193000 +0000" channel="SkyPL.uk"><title>Premier League 26/27 : Newcastle United v Chelsea ᴸᶦᵛᵉ</title></programme>
<programme start="20261107143000 +0000" stop="20261107163000 +0000" channel="TNT1.uk"><title>Premier League : Arsenal v Hull ᴸᶦᵛᵉ</title><icon src="http://i/a.png"/></programme>
<programme start="20261107150000 +0000" stop="20261107170000 +0000" channel="Jets.au"><title>A-League Men : Perth Glory v Newcastle Jets ᴸᶦᵛᵉ</title></programme>
<programme start="20261107100000 +0000" stop="20261107120000 +0000" channel="TNT1.uk"><title>Earlier Live Thing</title></programme>
</tv>'''

CHANNELS = [
    {'channelid': 1, 'label': 'EPL03: Fulham 15:00 Newcastle Utd 07/11', 'icon': 'epl.png'},
    {'channelid': 2, 'label': 'Newcastle United', 'icon': 'nufc.png'},
    {'channelid': 3, 'label': 'Peacock 12: Fulham v. Newcastle (Español) @ 7 Nov 10:55 AM ET', 'icon': 'p.png'},
    {'channelid': 4, 'label': 'Sky Sports Premier League', 'icon': 'skypl.png', 'lastplayed': '2026-11-07 13:00:00',
     'broadcastnow': {'title': 'Premier League Live', 'progresspercentage': 40.5}},
    {'channelid': 5, 'label': 'TNT Sports 1', 'icon': 'tnt.png', 'lastplayed': '2026-11-07 14:00:00',
     'broadcastnow': {'title': 'Arsenal v Hull', 'progresspercentage': 50.0}},
    {'channelid': 6, 'label': 'NowHK SPOTV', 'icon': 'hk.png'},
    {'channelid': 7, 'label': 'Hidden', 'hidden': True, 'lastplayed': '2026-11-07 15:00:00'},
]


def entries():
    return tvrows.programmes(GUIDE.encode(), tvrows.playlist_names(PLAYLIST), NOW)


def test_only_live_programmes_on_the_playlists_channels():
    titles = sorted(e['title'] for e in entries())
    assert 'Next: Fulham v Newcastle Utd at 15:00' not in titles   # a lead-in
    assert 'Premier League : Fulham v Newcastle United' not in titles  # a replay
    assert 'Earlier Live Thing' not in titles  # over
    assert 'Premier League 26/27 : Newcastle United v Chelsea ᴸᶦᵛᵉ' in titles  # next week, live


def test_a_match_is_one_card_across_its_channels_english_first():
    rows = tvrows.rows(CHANNELS, entries(), ['Newcastle United', 'Newcastle Utd', 'Newcastle'], NOW)
    teams = rows[tvrows.TEAMS_ROW]
    assert [c['card.title'] for c in teams] == ['Fulham v Newcastle Utd', 'Newcastle United v Chelsea']
    today = teams[0]
    assert today['card.sub'] == 'LIVE · 3 channels'
    assert today['tv.play'].endswith('mode=tv_watch&ids=1,2,3')  # the Spanish feed last
    assert today['percent'] == '22'
    assert 'mode=tv_remind' in teams[1]['tv.play'] and '3 channels' not in teams[1]['card.sub']


def test_whole_names_only():
    rows = tvrows.rows(CHANNELS, entries(), ['Newcastle United'], NOW)
    assert all('Jets' not in c['card.title'] for c in rows[tvrows.TEAMS_ROW])


def test_recent_channels_with_whats_on():
    rows = tvrows.rows(CHANNELS, entries(), [], NOW)
    assert [c['card.title'] for c in rows[tvrows.RECENT_ROW]] == ['TNT Sports 1', 'Sky Sports Premier League']
    assert rows[tvrows.RECENT_ROW][0]['percent'] == '50'
    assert rows[tvrows.RECENT_ROW][0]['tv.play'].endswith('mode=play_channel&id=5')


def test_each_guide_group_is_a_row_of_its_channels_by_number():
    groups = tvrows.playlist_groups(PLAYLIST)
    channels = [dict(c, channelnumber=n) for c, n in zip(CHANNELS, (31, 41, 51, 2, 22, 61, 0))]
    channels.append({'channelid': 8, 'label': 'Sky Sports Main Event', 'channelnumber': 1, 'icon': 'me.png',
                     'broadcastnow': {'title': 'Darts', 'endtime': '2026-11-07 16:00:00'}})
    groups['Sky Sports Main Event'] = 'UK | Sky Sports'
    rows = tvrows.rows(channels, entries(), [], NOW, groups=groups)
    titles = rows[tvrows.TITLES]
    # The playlist's group order; a group's channels by their number.
    assert [titles[k] for k in tvrows.GROUP_ROWS if k in titles] == [
        'Live | English Premier League - EPL', 'Live | EPL Teams', 'USA | Peacock Events', 'UK | Sky Sports',
        'UK | TNT Sports']
    sky = rows[titles and [k for k, t in titles.items() if t == 'UK | Sky Sports'][0]]
    assert [c['card.title'] for c in sky] == ['Sky Sports Main Event', 'Sky Sports Premier League']
    assert sky[0]['card.sub'] == 'Darts' and sky[0]['left'] == '30 min left'
    # Every channel, watched or not; a hidden one is left out.
    assert all(c['card.title'] != 'Hidden' for k in tvrows.GROUP_ROWS for c in rows.get(k, []))


def test_the_group_titles_are_kept_for_the_layout(tmp_path):
    path = str(tmp_path / 'rows.json')
    assert tvrows.saved_titles(path) == {}
    tvrows.save_titles({'group1': 'Sky Sports'}, path)
    assert tvrows.saved_titles(path) == {'group1': 'Sky Sports'}


def test_titles_lose_competition_and_season():
    assert tvrows.clean('Premier League 26/27 : Fulham vs Newcastle United ᴸᶦᵛᵉ') == 'Fulham vs Newcastle United'
    assert tvrows.clean('Fulham vs Newcastle United (MW10) - Premier League 2026/27') == 'Fulham vs Newcastle United'
    assert tvrows.clean('Premier League Live') == 'Premier League'


def test_the_settings_say_where_the_guide_is(tmp_path):
    folder = tmp_path / 'pvr.iptvsimple'
    folder.mkdir()
    (folder / 'instance-settings-31.xml').write_text(
        '<settings version="2"><setting id="m3uPathType">1</setting><setting id="m3uUrl">http://h/live.m3u</setting>'
        '<setting id="epgPathType">1</setting><setting id="epgUrl">http://h/epg.xml</setting></settings>')
    assert tvrows.sources(str(tmp_path)) == ('http://h/live.m3u', 'http://h/epg.xml')


def test_team_setting_splits_on_commas_and_lines():
    assert tvrows.team_names('Newcastle United, Newcastle Utd;\nSunderland ') == \
        ['Newcastle United', 'Newcastle Utd', 'Sunderland']


def test_a_shorter_name_is_not_another_team():
    teams = ['Newcastle United', 'Newcastle Utd', 'Newcastle']
    assert tvrows.mentions('Fulham v. Newcastle (Español)', 'Newcastle', teams)
    assert tvrows.mentions('Fulham v Newcastle Utd', 'Newcastle', teams)
    assert tvrows.mentions('Newcastle United @ Fulham', 'Newcastle', teams)
    assert not tvrows.mentions('Perth Glory v Newcastle Jets', 'Newcastle', teams)
    assert not tvrows.mentions('Newcastle Falcons v Bath', 'Newcastle', teams)
    assert not tvrows.mentions('Newcastle United Women v Arsenal', 'Newcastle United', teams)


def test_the_layout_has_the_tv_pages_rows_but_not_as_one_of_silos_pages():
    from resources.lib.silokodi.sync import skin_layout
    layout = skin_layout([], [], {})
    assert 'tv' not in layout['silo.pages'].split(',')
    titles = [layout['silo.tv.%d.title' % n] for n in range(1, len(tvrows.ROWS) + 1)]
    assert titles[0] == 'Recent channels' and titles[-2:] == ['Catch up', 'My teams']
    assert layout['silo.tv.%d.title' % (len(tvrows.ROWS) + 1)] == ''


def test_reminders_toggle_and_fall_due(tmp_path):
    path = str(tmp_path / 'reminders.json')
    assert tvrows.toggle_reminder('1000', ['1', '2'], 'Fulham v Newcastle Utd', path) is True
    assert tvrows.due_reminders(900, path) == []              # too early
    assert tvrows.due_reminders(960, path)[0]['title'] == 'Fulham v Newcastle Utd'  # a minute before
    assert tvrows.load_reminders(path) == {}                  # said once
    tvrows.toggle_reminder('5000', ['1'], 'Later', path)
    assert tvrows.toggle_reminder('5000', ['1'], 'Later', path) is False  # pressed again: removed


def test_every_card_has_a_label():
    """A skin's list leaves out an item with no label or type: the card wouldn't show."""
    rows = tvrows.rows(CHANNELS, entries(), ['Newcastle United', 'Newcastle Utd'], NOW)
    cards = [c for row in rows.values() for c in row]
    assert cards and all(c['label'] and c['type'] for c in cards)


def test_pictures_are_the_programmes_and_logos_stay_logos():
    pictures = {}
    found = tvrows.programmes(GUIDE.encode(), tvrows.playlist_names(PLAYLIST), NOW, pictures)
    rows = tvrows.rows(CHANNELS, found, [], NOW, pictures=pictures)
    tnt = rows[tvrows.RECENT_ROW][0]
    assert tnt['art.landscape'] == 'http://i/a.png'  # what TNT Sports 1 shows now
    assert tnt['tv.logo'] == 'tnt.png'
    sky = rows[tvrows.RECENT_ROW][1]
    assert sky['art.landscape'] == '' and sky['tv.logo'] == 'skypl.png'  # no picture: the logo, centred


def test_the_hero_shows_the_whole_title_then_the_channel_and_times():
    channel = {'channelid': 9, 'label': 'Sky Sports Main Event UHD', 'icon': 'me.png',
               'broadcastnow': {'title': "Saturday Night Football : Nott'm Forest v Man City ᴸᶦᵛᵉ",
                                'starttime': '2026-11-07 17:00:00', 'endtime': '2026-11-07 20:00:00'}}
    card = tvrows.channel_card(channel, NOW)
    assert card['hero.title'] == "Saturday Night Football : Nott'm Forest v Man City"
    assert card['hero.facts'].startswith('Sky Sports Main Event UHD  ·  ')
    plain = tvrows.channel_card({'label': 'Sky Sports News', 'broadcastnow': {'title': 'Soccer Saturday'}}, NOW)
    assert plain['hero.title'] == 'Soccer Saturday' and plain['hero.facts'] == 'Sky Sports News'


def test_the_preview_is_the_last_channel_watched():
    assert tvrows.last_channel(CHANNELS)['label'] == 'TNT Sports 1'  # not the hidden one, though it's later
    assert tvrows.last_channel([{'label': 'Never watched'}]) is None


def test_the_preview_turns_full_screen_off_for_its_start_only(monkeypatch):
    import xbmc
    calls = []
    def jsonrpc(method, **params):
        calls.append((method, params))
        if method == 'Settings.GetSettingValue':
            return {'value': 3}
        if method == 'PVR.GetChannels':
            return {'channels': [dict(c) for c in CHANNELS]}  # copies: kodi_channels sets lastplayed
    monkeypatch.setattr(tvrows.kodi, 'jsonrpc', jsonrpc)
    from resources.lib.silokodi import channels
    monkeypatch.setattr(channels, 'last_watched', lambda: {4: 1000, 5: 2000})  # TNT Sports 1 last
    monkeypatch.setattr(xbmc, 'getCondVisibility', lambda condition: condition in ('Player.HasVideo', tvrows.TV_PAGE_SHOWN))
    monkeypatch.setattr(tvrows.kodi, 'get_property', lambda key: '')
    tvrows.preview()
    assert [c for c in calls if c[0] != 'PVR.GetChannels'] == [
        ('Settings.GetSettingValue', {'setting': tvrows.FULL_SCREEN}),
        ('Settings.SetSettingValue', {'setting': tvrows.FULL_SCREEN, 'value': 0}),
        ('Player.Open', {'item': {'channelid': 5}}),
        ('Settings.SetSettingValue', {'setting': tvrows.FULL_SCREEN, 'value': 3})]


def test_the_preview_waits_after_a_stop():
    assert tvrows.wait_after_stop(1000, '992') == 4   # stopped 8 s ago: 4 more
    assert tvrows.wait_after_stop(1000, '900') == 0   # long ago
    assert tvrows.wait_after_stop(1000, '') == 0      # never


def test_the_preview_never_waits_for_ever(monkeypatch):
    """Kodi's waitForAbort(0) has no timeout: with nothing to wait for, it isn't called with 0."""
    import xbmc
    waits = []

    class Monitor(object):
        def waitForAbort(self, seconds=None):
            waits.append(seconds)
            return False
    monkeypatch.setattr(xbmc, 'Monitor', Monitor)
    monkeypatch.setattr(tvrows.kodi, 'jsonrpc', lambda method, **params: {'channels': [dict(c) for c in CHANNELS]}
                        if method == 'PVR.GetChannels' else {'value': 3})
    monkeypatch.setattr(xbmc, 'getCondVisibility', lambda condition: condition in ('Player.HasVideo', tvrows.TV_PAGE_SHOWN))
    monkeypatch.setattr(tvrows.kodi, 'get_property', lambda key: '')
    tvrows.preview()
    assert 0 not in waits and None not in waits


def test_a_card_plays_its_channel_or_a_matchs_best_feed():
    assert tvrows.card_channel(tvrows.PLUGIN + '?mode=play_channel&id=12') == 12
    assert tvrows.card_channel(tvrows.PLUGIN + '?mode=tv_watch&ids=4,9') == 4
    assert tvrows.card_channel(tvrows.PLUGIN + '?mode=tv_remind&start=1&ids=4&title=x') is None
    assert tvrows.card_channel('') is None


def test_the_preview_follows_a_card_rested_on(monkeypatch):
    follower = tvrows.Follower()
    focused = [12]
    started = []
    monkeypatch.setattr(follower, 'focused', lambda: focused[0])
    def switch(channel):
        started.append(channel)
        follower.switching = False
    monkeypatch.setattr(follower, 'switch', switch)

    class Now(object):  # the thread runs at once
        def __init__(self, target, args, name):
            self.run = lambda: target(*args)
            self.daemon = False

        def start(self):
            self.run()
    import threading
    monkeypatch.setattr(threading, 'Thread', Now)
    follower.tick(100)
    follower.tick(102)
    assert started == []  # not long enough
    follower.tick(103)
    follower.tick(110)
    assert started == [12]  # once
    focused[0] = 7
    follower.tick(111)
    follower.tick(113.5)
    assert started == [12]
    follower.tick(114)
    assert started == [12, 7]


def test_a_live_card_says_how_long_is_left():
    channels = [dict(c) for c in CHANNELS]
    channels[4]['broadcastnow'] = dict(channels[4]['broadcastnow'], endtime='2026-11-07 16:05:00')
    rows = tvrows.rows(channels, entries(), ['Newcastle United', 'Newcastle Utd'], NOW)
    assert rows[tvrows.RECENT_ROW][0]['left'] == '35 min left'  # TNT Sports 1, ends 16:05
    assert rows[tvrows.RECENT_ROW][1]['left'] == ''  # its end isn't known
    assert rows[tvrows.TEAMS_ROW][0]['left'] == '1 h 45 min left'  # live till 17:15
    assert rows[tvrows.TEAMS_ROW][1]['left'] == ''  # next week's


ENDED = GUIDE.replace('</tv>', '''
<programme start="20261107120000 +0000" stop="20261107140000 +0000" channel="TNT1.uk"><title>Premier League : Spurs v Wolves ᴸᶦᵛᵉ</title><icon src="http://i/s.png"/></programme>
<programme start="20261107120000 +0000" stop="20261107140000 +0000" channel="SkyPL.uk"><title>Premier League : Spurs v Wolves ᴸᶦᵛᵉ</title></programme>
<programme start="20261106120000 +0000" stop="20261106140000 +0000" channel="SkyPL.uk"><title>Yesterday's Match ᴸᶦᵛᵉ</title></programme>
<programme start="20261107140000 +0000" stop="20261107140500 +0000" channel="TNT1.uk"><title>Filler</title></programme>
<programme start="20261107080000 +0000" stop="20261107090000 +0000" channel="SkyPL.uk"><title>Morning Show</title></programme>
</tv>''')


def test_catch_up_is_whats_ended_on_channels_with_catch_up():
    ended = []
    found = tvrows.programmes(ENDED.encode(), tvrows.playlist_names(PLAYLIST), NOW, ended=ended)
    channels = [dict(c, hasarchive=c['channelid'] in (4, 5)) for c in CHANNELS]
    rows = tvrows.rows(channels, found, [], NOW, ended=ended)
    catchup = rows[tvrows.CATCHUP_ROW]
    # Newest first: the match (once, its best feed: Sky's ranks above TNT's?
    # both English: the name decides), then TNT's earlier programme. Not the
    # 5-minute filler, nor Sky's 08:00 show (over 6 h ago), nor yesterday's
    # match (over 24 h ago), nor channels without catch-up.
    assert [c['card.title'] for c in catchup] == ['Spurs v Wolves', 'Earlier Thing']
    match = catchup[0]
    assert match['card.sub'].endswith('Today 12:00 – 14:00') and match['left'] == 'Catch up'
    assert 'mode=play_catchup&channel=' in match['tv.play'] and match['tv.play'].endswith('&start=%d' % int(
        datetime.datetime(2026, 11, 7, 12, 0, tzinfo=UTC).timestamp()))
    assert tvrows.card_channel(match['tv.play']) is None  # resting on it doesn't switch the preview
    # Without catch-up anywhere, the row is empty.
    assert tvrows.rows(CHANNELS, found, [], NOW, ended=ended)[tvrows.CATCHUP_ROW] == []


def test_a_catch_up_card_plays_its_programme_from_kodis_guide(monkeypatch):
    from resources.lib.silokodi import plugin
    calls = []

    def jsonrpc(method, **params):
        calls.append((method, params))
        if method == 'PVR.GetBroadcasts':
            return {'broadcasts': [{'broadcastid': 70, 'starttime': '2026-11-07 10:00:00'},
                                   {'broadcastid': 71, 'starttime': '2026-11-07 12:00:00'}]}
        return {}
    monkeypatch.setattr(plugin.kodi, 'jsonrpc', jsonrpc)
    monkeypatch.setattr(plugin.kodi, 'log', lambda message: None)
    noticed = []
    monkeypatch.setattr(plugin.kodi, 'notify', lambda message, *args, **kwargs: noticed.append(message))
    start = int(datetime.datetime(2026, 11, 7, 12, 0, tzinfo=UTC).timestamp())
    plugin.play_catchup('5', str(start))
    assert calls[-1] == ('Player.Open', {'item': {'broadcastid': 71}})
    plugin.play_catchup('5', str(start + 60))  # gone from Kodi's guide
    assert calls[-1][0] == 'PVR.GetBroadcasts' and noticed


def test_a_broadcast_is_live_by_its_genre():
    from resources.lib.silokodi.channels import is_live
    assert is_live(['Sports / Live']) and is_live('Live') and is_live(['Live'])
    assert not is_live(['Other / Unknown']) and not is_live('') and not is_live(None) and not is_live(['Olive Oil'])


def test_the_banner_finds_a_channels_picture_and_live(monkeypatch):
    asked = []
    monkeypatch.setattr(tvrows, '_now_cache', {'at': 0, 'by_name': {}})
    monkeypatch.setattr(tvrows.kodi, 'jsonrpc', lambda method, **params: asked.append(method) or {'channels': [
        {'label': 'Sky Sports News', 'broadcastnow': {'thumbnail': 'https://i/ssn.jpg', 'genre': ['Live']}},
        {'label': 'CNN', 'broadcastnow': {'thumbnail': '', 'genre': ['Other / Unknown']}}]})
    assert tvrows.channel_now('Sky Sports News', now=1000) == ('https://i/ssn.jpg', True)
    assert tvrows.channel_now('CNN', now=1010) == ('', False)
    assert len(asked) == 1  # browsing on: kept, no lookup
    assert tvrows.channel_now('Nowhere', now=1020) == ('', False) and len(asked) == 2  # a channel not seen
    tvrows.channel_now('CNN', now=1000 + tvrows.NOW_KEEP + 30)
    assert len(asked) == 3  # a minute on: read again


def test_the_banner_steps_through_a_channels_programmes():
    from resources.lib.silokodi import banner
    shows = [{'start': 1000, 'end': 2000, 'title': 'A'}, {'start': 2000, 'end': 3000, 'title': 'B'},
             {'start': 3000, 'end': 4000, 'title': 'C'}]
    assert banner.programme(shows, 2500, -1) == (shows[0], -1)  # earlier: catch-up
    assert banner.programme(shows, 2500, 1) == (shows[2], 1)  # later
    assert banner.programme(shows, 2500, -5) == (shows[0], -1)  # no further than the guide has
    assert banner.programme(shows, 2500, 0) == (shows[1], 0)  # on now: the banner's own
    assert banner.programme([], 2500, 1) == (None, 0)
    assert banner.hint('past', True, False) == 'OK  Watch from the start'
    assert banner.hint('past', False, False) == 'Not on catch-up'
    assert banner.hint('future', False, True).startswith('Reminder set')
    assert banner.hint('now', False, False) == 'OK  Watch'
