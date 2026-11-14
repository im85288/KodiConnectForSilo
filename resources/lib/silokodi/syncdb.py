# -*- coding: utf-8 -*-
"""KodiConnectForSilo's own bookkeeping: which Silo item became which Kodi row,
what each looked like when last written, and the current artwork URLs."""
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager

from .mapping import unsigned

SCHEMA = '''
CREATE TABLE IF NOT EXISTS items (
    content_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    library_id TEXT,
    parent_id TEXT,
    season_number INTEGER,
    kodi_id INTEGER,
    kodi_file_id INTEGER,
    kodi_path_id INTEGER,
    fingerprint TEXT,
    state TEXT
);
CREATE INDEX IF NOT EXISTS ix_items_kind ON items (kind, library_id);
CREATE INDEX IF NOT EXISTS ix_items_parent ON items (parent_id);
CREATE INDEX IF NOT EXISTS ix_items_kodi ON items (kind, kodi_id);
CREATE TABLE IF NOT EXISTS art (
    content_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    url TEXT NOT NULL,
    PRIMARY KEY (content_id, kind)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
'''

COLUMNS = ('content_id', 'kind', 'library_id', 'parent_id', 'season_number', 'kodi_id', 'kodi_file_id',
           'kodi_path_id', 'fingerprint', 'state')


class SyncDB(object):
    """Thread-safe: one connection, one lock. Writes commit immediately,
    except inside batch(): a sync writes a batch of titles and commits them
    once (each commit, even in WAL mode, cost the SHIELD's storage time)."""

    def __init__(self, folder):
        self.path = os.path.join(folder, 'silokodi.db')
        self._lock = threading.RLock()
        self._batching = 0
        self.damaged = None  # why a damaged database was set aside at start, if one was
        try:
            self._conn = self._connect(check=True)
        except sqlite3.DatabaseError as error:
            # Damaged storage (a power cut, an SD card going bad): keep the file
            # for a look, start empty. It only mirrors Silo, so the next sync
            # rebuilds it, and Kodi's rows are found again by their files and
            # folders rather than written twice (Syncer._existing).
            self.damaged = str(error) or type(error).__name__
            self._set_aside()
            self._conn = self._connect(check=False)
        # A sync commits tens of thousands of small writes. With the default
        # journal each one waits for the disk, which on a SHIELD's flash
        # storage made a first sync crawl at about one movie a second. In WAL
        # mode with synchronous=NORMAL a commit doesn't wait for the disk;
        # a power cut can lose the last few commits, which the next sync
        # rewrites without duplicating Kodi rows.
        self._conn.execute('PRAGMA journal_mode=WAL')
        self._conn.execute('PRAGMA synchronous=NORMAL')
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def _connect(self, check):
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        if check:
            try:
                result = connection.execute('PRAGMA quick_check').fetchone()[0]  # 0.04 s for 22 MB on a Ugoos
            except sqlite3.DatabaseError:
                connection.close()
                raise
            if result != 'ok':
                connection.close()
                raise sqlite3.DatabaseError(result)
        return connection

    def _set_aside(self):
        stamp = time.strftime('%Y%m%d-%H%M%S')
        for suffix in ('', '-wal', '-shm'):
            if os.path.exists(self.path + suffix):
                os.replace(self.path + suffix, '%s.damaged-%s%s' % (self.path, stamp, suffix))

    def _commit(self):
        if not self._batching:
            self._conn.commit()

    @contextmanager
    def batch(self):
        """Writes inside commit together when it ends (nested batches, once).
        If it ends in an error they're undone, as Kodi's database undoes its
        half of a sync's batch: rows kept for titles Kodi no longer has would
        hand their Kodi ids to the next titles, which then overwrite each other."""
        with self._lock:
            self._batching += 1
        failed = False
        try:
            yield self
        except BaseException:
            failed = True
            raise
        finally:
            with self._lock:
                self._batching -= 1
                if not self._batching:
                    if failed:
                        self._conn.rollback()
                    else:
                        self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()

    def _query(self, sql, args=()):
        with self._lock:
            return [dict(row) for row in self._conn.execute(sql, args).fetchall()]

    def _write(self, sql, args=()):
        with self._lock:
            self._conn.execute(sql, args)
            self._commit()

    # ----- items -----

    def get(self, content_id):
        rows = self._query('SELECT * FROM items WHERE content_id = ?', (content_id,))
        return rows[0] if rows else None

    def by_kodi(self, kind, kodi_id):
        rows = self._query('SELECT * FROM items WHERE kind = ? AND kodi_id = ?', (kind, kodi_id))
        return rows[0] if rows else None

    def items(self, kind, library_id=None):
        if library_id is None:
            return self._query('SELECT * FROM items WHERE kind = ?', (kind,))
        return self._query('SELECT * FROM items WHERE kind = ? AND library_id = ?', (kind, library_id))

    def counts(self):
        """{kind: how many} for every kind of item synced."""
        return {row['kind']: row['n'] for row in self._query('SELECT kind, COUNT(*) AS n FROM items GROUP BY kind')}

    def children(self, parent_id, kind=None):
        if kind:
            return self._query('SELECT * FROM items WHERE parent_id = ? AND kind = ?', (parent_id, kind))
        return self._query('SELECT * FROM items WHERE parent_id = ?', (parent_id,))

    def libraries(self):
        return [row['library_id'] for row in
                self._query("SELECT DISTINCT library_id FROM items WHERE kind IN ('movie', 'tvshow')")]

    def put(self, **row):
        values = [row.get(column) for column in COLUMNS]
        self._write('INSERT OR REPLACE INTO items(%s) VALUES (%s)' % (', '.join(COLUMNS), ', '.join('?' * len(COLUMNS))),
                    values)

    def set_state(self, content_id, state):
        self._write('UPDATE items SET state = ? WHERE content_id = ?', (state, content_id))

    def set_fingerprints(self, pairs):
        """[(content_id, fingerprint)], in one commit."""
        with self._lock:
            self._conn.executemany('UPDATE items SET fingerprint = ? WHERE content_id = ?',
                                   [(fingerprint, content_id) for content_id, fingerprint in pairs])
            self._commit()

    def forget_fingerprints(self):
        """Make the next sync rewrite every item."""
        self._write('UPDATE items SET fingerprint = NULL')

    def remove(self, content_id):
        with self._lock:
            self._conn.execute('DELETE FROM items WHERE content_id = ?', (content_id,))
            self._conn.execute('DELETE FROM art WHERE content_id = ?', (content_id,))
            self._commit()

    def clear(self):
        with self._lock:
            self._conn.execute('DELETE FROM items')
            self._conn.execute('DELETE FROM art')
            self._conn.execute('DELETE FROM meta')
            self._commit()

    # ----- artwork -----

    def clear_art(self, keep_prefix=None):
        """Forget the stored artwork links (but those whose id starts with
        keep_prefix): the relay asks Silo again for each picture as Kodi next
        shows it (Relay.fetch_art)."""
        with self._lock:
            if keep_prefix:
                self._conn.execute('DELETE FROM art WHERE substr(content_id, 1, ?) != ?',
                                   (len(keep_prefix), keep_prefix))
            else:
                self._conn.execute('DELETE FROM art')
            self._commit()

    def set_art(self, content_id, urls):
        """urls: {kind: Silo URL}; replaces the item's whole set. Returns the
        kinds whose image changed (its address, not just its signature): Kodi
        holds the old one in its cache under the same local address."""
        with self._lock:
            before = dict(self._conn.execute('SELECT kind, url FROM art WHERE content_id = ?', (content_id,)))
            self._conn.execute('DELETE FROM art WHERE content_id = ?', (content_id,))
            self._conn.executemany('INSERT INTO art(content_id, kind, url) VALUES (?, ?, ?)',
                                   [(content_id, kind, url) for kind, url in urls.items()])
            self._commit()
        return [kind for kind, url in urls.items()
                if before.get(kind) and unsigned(before[kind]) != unsigned(url)]

    def forget_kodi_row(self, content_id):
        """A title with no Kodi row of its own: the next sync writes it, with a new one."""
        self._write('UPDATE items SET kodi_id = NULL, fingerprint = NULL WHERE content_id = ?', (content_id,))

    def forget_titles(self):
        """Clear films' and shows' fingerprints (not episodes'), so the next
        sync writes them again from their details: for what Silo's catalog
        cards don't carry (Rotten Tomatoes' score)."""
        self._write("UPDATE items SET fingerprint = NULL WHERE kind IN ('movie', 'tvshow')")

    def forget_svg_art(self):
        """Clear the fingerprint of items saved with SVG art (written before
        mapping.drawable), so the next sync rewrites them without it."""
        self._write("UPDATE items SET fingerprint = NULL WHERE content_id IN (SELECT content_id FROM art "
                    "WHERE lower(substr(url, 1, instr(url || '?', '?') - 1)) LIKE '%.svg')")

    def art_kinds(self, content_id):
        return [row['kind'] for row in self._query('SELECT kind FROM art WHERE content_id = ?', (content_id,))]

    def art(self, content_id, kind):
        rows = self._query('SELECT url FROM art WHERE content_id = ? AND kind = ?', (content_id, kind))
        return rows[0]['url'] if rows else None

    # ----- small values -----

    def meta(self, key, default=None):
        rows = self._query('SELECT value FROM meta WHERE key = ?', (key,))
        return json.loads(rows[0]['value']) if rows else default

    def set_meta(self, key, value):
        self._write('INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)', (key, json.dumps(value)))
