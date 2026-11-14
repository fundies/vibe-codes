"""End-to-end test against the Shield's Kodi (needs `adb forward tcp:9090 tcp:9090`)."""
import json
import subprocess
import sys
import time

from kodi_rpc import rpc

KODI = '/storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi'
BLEACH = 'nfs://192.0.2.65/media/share/Anime/[Adosin] Bleach 190-366 (BD 1080p HEVC FLAC) [Dual Audio]/'
OTHER = 'nfs://192.0.2.65/media/share/Anime/Undead Unluck [BD 1080p x265 OPUS][DUAL][Anipakku]/Undead Unluck - 01 [BD 1080p x265 OPUS][DUAL][Anipakku].mkv'
OUTSIDE = 'nfs://192.0.2.65/media/share/TV/Your Honor (2020) S01 (2160p PMTP WEB-DL Hybrid H265 DV HDR10+ DDP 5.1 English - HONE) [REPACK]/Your Honor (2020) S01E01 (2160p PMTP WEB-DL Hybrid H265 DV HDR10+ DDP 5.1 English - HONE) [REPACK].mkv'


def adb(cmd):
    return subprocess.run(['adb', 'shell', cmd], capture_output=True, text=True).stdout


def props():
    r = rpc('Player.GetProperties', {'playerid': 1, 'properties': [
        'audiostreams', 'currentaudiostream', 'subtitles', 'currentsubtitle', 'subtitleenabled']})
    return r.get('result') or {}


def summary(p):
    a = p.get('currentaudiostream') or {}
    s = p.get('currentsubtitle') or {}
    sub = '%s %s "%s"' % (s.get('index'), s.get('language'), s.get('name')) if p.get('subtitleenabled') else 'OFF'
    return 'audio=%s %s "%s" | sub=%s' % (a.get('index'), a.get('language'), a.get('name'), sub)


def play(path, settle=8):
    rpc('Player.Open', {'item': {'file': path}})
    for _ in range(40):
        time.sleep(0.5)
        if (props().get('audiostreams') or []):
            break
    time.sleep(settle)
    return props()


def stop():
    rpc('Player.Stop', {'playerid': 1})
    time.sleep(2)


def ours():
    return [l.split('[service.animetracks] ', 1)[-1] for l in adb(
        'grep "animetracks" %s/temp/kodi.log' % KODI).splitlines()]


def main():
    was_muted = (rpc('Application.GetProperties', {'properties': ['muted']}).get('result') or {}).get('muted')
    rpc('Application.SetMute', {'mute': True})
    adb('rm -f %s/userdata/addon_data/service.animetracks/prefs.json' % KODI)
    seen = len(ours())
    try:
        print('== T1 default: Bleach 207 ==')
        p = play(BLEACH + '[Adosin] Bleach - 207 (BD 1080p HEVC FLAC) [Dual Audio].mkv')
        print('  tracks: audio=%s' % [(t['index'], t['language'], t['name']) for t in p['audiostreams']])
        print('          subs=%s' % [(t['index'], t['language'], t['name'], t.get('isforced')) for t in p['subtitles']])
        print('  now   :', summary(p))

        print('== T2 user switches to English audio + subs OFF ==')
        eng = [t for t in p['audiostreams'] if t['language'] == 'eng'][0]
        rpc('Player.SetAudioStream', {'playerid': 1, 'stream': eng['index']})
        rpc('Player.SetSubtitle', {'playerid': 1, 'subtitle': 'off'})
        time.sleep(5)
        print('  now   :', summary(props()))
        print('  prefs :', adb('cat %s/userdata/addon_data/service.animetracks/prefs.json' % KODI).strip()[:600])
        stop()

        print('== T3 same folder, Bleach 208: should follow the saved choice ==')
        print('  now   :', summary(play(BLEACH + '[Adosin] Bleach - 208 (BD 1080p HEVC FLAC) [Dual Audio].mkv')))
        stop()

        print('== T4 different folder, Undead Unluck 01 (JP+PT audio): default JP + EN ==')
        print('  now   :', summary(play(OTHER)))
        stop()

        print('== T5 outside Anime: add-on must not touch it ==')
        print('  now   :', summary(play(OUTSIDE, settle=6)))
        stop()
    finally:
        try:
            stop()
        except Exception:
            pass
        rpc('Application.SetMute', {'mute': bool(was_muted)})
    print('== add-on log ==')
    for line in ours()[seen:]:
        print('  ' + line)


if __name__ == '__main__':
    sys.exit(main())
