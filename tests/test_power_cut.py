# -*- coding: utf-8 -*-
"""What a power cut can leave behind: the add-on starts anyway."""
import json
import os
import sqlite3

from resources.lib.silokodi import fileio
from resources.lib.silokodi.store import Store
from resources.lib.silokodi.syncdb import SyncDB


def test_write_atomic_replaces_whole_files_and_leaves_no_temporary(tmp_path):
    path = str(tmp_path / 'data.json')
    fileio.write_json(path, {'a': 1})
    fileio.write_json(path, {'a': 2})
    assert json.load(open(path)) == {'a': 2}
    assert os.listdir(str(tmp_path)) == ['data.json']
    fileio.write_atomic(path, b'raw', mode=0o600)
    assert open(path, 'rb').read() == b'raw'
    assert oct(os.stat(path).st_mode & 0o777) == oct(0o600)


def test_a_half_written_temporary_never_replaces_the_file(tmp_path, monkeypatch):
    path = str(tmp_path / 'data.json')
    fileio.write_json(path, {'kept': True})

    def cut(*args):
        raise OSError('power cut')
    monkeypatch.setattr(fileio.os, 'fsync', cut)  # the cut comes before the rename
    try:
        fileio.write_json(path, {'kept': False})
    except OSError:
        pass
    assert json.load(open(path)) == {'kept': True}


def test_sign_in_survives_an_unreadable_record(tmp_path):
    store = Store(str(tmp_path))
    store.update(server_url='https://silo.test', refresh_token='r1', profile_id='p1')
    device = store.get('device_id')
    open(store.path, 'w').write('{"server_url": "https://si')  # cut mid-write
    again = Store(str(tmp_path))
    assert again.recovered and again.signed_in and again.get('device_id') == device
    assert json.load(open(again.path))['refresh_token'] == 'r1'  # the record is whole again


def test_a_missing_record_is_simply_signed_out(tmp_path):
    store = Store(str(tmp_path))
    assert not store.recovered and not store.signed_in and store.get('device_id')


def test_a_damaged_library_database_is_set_aside_and_started_again(tmp_path):
    db = SyncDB(str(tmp_path))
    db.set_meta('k', 1)
    db._conn.close()
    with open(db.path, 'r+b') as handle:  # wreck the header
        handle.write(b'not a database' * 8)
    again = SyncDB(str(tmp_path))
    assert again.damaged
    assert again.meta('k') is None
    again.set_meta('k', 2)
    assert again.meta('k') == 2
    assert any(name.startswith('silokodi.db.damaged-') for name in os.listdir(str(tmp_path)))


def test_a_healthy_database_opens_as_before(tmp_path):
    db = SyncDB(str(tmp_path))
    db.set_meta('k', 1)
    db._conn.close()
    again = SyncDB(str(tmp_path))
    assert again.damaged is None and again.meta('k') == 1
    assert sqlite3.connect(again.path).execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
