# -*- coding: utf-8 -*-
"""Files that survive a power cut: a box on a timed smart plug loses power
whenever the schedule says, whatever it is writing.

A file is written to a temporary copy, flushed to the storage, then swapped in
by a rename, and the folder is flushed too, so after a cut the file is either
the old version or the new one, never empty or half written.
"""
import json
import os


def sync_folder(folder):
    """Flush a folder's entries (the rename) to the storage, where that can be
    done: Windows can't open a folder, which a rename there doesn't need."""
    try:
        fd = os.open(folder or '.', os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def write_atomic(path, data, mode=None):
    """Replace path with data (bytes, or text as UTF-8) in one step."""
    if not isinstance(data, bytes):
        data = data.encode('utf-8')
    temp = path + '.tmp'
    with open(temp, 'wb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    if mode is not None:
        try:
            os.chmod(temp, mode)
        except OSError:
            pass
    os.replace(temp, path)
    sync_folder(os.path.dirname(path))


def write_json(path, value, mode=None):
    write_atomic(path, json.dumps(value), mode)
