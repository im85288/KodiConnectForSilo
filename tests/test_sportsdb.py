# -*- coding: utf-8 -*-
"""TheSportsDB for Skyline's TV page: teams' fanart, leagues' fanart, next fixtures."""
import calendar
import datetime

from resources.lib.silokodi import sportsdb, tvrows

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 11, 7, 15, 30, tzinfo=UTC)

NUFC = {'idTeam': '134777', 'strTeam': 'Newcastle United', 'strTeamAlternate': 'Newcastle United Football Club, NUFC',
        'strFanart1': 'http://f/1.jpg', 'strFanart2': 'http://f/2.jpg', 'strBadge': 'http://b.png',
        'strColour1': '#FFFFFF', 'strColour2': '#241F20'}
FULHAM = {'idTeam': '133600', 'strTeam': 'Fulham', 'strFanart1': 'http://f/fulham.jpg', 'strColour1': '#FFFFFF',
          'strColour2': '#CC0000'}
NEXT = {'strEvent': 'Newcastle United vs Chelsea', 'strHomeTeam': 'Newcastle United', 'strAwayTeam': 'Chelsea',
        'strTimestamp': '2026-11-21T17:30:00', 'strThumb': 'http://t/next.jpg', 'strLeague': 'English Premier League',
        'strVenue': "St James' Park"}


class Fake(object):
    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def __call__(self, endpoint, **params):
        self.calls.append((endpoint, params))
        return self.answers.get((endpoint, tuple(sorted(params.items()))))


def fake():
    return Fake({('searchteams.php', (('t', 'Newcastle United'),)): {'teams': [NUFC]},
                 ('searchteams.php', (('t', 'NUFC'),)): {'teams': [NUFC]},
                 ('searchteams.php', (('t', 'Spurs'),)): {'teams': [{'idTeam': '9', 'strTeam': 'Austin Spurs'}]},
                 ('eventsnext.php', (('id', '134777'),)): {'events': [NEXT]}})


def test_only_the_team_named_never_a_guess(tmp_path):
    db = sportsdb.SportsDB(str(tmp_path / 'c.json'), NOW.timestamp(), fake())
    teams = db.teams(['Newcastle United', 'NUFC', 'Spurs'])
    assert [t['id'] for t in teams] == ['134777']  # once, and not Austin Spurs
    assert teams[0]['fanart'] == ['http://f/1.jpg', 'http://f/2.jpg']


def test_answers_are_kept_and_a_refusal_pauses(tmp_path):
    path = str(tmp_path / 'c.json')
    get = fake()
    db = sportsdb.SportsDB(path, NOW.timestamp(), get)
    db.teams(['Newcastle United'])
    db.keep()
    again = sportsdb.SportsDB(path, NOW.timestamp() + 3600, get)
    again.teams(['Newcastle United'])
    assert len(get.calls) == 1
    refused = Fake({})
    db = sportsdb.SportsDB(str(tmp_path / 'd.json'), NOW.timestamp(), refused)
    db.teams(['Newcastle United', 'Fulham'])
    assert len(refused.calls) == 1  # paused after the first refusal


def test_next_fixture(tmp_path):
    db = sportsdb.SportsDB(str(tmp_path / 'c.json'), NOW.timestamp(), fake())
    team = db.teams(['Newcastle United'])[0]
    fixture = db.next_fixtures(team)[0]
    assert fixture['title'] == 'Newcastle United v Chelsea'
    assert fixture['start'] == calendar.timegm((2026, 11, 21, 17, 30, 0))


def test_a_match_gets_the_home_teams_fanart():
    known = [sportsdb.team_record(NUFC), sportsdb.team_record(FULHAM)]
    assert tvrows.team_in('Newcastle United @ Fulham  ᴸᶦᵛᵉ', known)['id'] == '133600'
    assert tvrows.team_in('Premier League : Newcastle United v Chelsea', known)['id'] == '134777'
    assert tvrows.team_in('Perth Glory v Newcastle Jets', known) is None
    card = tvrows.channel_card({'channelid': 2, 'label': 'Newcastle United',
                                'broadcastnow': {'title': 'Newcastle United @ Fulham'}}, NOW, '', known)
    assert card['art.fanart'] == 'http://f/fulham.jpg' and 'tint' not in card


def test_a_fixture_the_guide_doesnt_list_yet_is_a_card():
    known = [sportsdb.team_record(NUFC)]
    fixture = sportsdb.fixture(NEXT)
    rows = tvrows.rows([], [], ['Newcastle United'], NOW, known=known, fixtures=[(known[0], fixture)])
    card = rows['teams'][0]
    assert card['card.title'] == 'Newcastle United v Chelsea'
    assert 'channel not known yet' in card['card.sub']
    assert 'mode=tv_remind' in card['tv.play'] and '&ids=&' in card['tv.play']
    assert card['art.landscape'] == 'http://t/next.jpg' and card['tv.logo'] == 'http://b.png'


def test_a_fixture_the_guide_lists_is_its_card_only():
    known = [sportsdb.team_record(NUFC)]
    fixture = dict(sportsdb.fixture(NEXT), start=calendar.timegm((2026, 11, 12, 17, 30, 0)))
    from tests.test_tvrows import CHANNELS, entries
    rows = tvrows.rows(CHANNELS, entries(), ['Newcastle United'], NOW, known=known,
                       fixtures=[(known[0], fixture)])
    chelsea = [c for c in rows['teams'] if 'Chelsea' in c['card.title']]
    assert len(chelsea) == 1 and 'channel not known' not in chelsea[0]['card.sub']
    assert chelsea[0]['art.landscape'] == 'http://t/next.jpg'


def test_a_reminder_gets_its_channels_once_the_guide_lists_it(tmp_path):
    path = str(tmp_path / 'r.json')
    start = calendar.timegm((2026, 11, 12, 17, 30, 0))
    tvrows.toggle_reminder(str(start), [], 'Newcastle United v Chelsea', path)
    card = {'tv.play': '%s?mode=tv_remind&start=%d&ids=4,9&title=x' % (tvrows.PLUGIN, start - 900)}
    tvrows.fill_reminders({'teams': [card]}, path)
    assert tvrows.load_reminders(path)[str(start)]['ids'] == ['4', '9']
    # and the guide card's toggle removes it (its start is the channel's)
    assert tvrows.toggle_reminder(str(start - 900), ['4'], 'x', path) is False
    assert tvrows.load_reminders(path) == {}


def test_a_played_next_fixture_is_asked_again_hourly(tmp_path):
    path = str(tmp_path / 'c.json')
    played = dict(NEXT, strTimestamp='2026-11-07T10:00:00')
    get = Fake({('searchteams.php', (('t', 'Newcastle United'),)): {'teams': [NUFC]},
                ('eventsnext.php', (('id', '134777'),)): {'events': [played]}})
    db = sportsdb.SportsDB(path, NOW.timestamp(), get)
    team = db.teams(['Newcastle United'])[0]
    assert db.next_fixtures(team) == []
    db.keep()
    later = sportsdb.SportsDB(path, NOW.timestamp() + 3700, get)
    later.next_fixtures(team)
    assert [c[0] for c in get.calls].count('eventsnext.php') == 2


EPL = {'idLeague': '4328', 'strLeague': 'English Premier League', 'strSport': 'Soccer',
       'strLeagueAlternate': 'Premier League, EPL, England', 'strFanart1': 'http://l/epl.jpg'}


def test_a_league_by_the_names_a_title_uses():
    league = sportsdb.league_record(EPL)
    assert 'England' not in league['names'] and 'EPL' in league['names']
    assert tvrows.league_in('Premier League : Nottingham Forest v Manchester City', [league]) is league
    assert tvrows.league_in('Test Cricket : England v India', [league]) is None


def test_backdrop_team_then_picture_then_league():
    known = [sportsdb.team_record(FULHAM)]
    leagues = [sportsdb.league_record(EPL)]
    team = tvrows.backdrop({'art.fanart': 'pic'}, 'Premier League : Fulham v Brentford', known, leagues)
    assert team['art.fanart'] == 'http://f/fulham.jpg'
    picture = tvrows.backdrop({'art.fanart': 'pic'}, 'Premier League : Spurs v Wolves', known, leagues)
    assert picture['art.fanart'] == 'pic'
    league = tvrows.backdrop({'art.fanart': ''}, 'Premier League : Spurs v Wolves', known, leagues)
    assert league['art.fanart'] == 'http://l/epl.jpg'


def test_leagues_are_asked_a_few_countries_at_a_time(tmp_path):
    get = Fake({('search_all_leagues.php', (('c', 'England'),)): {'countries': [EPL]}})
    db = sportsdb.SportsDB(str(tmp_path / 'c.json'), NOW.timestamp(), lambda e, **p: get(e, **p) or {'countries': []})
    assert [l['id'] for l in db.leagues(('England', 'Spain', 'Italy'), most=2)] == ['4328']
    assert len(get.calls) == 2
    db.leagues(('England', 'Spain', 'Italy'), most=2)
    assert len(get.calls) == 3  # Italy, the one left
