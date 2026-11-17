import datetime

from resources.lib.silokodi import plugin

day = lambda h: datetime.datetime(2026, 10, 28, int(h), int(h % 1 * 60)).timestamp()


class Item(object):
    def __init__(self, label, offscreen=False):
        self.label, self.props, self.art = label, {}, {}

    def setProperties(self, props):
        self.props.update(props)

    def setArt(self, art):
        self.art.update(art)


def test_the_grid_lists_the_group_with_each_channels_programmes(monkeypatch):
    group = [{'channelid': 7, 'channelnumber': 18, 'label': 'News', 'icon': 'n.png', 'hasarchive': True},
             {'channelid': 8, 'channelnumber': 19, 'label': 'Hidden', 'hidden': True},
             {'channelid': 9, 'channelnumber': 20, 'label': 'Plus', 'icon': 'p.png'}]
    guide = {7: [('Desk', 16, 19), ('Football', 19, 22), ('Late', 22, 23)],
             9: [('Cricket', 19, 21), ('Golf', 21, 23), ('Darts', 23, 23.5)]}
    monkeypatch.setattr(plugin, 'group_channels', lambda label, fields=None: group if label == 'UK | Sky Sports' else [])
    monkeypatch.setattr(plugin.channels, 'channel_schedule', lambda c, now: plugin.channels.schedule_rows(
        [{'broadcastid': c['channelid'] * 10 + i, 'title': t, 'start': day(s), 'end': day(e)}
         for i, (t, s, e) in enumerate(guide[c['channelid']])], now, bool(c.get('hasarchive'))))
    monkeypatch.setattr(plugin.xbmc, 'getRegion', lambda what: '%H:%M:%S', raising=False)
    monkeypatch.setattr(plugin.xbmcgui, 'ListItem', Item)
    listed, published = [], {}
    monkeypatch.setattr(plugin.xbmcplugin, 'addDirectoryItem', lambda handle, url, item, isFolder: listed.append(item))
    monkeypatch.setattr(plugin.kodi, 'set_property', lambda key, value: published.__setitem__(key, value))
    plugin.mini_grid(1, '20', 'UK | Sky Sports', now=day(20.5))
    assert [i.label for i in listed] == ['News', 'Plus']           # the hidden channel left out
    news, plus = (i.props for i in listed)
    assert (news['silo.prev.title'], news['silo.now.title'], news['silo.next.title']) == ('Desk', 'Football', 'Late')
    assert news['silo.now.times'] == '19:00 – 22:00' and news['silo.now.left'] == '90'
    assert news['silo.archive'] == '1' and news['silo.prev.broadcastid'] == '70'
    assert 'silo.prev.title' not in plus and plus['silo.later.title'] == 'Darts'   # no catch-up: no earlier
    assert listed[1].art['icon'] == 'p.png'
    assert published == {'mini_now': '1', 'mini_for': '20'}       # opens on channel 20
