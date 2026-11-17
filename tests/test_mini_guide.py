from resources.lib.silokodi import plugin


class Home(object):
    def __init__(self):
        self.props = {}

    def setProperty(self, key, value):
        self.props[key] = value

    def getProperty(self, key):
        return self.props.get(key, '')

    def clearProperty(self, key):
        self.props.pop(key, None)


def test_up_and_down_step_through_the_playing_group_and_wrap(monkeypatch):
    group = [{'channelid': 7, 'channelnumber': 18, 'label': 'News', 'icon': 'n.png'},
             {'channelid': 8, 'channelnumber': 19, 'label': 'News HD', 'icon': 'h.png', 'hidden': True},
             {'channelid': 9, 'channelnumber': 20, 'label': 'Plus', 'icon': 'p.png'}]
    monkeypatch.setattr(plugin, 'group_channels', lambda label: group if label == 'UK | Sky Sports' else [])
    home = Home()
    monkeypatch.setattr(plugin.kodi, 'HOME', home)
    home.setProperty('silo.mini.number', '18')
    home.setProperty('silo.mini.placed', '1')
    plugin.mini_step('1', 'UK | Sky Sports')
    # The hidden channel is skipped; the new one's details are published and focus waits for its schedule.
    assert [home.getProperty('silo.mini.%s' % k) for k in ('number', 'name', 'logo', 'channelid')] == ['20', 'Plus', 'p.png', '9']
    assert home.getProperty('silo.mini.placed') == ''
    plugin.mini_step('1', 'UK | Sky Sports')
    assert home.getProperty('silo.mini.number') == '18'      # round to the first
    plugin.mini_step('-1', 'UK | Sky Sports')
    assert home.getProperty('silo.mini.number') == '20'
