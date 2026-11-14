"""Remembered per-folder track choices, kept in the add-on's profile folder."""
import json
import os
import time

import xbmcaddon
import xbmcvfs


def _path():
    profile = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
    if not xbmcvfs.exists(profile):
        xbmcvfs.mkdirs(profile)
    return os.path.join(profile, 'prefs.json')


def load():
    try:
        with open(_path(), 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get('folders'), dict):
            return data
    except (OSError, ValueError):
        pass
    return {'version': 1, 'folders': {}}


def save(data):
    path = _path()
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, path)


def get(key):
    return load()['folders'].get(key)


def put(key, pref):
    data = load()
    pref = dict(pref)
    pref['updated'] = int(time.time())
    data['folders'][key] = pref
    save(data)


def forget(key):
    data = load()
    removed = data['folders'].pop(key, None) is not None
    save(data)
    return removed


def clear():
    save({'version': 1, 'folders': {}})
