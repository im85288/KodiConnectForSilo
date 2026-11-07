# -*- coding: utf-8 -*-
"""Skyline's YouTube page: the YouTube add-on's lists as cards."""
import datetime

from resources.lib.silokodi import ytrows

TODAY = datetime.date(2026, 11, 7)
ITEM = {'file': 'plugin://plugin.video.youtube/play/?video_id=abcdefghijk', 'title': 'Reaction to Fulham 1 Vs Newcastle 1',
        'label': 'x', 'studio': ['LOADED MAG NUFC'], 'premiered': '2026-11-07', 'runtime': 754,
        'plot': 'A reaction.', 'art': {'thumb': 'https://i.ytimg.com/vi/abcdefghijk/hq720.jpg'},
        'resume': {'position': 377, 'total': 754}}


def test_a_video_is_a_card():
    card = ytrows.card(ITEM, TODAY)
    assert card['type'] == 'youtube' and card['label'] == card['card.title'] == ITEM['title']
    assert card['card.sub'] == 'LOADED MAG NUFC'
    assert card['hero.facts'] == 'LOADED MAG NUFC  ·  Today  ·  12:34'
    assert card['art.landscape'] == 'https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg'
    assert card['art.fanart'].endswith('hq720.jpg')
    assert card['yt.play'] == ITEM['file'] and card['percent'] == '50'


def test_not_a_video_is_no_card():
    assert ytrows.card({'file': 'plugin://plugin.video.youtube/channel/x/', 'title': 'A channel'}, TODAY) is None


def test_ages_and_lengths_as_youtube_writes_them():
    assert [ytrows.ago(d, TODAY) for d in ('2026-11-06', '2026-11-04', '2026-10-24', '2026-08-01', '2024-11-01', '')] \
        == ['Yesterday', '3 days ago', '2 weeks ago', '3 months ago', '2 years ago', '']
    assert (ytrows.length(59), ytrows.length(3723), ytrows.length(None)) == ('0:59', '1:02:03', '')


def test_the_channel_is_the_studio_or_the_artist():
    assert ytrows.channel_of({'studio': ['Untitled'], 'artist': ['Squirrel']}) == 'Squirrel'
    assert ytrows.channel_of({}) == ''


def test_rows_one_list_at_a_time():
    asked = []

    def fetch(path):
        asked.append(path)
        return [ITEM] if 'recommendations' in path else []
    rows = ytrows.gather(TODAY, fetch)
    assert len(asked) == len(ytrows.ROWS) + 1  # and the channels
    assert all('hide_folders=true' in p for p in asked if 'subscriptions/list' not in p)
    assert len(rows['recommended']) == 1 and rows['history'] == [] and rows['channels'] == []


def test_a_key_pressed_stops_after_the_list_its_on():
    asked = []

    def fetch(path):
        asked.append(path)
        return [ITEM]
    idle = iter([True, False])  # a key pressed during the second list
    rows = ytrows.gather(TODAY, fetch, idle=lambda: next(idle))
    assert list(rows) == ['recommended', 'subscriptions', 'recent'] and len(asked) == 2


def test_the_description_without_the_add_ons_details():
    plot = ('[B]LOADED MAG NUFC[/B][CR][CR][COLOR lime][B]154 Views[/B][/COLOR] | [COLOR cyan][B]18 Likes[/B][/COLOR][CR]'
            '[CR]Our reaction to the draw.[CR]Subscribe![CR][CR]--------[CR]https://youtu.be/abcdefghijk')
    assert ytrows.description(plot, 'LOADED MAG NUFC') == ('154 views', 'Our reaction to the draw.\nSubscribe!', '')
    assert ytrows.description('Just a description.', 'X') == ('', 'Just a description.', '')
    card = ytrows.card(dict(ITEM, plot=plot), TODAY)
    assert card['hero.facts'] == 'LOADED MAG NUFC  ·  154 views  ·  Today  ·  12:34'


def test_no_emoji_kodi_would_draw_as_boxes():
    assert ytrows.plain('\U0001F534 Reaction to Fulham 1 Vs Newcastle United 1 \U0001F534') == \
        'Reaction to Fulham 1 Vs Newcastle United 1'
    assert ytrows.plain('Café ✅ “quotes” – dash\n❤️ Line two') == 'Café “quotes” – dash\nLine two'
    card = ytrows.card(dict(ITEM, title='⚽ Goals \U0001F3C6', studio=['Club TV ✅']), TODAY)
    assert (card['card.title'], card['card.sub']) == ('Goals', 'Club TV')


def test_the_subscriptions_screen_from_the_same_fetch():
    channel = {'file': 'plugin://plugin.video.youtube/channel/UC123/', 'label': 'HaytersTV \u2705',
               'art': {'thumb': 'http://c/1.jpg'}}

    def fetch(path):
        if 'subscriptions/list' in path:
            return [channel]
        return [ITEM] * 40 if 'my_subscriptions' in path else []
    rows = ytrows.gather(TODAY, fetch)
    assert len(rows['subscriptions']) == ytrows.CARDS and len(rows['recent']) == ytrows.RECENT
    props = ytrows.screen_properties(rows)
    assert props['silo.youtube.channels.1.label'] == 'HaytersTV'
    assert props['silo.youtube.channels.1.path'].endswith('/channel/UC123/')  # not a channel id: as it is
    assert props['silo.youtube.channels.2.label'] == '' and props['silo.youtube.channels.count'] == '1'
    assert props['silo.youtube.recent.1.length'] == '12:34' and props['silo.youtube.recent.1.when'] == 'Today'
    assert props['silo.youtube.recent.30.play'] == ITEM['file'] and props['silo.youtube.recent.count'] == '30'
    assert ytrows.screen_properties({'recommended': []}) == {}  # neither fetched: theirs kept


def test_every_page_of_the_channels():
    pages = {'plugin://plugin.video.youtube/subscriptions/list/': [
                {'file': 'plugin://plugin.video.youtube/channel/UCa/', 'label': 'Allie Sherlock'},
                {'file': 'plugin://plugin.video.youtube/subscriptions/list/?page=2&page_token=CDIQAA', 'label': 'Next page (2)'}],
             'plugin://plugin.video.youtube/subscriptions/list/?page=2&page_token=CDIQAA': [
                {'file': 'plugin://plugin.video.youtube/channel/UCb/', 'label': 'Brian Menard'},
                {'file': 'plugin://plugin.video.youtube/channel/UCa/', 'label': 'Allie Sherlock'}]}
    rows = ytrows.gather(TODAY, lambda path: pages.get(path, []))
    assert [c['label'] for c in rows['channels']] == ['Allie Sherlock', 'Brian Menard']


PAGE = ('<html><meta property="og:title" content="Brian Menard">'
        '<meta property="og:image" content="https://yt3.ggpht.com/brian=s900">'
        '<meta itemprop="identifier" content="UC3t5CYZMhhOl0_8ATxCBrkg"></html>')


def test_extra_channels_from_their_pages_kept(tmp_path):
    asked = []

    def get(url):
        asked.append(url)
        return PAGE
    path = str(tmp_path / 'extra.json')
    setting = '@BrianMenard, nonsense words, @BrianMenard'
    assert ytrows.extra_handles(setting) == ['@BrianMenard', '@BrianMenard']
    found = ytrows.extra_channels('@BrianMenard', path, 1000, get)
    assert found == [{'id': 'UC3t5CYZMhhOl0_8ATxCBrkg', 'label': 'Brian Menard', 'thumb': 'https://yt3.ggpht.com/brian=s900'}]
    assert asked == ['https://www.youtube.com/@BrianMenard']
    ytrows.extra_channels('@BrianMenard', path, 2000, get)
    assert len(asked) == 1  # kept
    assert ytrows.extra_channels('@Gone', path, 2000, lambda url: '<html></html>') == []


def test_extra_channels_join_the_subscriptions():
    extra = {'id': 'UC3t5CYZMhhOl0_8ATxCBrkg', 'label': 'Brian Menard', 'thumb': 'b.jpg'}
    newer = dict(ITEM, file='plugin://plugin.video.youtube/play/?video_id=bbbbbbbbbbb', title='Ocarina',
                 premiered='2026-11-08', studio=['Brian Menard'])
    older = dict(ITEM, premiered='2026-11-01')

    def fetch(path):
        if 'my_subscriptions' in path:
            return [older]
        if '/playlist/UU3t5CYZMhhOl0_8ATxCBrkg/' in path:
            return [newer]
        if 'subscriptions/list' in path:
            return [{'file': 'plugin://plugin.video.youtube/channel/UCz/', 'label': 'Zed'}]
        return []
    rows = ytrows.gather(TODAY, fetch, extras=[extra])
    assert [c['card.title'] for c in rows['subscriptions']] == ['Ocarina', ITEM['title']]
    assert rows['recent'][0]['card.title'] == 'Ocarina'
    assert [c['label'] for c in rows['channels']] == ['Brian Menard', 'Zed']
    assert rows['channels'][0]['path'] == 'plugin://plugin.video.youtube/playlist/UU3t5CYZMhhOl0_8ATxCBrkg/'


def test_a_streams_start_or_that_its_live():
    upcoming = '[B]Brian Menard[/B][CR][I]Upcoming Live @ 21:00[/I][CR][CR]Join me![CR]--------[CR]https://youtu.be/x'
    card = ytrows.card(dict(ITEM, plot=upcoming, studio=['Brian Menard'], runtime=0), TODAY)
    assert card['yt.when'] == 'Starts 21:00' and card['plot'] == 'Join me!'
    assert card['hero.facts'] == 'Brian Menard  ·  Starts 21:00'
    live = '[B]X[/B][CR]Live broadcast @ 19:32[CR]Live now'
    assert ytrows.card(dict(ITEM, plot=live, studio=['X'], runtime=0), TODAY)['yt.when'] == 'LIVE'
    ended = ytrows.card(dict(ITEM, plot=live, studio=['X']), TODAY)  # it has a length: over
    assert ended['yt.when'] == 'Today' and ended['plot'] == 'Live now'
    later = '[B]X[/B][CR]Premieres @ 08/11/2026, 18:00[CR]Soon'
    assert ytrows.card(dict(ITEM, plot=later, studio=['X'], runtime=0), TODAY)['yt.when'] == 'Premieres 08/11/2026, 18:00'


def test_a_stream_yet_to_start_has_likes_but_no_views():
    plot = '[B]Brian Menard[/B][CR][B]5 Likes[/B][CR][I]Upcoming Live @ 21:00[/I][CR]HumanitZ just dropped a HUGE update.'
    assert ytrows.description(plot, 'Brian Menard', False) == ('', 'HumanitZ just dropped a HUGE update.', 'Starts 21:00')


def test_a_stream_yet_to_start_brings_the_next_fetch_forward():
    import time
    starts = ytrows.starts_at('Starts 21:00', TODAY)
    assert starts == time.mktime((2026, 11, 7, 21, 0, 0, 0, 0, -1))
    assert ytrows.starts_at('Premieres 08/11/2026, 18:00', TODAY) == time.mktime((2026, 11, 8, 18, 0, 0, 0, 0, -1))
    assert ytrows.starts_at('LIVE', TODAY) is None and ytrows.starts_at('Today', TODAY) is None
    rows = {'subscriptions': [{'yt.starts': starts}, {'yt.starts': None}], 'channels': [{'label': 'x'}]}
    assert ytrows.next_start(rows, starts - 600) == starts
    assert ytrows.next_start(rows, starts + 600) == starts  # late: still watched
    assert ytrows.next_start(rows, starts + ytrows.WATCH + 1) is None
    assert not ytrows.stream_due(starts, starts - 600, starts + 60)  # not yet
    assert ytrows.stream_due(starts, starts - 600, starts + ytrows.LIVE_AFTER)
    assert not ytrows.stream_due(starts, starts + 200, starts + 300)  # fetched lately
    assert ytrows.stream_due(starts, starts + 200, starts + 200 + ytrows.RECHECK)
    assert not ytrows.stream_due(None, 0, starts)


def test_a_streams_recheck_asks_for_fresh_details():
    asked = []
    extra = {'id': 'UC3t5CYZMhhOl0_8ATxCBrkg', 'label': 'Brian Menard', 'thumb': ''}
    ytrows.gather(TODAY, lambda path: asked.append(path) or [], extras=[extra], refresh=True)
    fresh = [p for p in asked if p.endswith('&refresh=1')]
    assert len(fresh) == 2 and any('my_subscriptions' in p for p in fresh) and any('/playlist/UU3t5' in p for p in fresh)
