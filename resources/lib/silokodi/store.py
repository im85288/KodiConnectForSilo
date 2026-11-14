# -*- coding: utf-8 -*-
"""The sign-in record: server address, tokens, device id and chosen profile.

It lives in one JSON file in the add-on's profile folder. The service owns the
tokens once signed in; the plugin process writes the file only when someone
signs in or out, and the service notices the change by the file's mtime.

Each write also keeps a last-good copy (account.json.bak). If the file can't
be read (a power cut while the storage held it half written), the copy is
read instead: without it the add-on would be signed out, and a new device id
would make it a new device in Silo.
"""
import json
import os
import threading
import uuid

from .fileio import write_atomic

FILENAME = 'account.json'
BACKUP_SUFFIX = '.bak'


class Store(object):
    def __init__(self, folder):
        self.path = os.path.join(folder, FILENAME)
        self._lock = threading.RLock()
        self._data = {}
        self._mtime = None
        self.reload()

    def reload(self):
        with self._lock:
            self.recovered = False
            try:
                self._data = self._read(self.path)
                self._mtime = os.path.getmtime(self.path)
            except (IOError, OSError, ValueError):
                self._data, self._mtime = {}, None
                try:
                    self._data = self._read(self.path + BACKUP_SUFFIX)
                    self.recovered = os.path.exists(self.path)  # unreadable, not simply missing
                except (IOError, OSError, ValueError):
                    pass
                if self._data:
                    self._write()  # the file again, from the copy
            if not self._data.get('device_id'):
                self._data['device_id'] = str(uuid.uuid4())

    @staticmethod
    def _read(path):
        with open(path, 'r') as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError('not a sign-in record')
        return data

    def changed_on_disk(self):
        try:
            return os.path.getmtime(self.path) != self._mtime
        except OSError:
            return self._mtime is not None

    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)

    def update(self, **values):
        with self._lock:
            for key, value in values.items():
                if value is None:
                    self._data.pop(key, None)
                else:
                    self._data[key] = value
            self._write()

    def sign_out(self):
        """Forget the account but keep this device's id."""
        with self._lock:
            self._data = {'device_id': self._data['device_id'],
                          'server_url': self._data.get('server_url')}
            self._write()

    @property
    def signed_in(self):
        # Sign-in saves the tokens before the profile is chosen; Silo's
        # library and progress routes need the profile, so wait for both.
        return bool(self.get('server_url') and self.get('refresh_token') and self.get('profile_id'))

    def _write(self):
        data = json.dumps(self._data)
        write_atomic(self.path, data, 0o600)  # holds sign-in tokens
        self._mtime = os.path.getmtime(self.path)
        try:
            write_atomic(self.path + BACKUP_SUFFIX, data, 0o600)
        except (IOError, OSError):
            pass  # the copy is a spare: the record itself is saved
