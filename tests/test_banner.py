# -*- coding: utf-8 -*-
from resources.lib.silokodi import banner


def test_the_banner_lists_the_programmes_after_the_one_shown_in_order():
    shows = [{'title': 'C', 'start': 300}, {'title': 'A', 'start': 100}, {'title': 'B', 'start': 200},
             {'title': 'Old', 'start': 0}]
    assert [s['title'] for s in banner.following(shows, 100)] == ['B', 'C']
    assert [s['title'] for s in banner.following(shows, 250)] == ['C']
