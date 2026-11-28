import datetime
import time
from urllib.parse import parse_qs, urlsplit

from resources.lib.silokodi import banner, iplayer, tvrows

MOTD = {'programme_episodes': {'elements': [
    {'id': 'm0035abc', 'subtitle': 'Nottingham Forest v Chelsea Highlights', 'release_date': '27 Nov 2026',
     'images': {'standard': 'https://ichef.bbci.co.uk/images/ic/{recipe}/p0aaa.jpg'},
     'synopses': {'small': 'Cut straight to the action.'},
     'versions': [{'duration': {'text': '8 mins'}, 'availability': {'end': '2026-12-04T20:00:00Z'}}]},
    {'id': 'm0035day', 'subtitle': '22/11/2026', 'release_date': '22 Nov 2026',
     'images': {'standard': 'https://ichef.bbci.co.uk/images/ic/{recipe}/p0day.jpg'},
     'versions': [{'duration': {'text': '1 hr 20 mins'}}]},
    {'id': 'm00359vw', 'subtitle': 'Newcastle United v Arsenal Highlights', 'release_date': '21 Nov 2026',
     'images': {'standard': 'https://ichef.bbci.co.uk/images/ic/{recipe}/p0pp8qyf.jpg'},
     'versions': [{'duration': {'text': '8 mins'}}]},
    {'id': 'm0035jet', 'subtitle': 'Newcastle Jets v Sydney FC Highlights', 'release_date': '20 Nov 2026'}]}}


def test_match_of_the_day_highlights_newest_first(monkeypatch):
    monkeypatch.setattr(iplayer, 'get', lambda path, **query: MOTD)
    items = iplayer.highlights()
    assert [i['match'] for i in items] == ['Nottingham Forest v Chelsea', 'Newcastle United v Arsenal',
                                           'Newcastle Jets v Sydney FC']
    assert items[0]['picture'] == 'https://ichef.bbci.co.uk/images/ic/832x468/p0aaa.jpg'
    assert items[0]['day'] == datetime.date(2026, 11, 27) and items[0]['length'] == '8 mins'


def test_the_teams_matches_lead_the_highlights_not_another_teams(monkeypatch):
    monkeypatch.setattr(iplayer, 'get', lambda path, **query: MOTD)
    teams = ['Newcastle United', 'England']
    ordered = iplayer.team_first(iplayer.highlights(), teams, tvrows.mentions)
    assert [i['match'] for i in ordered] == ['Newcastle United v Arsenal', 'Nottingham Forest v Chelsea',
                                             'Newcastle Jets v Sydney FC']


def test_the_full_programmes_have_their_own_row(monkeypatch):
    monkeypatch.setattr(iplayer, 'get', lambda path, **query: MOTD)
    monkeypatch.setattr(iplayer, 'installed', lambda: True)
    monkeypatch.setattr(iplayer, 'continue_watching', lambda: [])
    rows = iplayer.rows(['Newcastle United'], tvrows.mentions)
    assert [c['card.title'] for c in rows['iplayer_league']][:2] == ['Newcastle United v Arsenal',
                                                                    'Nottingham Forest v Chelsea']
    assert [(c['card.title'], c['card.sub'], c['left']) for c in rows['iplayer_motd']] == [
        ('Match of the Day', 'Sunday 22 November', '1 hr 20 mins')]
    assert 'iplayer_team' not in rows


def test_a_highlight_card_plays_through_iplayer_www(monkeypatch):
    monkeypatch.setattr(iplayer, 'get', lambda path, **query: MOTD)
    card = iplayer.highlight_card(iplayer.highlights()[1], today=datetime.date(2026, 11, 22))
    assert card['card.title'] == 'Newcastle United v Arsenal'
    assert card['card.sub'] == 'Match of the Day  ·  Yesterday'
    assert card['left'] == '8 mins'
    play = parse_qs(urlsplit(card['tv.play']).query)
    assert play['mode'] == ['iplayer']
    www = urlsplit(play['path'][0])
    assert www.netloc == 'plugin.video.iplayerwww'
    query = parse_qs(www.query)
    assert query['url'] == ['https://www.bbc.co.uk/iplayer/episode/m00359vw'] and query['mode'] == ['202']


def test_continue_watching_from_iplayer_www(monkeypatch):
    listing = {'files': [
        {'label': 'Kin - [I]49 min left[/I]', 'file': 'plugin://plugin.video.iplayerwww/?mode=202&url=x',
         'art': {'thumb': 'https://ichef/kin.jpg'}, 'plot': 'Drama.'},
        {'label': 'The Traitors - [I]next episode[/I]', 'file': 'plugin://plugin.video.iplayerwww/?mode=202&url=y',
         'art': {'fanart': 'https://ichef/traitors.jpg'}},
        {'label': '', 'file': ''}]}
    monkeypatch.setattr(iplayer.kodi, 'jsonrpc', lambda method, **params: listing)
    items = iplayer.continue_watching()
    assert [(i['title'], i['left']) for i in items] == [('Kin', '49 min left'), ('The Traitors', 'next episode')]
    card = iplayer.continue_card(items[0])
    assert card['left'] == '49 min left' and card['art.landscape'] == 'https://ichef/kin.jpg'


def test_a_guide_programme_is_found_by_channel_and_start(monkeypatch):
    start = int(datetime.datetime(2026, 11, 27, 22, 30, tzinfo=datetime.timezone.utc).timestamp())
    broadcasts = {'broadcasts': {'elements': [
        {'scheduled_start': '2026-11-27T22:00:00.000Z', 'episode': {'id': 'p1', 'title': 'BBC News'}},
        {'scheduled_start': '2026-11-27T22:30:00.000Z',
         'episode': {'id': 'm0035nn', 'title': 'Newsnight', 'subtitle': '27/11/2026',
                     'images': {'standard': 'https://ichef/{recipe}/n.jpg'}}}]}}
    asked = []
    monkeypatch.setattr(iplayer, 'get', lambda path, **query: asked.append(path) or broadcasts)
    assert iplayer.find_episode('BBC News', start)[:2] == ('m0035nn', 'Newsnight - 27/11/2026')
    assert asked == ['channels/bbc_news24/broadcasts']
    assert iplayer.find_episode('BBC News', start + 3 * 3600) is None
    assert iplayer.find_episode('Sky News', start) is None


def test_the_guides_date_label():
    assert iplayer.guide_start('27/11/2026 22:40') == int(time.mktime((2026, 11, 27, 22, 40, 0, 0, 0, -1)))
    assert iplayer.guide_start('') is None


def test_the_banner_offers_iplayer_for_a_bbc_programme_without_catch_up():
    assert banner.hint('past', False, False, iplayer=True) == 'OK  Watch on iPlayer'
    assert banner.hint('past', True, False, iplayer=True) == 'OK  Watch from the start'
    assert banner.hint('past', False, False) == 'Not on catch-up'


def test_no_rows_without_iplayer_www(monkeypatch):
    monkeypatch.setattr(iplayer, 'installed', lambda: False)
    assert iplayer.rows(['Newcastle United'], tvrows.mentions) == {}


def test_a_continue_watching_card_knows_its_programme_for_remove(monkeypatch):
    asked = []

    def get(path, **query):
        asked.append(path)
        return {'episodes': [{'id': 'm0035mc', 'tleo_id': 'b006wnfw'}]}
    monkeypatch.setattr(iplayer, 'get', get)
    path = iplayer.episode_path('m0035mc', 'MasterChef')
    assert iplayer.programme_of(path) == 'b006wnfw' and asked == ['episodes/m0035mc']
    assert iplayer.programme_of('plugin://plugin.video.iplayerwww/?mode=202&url=x') == ''
    card = iplayer.continue_card({'title': 'MasterChef', 'left': '', 'path': path, 'plot': '', 'picture': '',
                                  'programme': 'b006wnfw'})
    assert card['tv.iplayer'] == 'b006wnfw'


def test_most_popular_on_iplayer(monkeypatch):
    answer = {'group_episodes': {'elements': [
        {'id': 'm0035sh', 'title': 'Shetland', 'subtitle': 'Series 11: Episode 1',
         'images': {'standard': 'https://ichef/{recipe}/s.jpg'}, 'versions': [{'duration': {'text': '59 mins'}}]},
        {'id': 'm0035ee', 'title': 'EastEnders', 'subtitle': '26/11/2026'},
        {'title': 'No id'}]}}
    monkeypatch.setattr(iplayer, 'get', lambda path, **query: answer)
    cards = [iplayer.popular_card(i) for i in iplayer.popular()]
    assert [(c['card.title'], c['card.sub'], c['left']) for c in cards] == [
        ('Shetland', 'Series 11: Episode 1', '59 mins'), ('EastEnders', '26/11/2026', '')]
    assert 'm0035sh' in cards[0]['tv.play']
