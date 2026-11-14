# -*- coding: utf-8 -*-
import time

import pytest

from resources.lib.silokodi import api
from resources.lib.silokodi import service as service_module
from resources.lib.silokodi.syncdb import SyncDB
from silo_fakes import movie
from resources.lib.silokodi.store import Store
from test_api_playback import Response, client_with
from test_service import bare_service


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path))
    s.update(server_url='https://silo.test', access_token='t', access_expires_at=time.time() + 3600, profile_id='p1')
    return s


def test_4k_menus_ask_for_wider_pictures():
    assert api.art_widths_for(1920) == {}
    assert api.art_widths_for(None) == {}
    assert api.art_widths_for(3840) == {'poster_width': 1000, 'backdrop_width': 3840, 'logo_width': 3840}


def test_every_picture_request_carries_the_widths(store):
    client = client_with(store, [('GET', '/api/v2/catalog/items/movie-1', Response(200, movie())),
                                 ('GET', '/api/v2/catalog/items/movie-1', Response(200, movie()))])
    client.item('movie-1')
    assert client.session.sent[0][3] == {'image_size': 'large'}
    client.art_widths = api.art_widths_for(3840)
    client.item('movie-1')
    assert client.session.sent[1][3] == dict({'image_size': 'large'}, **api.ART_WIDTHS_4K)


def test_changing_sizes_drops_stored_links_once(tmp_path, store, monkeypatch):
    monkeypatch.setattr(service_module.kodi, 'log', lambda message: None)
    db = SyncDB(str(tmp_path))
    db.set_art('movie-1', {'poster': 'https://silo.test/p.webp'})
    db.set_art('row:episode-1', {'fanart': 'https://silo.test/f.webp'})
    service = bare_service(client=client_with(store, []), db=db)
    service.use_art_widths(1920)  # 1080p as before: links kept
    assert db.art('movie-1', 'poster')
    service.use_art_widths(3840)
    assert db.art('movie-1', 'poster') is None and db.meta('art_widths') == api.ART_WIDTHS_4K
    # A home-row card keeps its link: it can't be asked for alone (Kodi would show it blank).
    assert db.art('row:episode-1', 'fanart') == 'https://silo.test/f.webp'
    db.set_art('movie-1', {'poster': 'https://silo.test/p4k.webp'})
    service.use_art_widths(3840)  # unchanged: kept
    assert db.art('movie-1', 'poster')
