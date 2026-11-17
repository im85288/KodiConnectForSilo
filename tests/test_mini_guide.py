import datetime

from resources.lib.silokodi import plugin

day = lambda h: datetime.datetime(2026, 10, 28, int(h), int(h % 1 * 60)).timestamp()


class Home(object):
    def __init__(self):
        self.props = {}

    def setProperty(self, key, value):
        self.props[key] = value

    def getProperty(self, key):
        return self.props.get(key, '')

    def clearProperty(self, key):
        self.props.pop(key, None)


class Item(object):
    def __init__(self, label, offscreen=False):
        self.label, self.props, self.art = label, {}, {}

    def setProperties(self, props):
        self.props.update(props)

    def setArt(self, art):
        self.art.update(art)


def _grid(monkeypatch, tmp_path):
    group = [{'channelid': 7, 'channelnumber': 18, 'label': 'News', 'icon': 'n.png', 'hasarchive': True},
             {'channelid': 8, 'channelnumber': 19, 'label': 'Hidden', 'hidden': True},
             {'channelid': 9, 'channelnumber': 20, 'label': 'Plus', 'icon': 'p.png'}]
    guide = {7: [('Desk', 16, 19), ('Football', 19, 22), ('Late', 22, 23)],
             9: [('Cricket', 19, 21), ('Golf', 21, 23), ('Darts', 23, 23.5)]}
    fetched = []

    def broadcasts(c):
        fetched.append(c['channelid'])
        return [{'broadcastid': c['channelid'] * 10 + i, 'title': t, 'start': day(s), 'end': day(e)}
                for i, (t, s, e) in enumerate(guide[c['channelid']])]
    monkeypatch.setattr(plugin, 'group_channels', lambda label, fields=None: group if label == 'UK | Sky Sports' else [])
    monkeypatch.setattr(plugin.channels, 'channel_broadcasts', broadcasts)
    monkeypatch.setattr(plugin.kodi, 'profile_dir', lambda: str(tmp_path))
    monkeypatch.setattr(plugin.xbmc, 'getRegion', lambda what: '%H:%M:%S', raising=False)
    monkeypatch.setattr(plugin.xbmcgui, 'ListItem', Item)
    listed, published = [], {}
    monkeypatch.setattr(plugin.xbmcplugin, 'addDirectoryItem', lambda handle, url, item, isFolder: listed.append(item))
    monkeypatch.setattr(plugin.kodi, 'set_property', lambda key, value: published.__setitem__(key, value))
    return listed, published, fetched


def test_the_grid_lists_the_group_in_half_hours_from_now(monkeypatch, tmp_path):
    listed, published, fetched = _grid(monkeypatch, tmp_path)
    monkeypatch.setattr(plugin, 'playing_channel', lambda: 9)
    plugin.mini_grid(1, '20', 'UK | Sky Sports', now=day(20.5) + 300)
    assert [i.label for i in listed] == ['News', 'Plus']           # the hidden channel left out
    news, plus = (i.props for i in listed)
    assert [news.get('silo.c%d.title' % n) for n in range(4)] == ['Football', 'Football', 'Football', 'Late']
    assert news['silo.c0.when'] == 'now' and news['silo.c0.left'] == '85' and news['silo.c1.cont'] == '1'
    assert [plus.get('silo.c%d.title' % n) for n in range(4)] == ['Cricket', 'Golf', 'Golf', 'Golf']
    assert listed[1].art['icon'] == 'p.png'
    assert (news['silo.playing'], plus['silo.playing']) == ('', '1')   # marked by the add-on
    assert [published['mini_head%d' % n] for n in range(4)] == ['Now', '21:00', '21:30', '22:00']
    assert (published['mini_now'], published['mini_for']) == ('1', '20')   # opens on channel 20


def test_moved_back_the_grid_offers_catch_up_and_uses_the_saved_guide(monkeypatch, tmp_path):
    listed, published, fetched = _grid(monkeypatch, tmp_path)
    plugin.mini_grid(1, '20', 'UK | Sky Sports', now=day(20.5))
    del listed[:]
    plugin.mini_grid(1, '20', 'UK | Sky Sports', shift=-8, focus='18', now=day(20.5) + 60)
    news = listed[0].props
    assert (news['silo.c0.title'], news['silo.c0.when'], news['silo.c0.archive']) == ('Desk', 'past', '1')
    assert published['mini_head0'] == '16:30' and published['mini_now'] == '0'   # kept on channel 18
    assert fetched == [7, 9]                                       # the second asked Kodi nothing


def test_left_and_right_past_the_edges_move_the_grid(monkeypatch):
    home = Home()
    monkeypatch.setattr(plugin.kodi, 'HOME', home)
    cleared = []
    monkeypatch.setattr(plugin.kodi, 'clear_property', cleared.append)
    home.setProperty('silo.mini.placed', '1')
    plugin.mini_shift('-1', '19')
    assert (home.getProperty('silo.mini.shift'), home.getProperty('silo.mini.focus')) == ('-1', '19')
    assert home.getProperty('silo.mini.placed') == '' and cleared == ['mini_for']
    home.setProperty('silo.mini.shift', str(plugin.GRID_SHIFTS[1]))
    plugin.mini_shift('1', '19')
    assert home.getProperty('silo.mini.shift') == str(plugin.GRID_SHIFTS[1])   # no further
