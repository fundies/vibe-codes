"""Pure track-selection logic for Anime Tracks.

No Kodi imports here, so this module can be unit-tested on any machine.
Track dicts follow Kodi JSON-RPC Player.GetProperties output:
  audio:    index, language, name, codec, channels, isdefault, isoriginal, isimpaired
  subtitle: index, language, name, isdefault, isforced, isimpaired
"""
import re

JPN_CODES = {'jpn', 'ja', 'jap', 'jp', 'japanese'}
ENG_CODES = {'eng', 'en', 'english'}
UNTAGGED = {'', 'und', 'unk', 'unknown', 'mul', 'mis', 'zxx', 'none', 'null', 'n/a'}

JPN_NAME = re.compile(r'japan|\bjpn\b|\bjp\b|\bja\b|nihongo|日本', re.I)
ENG_NAME = re.compile(r'english|\beng\b|\ben\b', re.I)
COMMENTARY = re.compile(r'comment', re.I)
FORCED_NAME = re.compile(r'forced', re.I)
SIGNS_NAME = re.compile(r'sign|song|s\s*&\s*s|\bs/s\b|karaoke|lyric|on[\s-]?screen|titles?\s+only', re.I)
FULL_NAME = re.compile(r'full|dialog|complete', re.I)
SDH_NAME = re.compile(r'\bsdh\b|\bcc\b|hearing|impaired|closed\s*caption', re.I)

# How much each subtitle "kind" is wanted, per mode.
FULL_RANK = {'full': 40, 'regular': 30, 'sdh': 15, 'signs': -40, 'forced': -50}
SIGNS_RANK = {'signs': 40, 'forced': 35, 'regular': -20, 'full': -30, 'sdh': -30}


def parse_codes(text, default):
    codes = {c.strip().lower() for c in (text or '').split(',') if c.strip()}
    return codes or set(default)


def norm_lang(value):
    return (value or '').strip().lower()


def norm_name(value):
    value = (value or '').lower()
    value = re.sub(r'[\[\]\(\)\{\}_\-.,:|/]+', ' ', value)
    return ' '.join(value.split())


def _tokens(value):
    return set(norm_name(value).split())


def jaccard(a, b):
    a, b = _tokens(a), _tokens(b)
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def lang_affinity(track, codes, name_re, other_name_re=None):
    """> 0: track is in the wanted language, < 0: clearly another language, 0: unknown."""
    lang = norm_lang(track.get('language'))
    name = track.get('name') or ''
    score = 0
    if lang in codes:
        score += 100
    elif lang not in UNTAGGED:
        score -= 100
    if name_re.search(name):
        score += 60
    elif other_name_re is not None and other_name_re.search(name):
        score -= 40
    return score


def is_commentary(track):
    return bool(COMMENTARY.search(track.get('name') or ''))


# ---------------------------------------------------------------- audio

def pick_audio(tracks, jpn_codes=JPN_CODES, eng_codes=ENG_CODES):
    """Return (track, reason). track is None when no Japanese track can be identified."""
    best, best_score = None, 0.0
    for t in tracks:
        score = lang_affinity(t, jpn_codes, JPN_NAME, ENG_NAME)
        if score <= 0:
            continue
        if is_commentary(t):
            score -= 300
        if t.get('isoriginal'):
            score += 20
        if t.get('isdefault'):
            score += 2
        score += min(int(t.get('channels') or 0), 8) * 0.5  # prefer surround on ties
        if score > best_score:
            best, best_score = t, score
    if best is not None:
        return best, 'japanese'

    # Dual-audio release where only the dub is tagged: the lone untagged track is Japanese.
    english = [t for t in tracks if lang_affinity(t, eng_codes, ENG_NAME) > 0]
    untagged = [t for t in tracks
                if norm_lang(t.get('language')) in UNTAGGED
                and not is_commentary(t)
                and lang_affinity(t, eng_codes, ENG_NAME) <= 0]
    if english and len(untagged) == 1:
        return untagged[0], 'untagged-beside-english'
    return None, 'no-japanese'


def audio_sig(track, jpn_codes=JPN_CODES):
    return {
        'lang': norm_lang(track.get('language')),
        'name': norm_name(track.get('name')),
        'codec': (track.get('codec') or '').lower(),
        'channels': int(track.get('channels') or 0),
        'index': track.get('index'),
        'jp': lang_affinity(track, jpn_codes, JPN_NAME, ENG_NAME) > 0,
    }


def match_audio(tracks, sig, jpn_codes=JPN_CODES, eng_codes=ENG_CODES):
    """Find the track in this file that best matches a remembered choice."""
    best, best_score = None, None
    for t in tracks:
        score = 0.0
        lang = norm_lang(t.get('language'))
        if sig.get('lang') and lang:
            score += 100 if lang == sig['lang'] else -100
        name = norm_name(t.get('name'))
        if sig.get('name') and name:
            score += 50 if name == sig['name'] else 30 * jaccard(name, sig['name'])
        if (t.get('codec') or '').lower() == sig.get('codec'):
            score += 5
        if int(t.get('channels') or 0) == sig.get('channels'):
            score += 5
        if t.get('index') == sig.get('index'):
            score += 3
        if best_score is None or score > best_score:
            best, best_score = t, score
    if best is not None and best_score >= 60:
        return best
    if sig.get('jp'):
        return pick_audio(tracks, jpn_codes, eng_codes)[0]
    if sig.get('lang'):
        for t in tracks:
            if norm_lang(t.get('language')) == sig['lang']:
                return t
    for t in tracks:
        if t.get('index') == sig.get('index'):
            return t
    return None


# ------------------------------------------------------------ subtitles

def sub_kind(track):
    name = track.get('name') or ''
    if track.get('isforced') or FORCED_NAME.search(name):
        return 'forced'
    if FULL_NAME.search(name):
        return 'full'
    if SIGNS_NAME.search(name):
        return 'signs'
    if track.get('isimpaired') or SDH_NAME.search(name):
        return 'sdh'
    return 'regular'


def pick_sub(tracks, mode='full', eng_codes=ENG_CODES):
    """Best English subtitle. mode 'full' = dialogue subs, 'signs' = signs & songs only."""
    rank = FULL_RANK if mode == 'full' else SIGNS_RANK
    best, best_score = None, None
    for t in tracks:
        affinity = lang_affinity(t, eng_codes, ENG_NAME)
        if affinity <= 0 or is_commentary(t):
            continue
        score = affinity + rank[sub_kind(t)] + (2 if t.get('isdefault') else 0)
        if best_score is None or score > best_score:
            best, best_score = t, score
    if mode == 'signs' and best is not None and sub_kind(best) not in ('signs', 'forced'):
        return None
    return best


def sub_sig(track, enabled, eng_codes=ENG_CODES):
    if not enabled or track is None:
        return {'enabled': False}
    return {
        'enabled': True,
        'lang': norm_lang(track.get('language')),
        'name': norm_name(track.get('name')),
        'kind': sub_kind(track),
        'index': track.get('index'),
        'en': lang_affinity(track, eng_codes, ENG_NAME) > 0,
    }


def match_sub(tracks, sig, eng_codes=ENG_CODES):
    """Return (track, enabled). enabled False = turn subtitles off."""
    if not sig.get('enabled'):
        return None, False
    best, best_score = None, None
    for t in tracks:
        score = 0.0
        lang = norm_lang(t.get('language'))
        if sig.get('lang') and lang:
            score += 100 if lang == sig['lang'] else -100
        if sub_kind(t) == sig.get('kind'):
            score += 60
        name = norm_name(t.get('name'))
        if sig.get('name') and name:
            score += 50 if name == sig['name'] else 30 * jaccard(name, sig['name'])
        if t.get('index') == sig.get('index'):
            score += 3
        if best_score is None or score > best_score:
            best, best_score = t, score
    if best is not None and best_score >= 100:
        return best, True
    if sig.get('en'):
        mode = 'signs' if sig.get('kind') in ('signs', 'forced') else 'full'
        track = pick_sub(tracks, mode, eng_codes)
        if track is not None:
            return track, True
    for t in tracks:
        if t.get('index') == sig.get('index'):
            return t, True
    return None, True


# ---------------------------------------------------------------- decide

def decide(audios, subs, pref=None, no_jpn_mode='signs',
           jpn_codes=JPN_CODES, eng_codes=ENG_CODES):
    """Return {'audio': track|None, 'sub': track|None, 'sub_enabled': True|False|None, 'reason': str}.

    None for audio/sub means "leave what Kodi chose"; sub_enabled False means "turn subs off".
    """
    if pref:
        audio = match_audio(audios, pref['audio'], jpn_codes, eng_codes) if pref.get('audio') else None
        if pref.get('sub'):
            sub, enabled = match_sub(subs, pref['sub'], eng_codes)
        else:
            sub, enabled = None, None
        return {'audio': audio, 'sub': sub, 'sub_enabled': enabled, 'reason': 'remembered'}

    audio, why = pick_audio(audios, jpn_codes, eng_codes)
    if audio is not None:
        sub = pick_sub(subs, 'full', eng_codes)
        if sub is None:
            untagged = [s for s in subs if norm_lang(s.get('language')) in UNTAGGED and not is_commentary(s)]
            if len(subs) == 1 and len(untagged) == 1:
                sub = untagged[0]
        return {'audio': audio, 'sub': sub, 'sub_enabled': True if sub is not None else None, 'reason': why}

    if no_jpn_mode == 'leave':
        return {'audio': None, 'sub': None, 'sub_enabled': None, 'reason': why}
    sub = pick_sub(subs, 'full' if no_jpn_mode == 'full' else 'signs', eng_codes)
    return {'audio': None, 'sub': sub, 'sub_enabled': True if sub is not None else None,
            'reason': why + '-' + no_jpn_mode}


# ------------------------------------------------------------ paths

def folder_of(path):
    """Folder (with trailing slash) that contains the playing file."""
    path = path or ''
    if path.startswith('stack://'):
        path = path[len('stack://'):].split(' , ')[0]
    path = path.replace('\\', '/')
    i = path.rfind('/')
    return path[:i + 1] if i >= 0 else path


def anime_root(folder, roots):
    """Return the anime root folder containing `folder`, or None if out of scope.

    roots: names like 'Anime' (matches any path segment, case-insensitive) or
    fragments containing '/', e.g. 'media/share/Anime' (substring match).
    """
    segs = folder.split('/')
    low = [s.lower() for s in segs]
    for root in roots:
        root = root.strip().strip('/')
        if not root:
            continue
        if '/' in root:
            idx = folder.lower().find('/' + root.lower() + '/')
            if idx >= 0:
                return folder[:idx + len(root) + 2]
        else:
            for i, seg in enumerate(low):
                if seg == root.lower():
                    return '/'.join(segs[:i + 1]) + '/'
    return None


_EPISODE_CUT = re.compile(
    r'(\bS\d{1,2}\s*E\d{1,3}\b|\bS\d{1,2}\b|\bE\d{2,4}\b|\bEp?\s*\d{1,4}\b|\s-\s*\d{1,4}\b|'
    r'\b\d{3,4}p\b|\[|\(|\bv\d\b)', re.I)


def series_name(path):
    """Best-effort show name from a filename, e.g. 'Medalist.S02E09.1080p...' -> 'medalist'."""
    base = (path or '').replace('\\', '/').rsplit('/', 1)[-1]
    base = re.sub(r'\.[A-Za-z0-9]{2,4}$', '', base)           # extension
    base = re.sub(r'^\s*(\[[^\]]*\]\s*)+', '', base)          # leading [Group] tags
    base = re.sub(r'[._]+', ' ', base)
    m = _EPISODE_CUT.search(base)
    if m:
        base = base[:m.start()]
    name = ' '.join(base.lower().split()).strip(' -')
    return name or None


def pref_key(folder, root, scope, path=None):
    """Where a remembered choice is stored.

    scope 0: the file's own folder. scope 1: the show folder (first level under the root).
    Files sitting loose in the root are keyed by the series name in their filename, so
    unrelated shows dropped straight into Anime/ don't share a choice.
    """
    if folder == root and path:
        name = series_name(path)
        if name:
            return root + '#' + name
    if scope == 1:
        first = folder[len(root):].split('/')[0]
        return root + first + '/' if first else root
    return folder


LANG_NAMES = {'jpn': 'Japanese', 'ja': 'Japanese', 'eng': 'English', 'en': 'English',
              'spa': 'Spanish', 'por': 'Portuguese', 'fre': 'French', 'fra': 'French',
              'ger': 'German', 'deu': 'German', 'ita': 'Italian', 'chi': 'Chinese',
              'zho': 'Chinese', 'kor': 'Korean', 'rus': 'Russian', 'ara': 'Arabic'}


def describe(audio, sub, sub_enabled):
    parts = []
    if audio is not None:
        lang = norm_lang(audio.get('language'))
        parts.append('Audio: ' + (LANG_NAMES.get(lang) or audio.get('name') or lang or 'track %s' % audio.get('index')))
    if sub_enabled is False:
        parts.append('Subs: off')
    elif sub is not None:
        lang = norm_lang(sub.get('language'))
        label = LANG_NAMES.get(lang) or sub.get('name') or lang or 'track %s' % sub.get('index')
        kind = sub_kind(sub)
        parts.append('Subs: %s%s' % (label, '' if kind == 'regular' else ' (%s)' % kind))
    return ' · '.join(parts)
