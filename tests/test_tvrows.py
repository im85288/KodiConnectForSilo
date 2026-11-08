# -*- coding: utf-8 -*-
"""Skyline's TV page: My teams, On now and Live sport now."""
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
    # Newcastle Jets' game is in Live sport now, not My teams.
    assert 'Perth Glory v Newcastle Jets' in [c['card.title'] for c in rows[tvrows.SPORT_ROW]]


def test_on_now_is_recent_channels_with_whats_on():
    rows = tvrows.rows(CHANNELS, entries(), [], NOW)
    assert [c['card.title'] for c in rows[tvrows.ON_NOW_ROW]] == ['TNT Sports 1', 'Sky Sports Premier League']
    assert rows[tvrows.ON_NOW_ROW][0]['percent'] == '50'
    assert rows[tvrows.ON_NOW_ROW][0]['tv.play'].endswith('mode=play_channel&id=5')


def test_live_sport_now_leaves_out_my_teams_matches():
    rows = tvrows.rows(CHANNELS, entries(), ['Newcastle United', 'Newcastle Utd'], NOW)
    sport = [c['card.title'] for c in rows[tvrows.SPORT_ROW]]
    assert 'Arsenal v Hull' in sport
    assert 'Fulham v Newcastle Utd' not in sport


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
    assert [layout['silo.tv.%d.title' % n] for n in (1, 2, 3)] == ['On now', 'Live sport now', 'My teams']
    assert layout['silo.tv.4.title'] == ''


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
    tnt = rows[tvrows.ON_NOW_ROW][0]
    assert tnt['art.landscape'] == 'http://i/a.png'  # what TNT Sports 1 shows now
    assert tnt['tv.logo'] == 'tnt.png'
    sky = rows[tvrows.ON_NOW_ROW][1]
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
            return {'channels': CHANNELS}
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
    monkeypatch.setattr(tvrows.kodi, 'jsonrpc', lambda method, **params: {'channels': CHANNELS}
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


def test_live_sport_now_keeps_to_the_chosen_groups():
    groups = tvrows.playlist_groups(PLAYLIST)
    assert groups['TNT Sports 1'] == 'UK | TNT Sports'
    every = tvrows.rows(CHANNELS, entries(), [], NOW)['sport']
    kept = tvrows.rows(CHANNELS, entries(), [], NOW, sport_groups=['UK | TNT Sports'], groups=groups)['sport']
    assert len(every) > len(kept) == 1 and 'Arsenal' in kept[0]['card.title']
    # My teams looks in every group
    teams = tvrows.rows(CHANNELS, entries(), ['Newcastle United', 'Newcastle Utd'], NOW,
                        sport_groups=['UK | TNT Sports'], groups=groups)['teams']
    assert teams


def test_the_chosen_groups_are_kept(tmp_path):
    path = str(tmp_path / 'g.json')
    assert tvrows.load_sport_groups(path) == []
    tvrows.save_sport_groups(['UK | Sky Sports', 'UK | TNT Sports'], path)
    assert tvrows.load_sport_groups(path) == ['UK | Sky Sports', 'UK | TNT Sports']
