"""Anime Tracks service.

For files under an anime folder: picks Japanese audio + English (full) subtitles,
and remembers any track change you make, applying it to other files in that folder.
"""
import json
import os
import time

import xbmc
import xbmcaddon
import xbmcgui

from resources.lib import logic, store

ADDON_ID = 'service.animetracks'
TICK = 0.5          # seconds between checks while playing
GRACE = 3.0         # seconds after our own change before a change counts as yours
STABLE = 2.0        # a new selection must hold this long before it is saved
MAX_WAIT = 20       # ticks to wait for the stream list to appear


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, msg), level)


def rpc(method, params=None):
    req = {'jsonrpc': '2.0', 'id': 1, 'method': method}
    if params is not None:
        req['params'] = params
    try:
        resp = json.loads(xbmc.executeJSONRPC(json.dumps(req)))
    except ValueError:
        return None
    if 'error' in resp:
        log('%s failed: %s' % (method, resp['error']), xbmc.LOGWARNING)
        return None
    return resp.get('result')


def video_player_id():
    for player in rpc('Player.GetActivePlayers') or []:
        if player.get('type') == 'video':
            return player.get('playerid')
    return None


def read_streams(pid):
    return rpc('Player.GetProperties', {
        'playerid': pid,
        'properties': ['audiostreams', 'currentaudiostream', 'subtitles',
                       'currentsubtitle', 'subtitleenabled'],
    }) or {}


def current_state(props):
    audio = (props.get('currentaudiostream') or {}).get('index')
    enabled = bool(props.get('subtitleenabled'))
    sub = (props.get('currentsubtitle') or {}).get('index') if enabled else None
    return audio, enabled, sub


def find(tracks, index):
    for t in tracks or []:
        if t.get('index') == index:
            return t
    return None


class Settings(object):
    def __init__(self):
        addon = xbmcaddon.Addon()
        self.enabled = self._bool(addon, 'enabled', True)
        self.roots = [r for r in (addon.getSetting('folders') or 'Anime').split(',') if r.strip()]
        self.scope = self._int(addon, 'scope', 0)
        self.jpn = logic.parse_codes(addon.getSetting('audio_langs'), logic.JPN_CODES)
        self.eng = logic.parse_codes(addon.getSetting('sub_langs'), logic.ENG_CODES)
        self.no_jpn = ['signs', 'full', 'leave'][min(max(self._int(addon, 'no_jpn', 0), 0), 2)]
        self.notify = self._bool(addon, 'notify', True)
        self.debug = self._bool(addon, 'debug', False)

    @staticmethod
    def _bool(addon, key, default):
        value = addon.getSetting(key)
        return default if value == '' else value.lower() == 'true'

    @staticmethod
    def _int(addon, key, default):
        try:
            return int(addon.getSetting(key))
        except (TypeError, ValueError):
            return default


class Session(object):
    """State for the file that is currently playing."""

    def __init__(self, path, key, settings):
        self.path = path
        self.key = key
        self.settings = settings
        self.waits = 0
        self.applied_at = None    # time we last changed streams
        self.target = None        # what we asked for
        self.baseline = None      # settled state; changes from this are yours
        self.reapplied = False
        self.candidate = None     # a changed state waiting to prove it is stable
        self.candidate_since = 0.0


class Service(xbmc.Player):
    def __init__(self):
        super(Service, self).__init__()
        self.session = None
        self.pending = None

    # Player callbacks run on Kodi's callback thread; keep them tiny.
    def onAVStarted(self):
        try:
            self.pending = self.getPlayingFile()
        except RuntimeError:
            self.pending = None

    def onPlayBackStopped(self):
        self.session, self.pending = None, None

    def onPlayBackEnded(self):
        self.session, self.pending = None, None

    def onPlayBackError(self):
        self.session, self.pending = None, None

    # ------------------------------------------------------------ main loop work

    def tick(self):
        if self.pending:
            path, self.pending = self.pending, None
            self.start(path)
        if self.session is not None:
            try:
                self.step(self.session)
            except Exception as exc:  # never let one bad file kill the service
                log('error: %r' % (exc,), xbmc.LOGERROR)
                self.session = None

    def start(self, path):
        settings = Settings()
        if not settings.enabled:
            return
        folder = logic.folder_of(path)
        root = logic.anime_root(folder, settings.roots)
        if root is None:
            self.session = None
            if settings.debug:
                log('out of scope: %s' % path)
            return
        key = logic.pref_key(folder, root, settings.scope, path)
        self.session = Session(path, key, settings)
        log('in scope: %s (key %s)' % (os.path.basename(folder.rstrip('/')) or folder, key))

    def step(self, s):
        pid = video_player_id()
        if pid is None:
            return
        props = read_streams(pid)
        audios = props.get('audiostreams') or []
        subs = props.get('subtitles') or []

        if s.applied_at is None:
            if not audios and s.waits < MAX_WAIT:
                s.waits += 1
                return
            self.apply(s, pid, props, audios, subs)
            return

        state = current_state(props)
        if s.baseline is None:
            if time.time() - s.applied_at < GRACE:
                return
            if s.target and state != s.target and not s.reapplied:
                # Kodi overrode us right after start; try once more.
                s.reapplied = True
                log('selection was overridden, re-applying')
                self.set_streams(pid, props, s.target)
                s.applied_at = time.time()
                return
            s.baseline = state
            return

        # Kodi briefly reports stale indices while it switches streams, and you may change
        # audio then subtitles back to back. Only save once the new selection holds steady.
        now = time.time()
        if state == s.baseline or now - s.applied_at < GRACE:
            s.candidate = None
            return
        if state != s.candidate:
            s.candidate, s.candidate_since = state, now
            return
        if now - s.candidate_since >= STABLE:
            self.remember(s, state, audios, subs)
            s.baseline, s.candidate = state, None

    def apply(self, s, pid, props, audios, subs):
        st = s.settings
        pref = store.get(s.key)
        d = logic.decide(audios, subs, pref, st.no_jpn, st.jpn, st.eng)
        audio = d['audio']
        sub = d['sub']
        enabled = d['sub_enabled']

        cur_audio, cur_enabled, cur_sub = current_state(props)
        target_audio = audio['index'] if audio is not None else cur_audio
        if enabled is False:
            target = (target_audio, False, None)
        elif enabled and sub is not None:
            target = (target_audio, True, sub['index'])
        else:
            target = (target_audio, cur_enabled, cur_sub)

        self.set_streams(pid, props, target)
        s.applied_at = time.time()
        s.target = target
        summary = logic.describe(audio, sub, enabled) or 'left as is'
        log('%s -> %s [%s] audio=%s sub=%s/%s' % (
            os.path.basename(s.path), summary, d['reason'],
            target[0], target[1], target[2]))
        if st.debug:
            log('audio streams: %s' % json.dumps(audios))
            log('subtitles: %s' % json.dumps(subs))
        if st.notify and (audio is not None or sub is not None or enabled is False):
            prefix = 'Remembered' if d['reason'] == 'remembered' else 'Anime'
            xbmcgui.Dialog().notification(prefix, summary, xbmcgui.NOTIFICATION_INFO, 2500, False)

    @staticmethod
    def set_streams(pid, props, target):
        cur_audio, cur_enabled, cur_sub = current_state(props)
        audio, enabled, sub = target
        if audio is not None and audio != cur_audio:
            rpc('Player.SetAudioStream', {'playerid': pid, 'stream': audio})
        if enabled is False:
            if cur_enabled:
                rpc('Player.SetSubtitle', {'playerid': pid, 'subtitle': 'off'})
        elif enabled and sub is not None and (sub != cur_sub or not cur_enabled):
            rpc('Player.SetSubtitle', {'playerid': pid, 'subtitle': sub, 'enable': True})

    def remember(self, s, state, audios, subs):
        audio_idx, enabled, sub_idx = state
        audio = find(audios, audio_idx)
        sub = find(subs, sub_idx) if enabled else None
        pref = {
            'audio': logic.audio_sig(audio, s.settings.jpn) if audio is not None else None,
            'sub': logic.sub_sig(sub, enabled, s.settings.eng),
            'example': os.path.basename(s.path),
        }
        store.put(s.key, pref)
        summary = logic.describe(audio, sub, enabled)
        log('remembered for %s: %s' % (s.key, summary))
        if s.settings.notify:
            xbmcgui.Dialog().notification('Saved for this folder', summary,
                                          xbmcgui.NOTIFICATION_INFO, 3000, False)


def main():
    log('started')
    monitor = xbmc.Monitor()
    service = Service()
    while not monitor.abortRequested():
        if monitor.waitForAbort(TICK):
            break
        service.tick()
    log('stopped')


if __name__ == '__main__':
    main()
