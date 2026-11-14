# -*- coding: utf-8 -*-
"""TheSportsDB (thesportsdb.com) for Skyline's TV page: the viewer's teams'
fanart and next fixture, and leagues' fanart.

Its free API key allows few calls (a quick burst of 14 was refused with HTTP
429), so it's asked only about the teams in the add-on's setting, and what it
says is kept in the profile: a team for TEAM_TTL (one not found for MISS_TTL),
its next fixture for NEXT_TTL. A refused or failed call pauses every lookup
for PAUSE.
"""
import json
import re

from . import fileio

API = 'https://www.thesportsdb.com/api/v1/json/123/'
CACHE = 'sportsdb.json'
TEAM_TTL = 7 * 86400
MISS_TTL = 86400
NEXT_TTL = 6 * 3600
STALE_TTL = 3600  # a "next" fixture that's been played: asked again sooner
PAUSE = 600
MATCH_LENGTH = 2 * 3600  # a fixture is still worth showing this long after kick-off
LEAGUE_TTL = 30 * 86400
LEAGUE_COUNTRIES = ('England', 'Spain', 'Italy', 'Germany', 'France', 'USA')


def fetch(endpoint, **params):
    """TheSportsDB's answer as a dict, or None if it failed or refused."""
    import requests
    try:
        response = requests.get(API + endpoint, params=params, timeout=10,
                                headers={'User-Agent': 'KodiConnectForSilo'})
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        return None


def load(path):
    try:
        with open(path, encoding='utf-8') as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(path, data):
    fileio.write_json(path, data)


def team_record(raw):
    """What the TV page uses of a team: its names (any of which a guide may
    use), fanart and badge."""
    names = [raw.get('strTeam') or ''] + (raw.get('strTeamAlternate') or '').split(',') + [raw.get('strTeamShort') or '']
    return {'id': str(raw.get('idTeam') or ''),
            'names': [n.strip() for n in names if n and n.strip()],
            'fanart': [raw[key] for key in ('strFanart1', 'strFanart2', 'strFanart3', 'strFanart4') if raw.get(key)],
            'badge': raw.get('strBadge') or ''}


def chosen(name, found):
    """The team TheSportsDB found that is the one named: by its name or one of
    its other names, never a guess ("Spurs" finds Austin Spurs, a basketball
    team)."""
    wanted = name.strip().lower()
    for raw in found or []:
        if wanted in (n.lower() for n in team_record(raw)['names']):
            return team_record(raw)
    return None


def league_record(raw):
    """A league as the TV page uses it: the names a title may call it by and
    its fanart. A one-word name only if it's an acronym (EPL, NFL): "England",
    one of the Premier League's, would match England's cricket."""
    names = [raw.get('strLeague') or ''] + (raw.get('strLeagueAlternate') or '').split(',')
    names = [n.strip() for n in names if n and n.strip()]
    return {'id': str(raw.get('idLeague') or ''), 'sport': raw.get('strSport') or '',
            'names': [n for n in names if ' ' in n or (n.isupper() and len(n) >= 3)],
            'fanart': [raw[key] for key in ('strFanart1', 'strFanart2', 'strFanart3', 'strFanart4') if raw.get(key)]}


def fixture(raw):
    """A fixture as the TV page uses it: 'Fulham v Newcastle United', kick-off
    in seconds (UTC), its picture and competition."""
    stamp = raw.get('strTimestamp') or ''
    match = re.match(r'(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d)', stamp)
    if not match:
        return None
    import calendar
    start = calendar.timegm(tuple(int(part) for part in match.groups()) + (0, 0, 0, 0))
    title = re.sub(r'\s+vs\.?\s+', ' v ', raw.get('strEvent') or '')
    return {'title': title, 'home': raw.get('strHomeTeam') or '', 'away': raw.get('strAwayTeam') or '',
            'start': start, 'thumb': raw.get('strThumb') or raw.get('strBanner') or '',
            'league': raw.get('strLeague') or '', 'venue': raw.get('strVenue') or ''}


class SportsDB(object):
    """Lookups that keep their answers (in the profile, at path)."""

    def __init__(self, path, now, get=fetch):
        self.path, self.now, self.get = path, now, get
        self.data = load(path)
        self.changed = False

    def paused(self):
        return self.now < self.data.get('paused_until', 0)

    def ask(self, endpoint, **params):
        if self.paused():
            return None
        answer = self.get(endpoint, **params)
        if answer is None:
            self.data['paused_until'] = self.now + PAUSE
            self.changed = True
        return answer

    def team(self, name):
        """The team called name, or None (not found, or not asked yet)."""
        teams = self.data.setdefault('teams', {})
        kept = teams.get(name.lower())
        if kept and self.now - kept.get('at', 0) < (TEAM_TTL if kept.get('team') else MISS_TTL):
            return kept.get('team')
        answer = self.ask('searchteams.php', t=name)
        if answer is None:
            return kept.get('team') if kept else None
        teams[name.lower()] = {'at': self.now, 'team': chosen(name, answer.get('teams'))}
        self.changed = True
        return teams[name.lower()]['team']

    def teams(self, names):
        """The named teams TheSportsDB knows, once each (a team's names all
        lead to it: "Newcastle United", "NUFC")."""
        found, ids = [], set()
        for name in names:
            team = self.team(name)
            if team and team['id'] not in ids:
                ids.add(team['id'])
                found.append(team)
        return found

    def next_fixtures(self, team):
        """A team's next fixtures (the free key gives one), not over yet."""
        upcoming = self.data.setdefault('next', {})
        kept = upcoming.get(team['id'])
        # TheSportsDB's "next" stays the last match for a while after it's
        # played: asked again hourly until it moves on.
        over = kept and not any(f['start'] + MATCH_LENGTH > self.now for f in kept.get('events', []))
        if not kept or self.now - kept.get('at', 0) >= (STALE_TTL if over else NEXT_TTL):
            answer = self.ask('eventsnext.php', id=team['id'])
            if answer is not None:
                kept = {'at': self.now, 'events': [f for f in (fixture(e) for e in answer.get('events') or []) if f]}
                upcoming[team['id']] = kept
                self.changed = True
        return [f for f in (kept or {}).get('events', []) if f['start'] + MATCH_LENGTH > self.now]

    def leagues(self, countries=LEAGUE_COUNTRIES, most=2):
        """The leagues of the countries (the free key gives five a country:
        football's top ones, the NFL, NBA...), each country asked once a
        LEAGUE_TTL, at most `most` of them a time."""
        kept = self.data.setdefault('leagues', {})
        asked = 0
        found = []
        for country in countries:
            entry = kept.get(country)
            if (not entry or self.now - entry.get('at', 0) >= LEAGUE_TTL) and asked < most:
                asked += 1
                answer = self.ask('search_all_leagues.php', c=country)
                if answer is not None:
                    raw = answer.get('countries') or answer.get('leagues') or []
                    entry = {'at': self.now, 'leagues': [league_record(r) for r in raw if r.get('strFanart1')]}
                    kept[country] = entry
                    self.changed = True
            found += (entry or {}).get('leagues', [])
        return found

    def keep(self):
        if self.changed:
            try:
                save(self.path, self.data)
            except OSError:
                pass

