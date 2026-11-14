import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'service.animetracks', 'resources', 'lib'))
import logic  # noqa: E402


def A(i, lang, name='', codec='aac', ch=2, **kw):
    d = {'index': i, 'language': lang, 'name': name, 'codec': codec, 'channels': ch}
    d.update(kw)
    return d


def S(i, lang, name='', **kw):
    d = {'index': i, 'language': lang, 'name': name}
    d.update(kw)
    return d


class PickDefaults(unittest.TestCase):
    def test_judas_bleach_dual_audio_two_english_subs(self):
        audios = [A(0, 'eng', 'English', 'opus'), A(1, 'jpn', 'Japanese', 'opus')]
        subs = [S(0, 'eng', 'English [Signs & Songs]', isforced=True),
                S(1, 'eng', 'English [Full]'),
                S(2, 'por', 'Portuguese'), S(3, 'spa', 'Spanish')]
        d = logic.decide(audios, subs)
        self.assertEqual(d['audio']['index'], 1)
        self.assertEqual(d['sub']['index'], 1)
        self.assertTrue(d['sub_enabled'])

    def test_full_sub_listed_second_signs_unnamed_but_forced(self):
        subs = [S(0, 'eng', '', isforced=True), S(1, 'eng', '')]
        self.assertEqual(logic.pick_sub(subs, 'full')['index'], 1)

    def test_dialogue_vs_songs_names(self):
        subs = [S(0, 'eng', 'Songs'), S(1, 'eng', 'Dialogue')]
        self.assertEqual(logic.pick_sub(subs, 'full')['index'], 1)

    def test_sdh_loses_to_regular(self):
        subs = [S(0, 'eng', 'English SDH'), S(1, 'eng', 'English')]
        self.assertEqual(logic.pick_sub(subs, 'full')['index'], 1)

    def test_commentary_audio_skipped(self):
        audios = [A(0, 'jpn', 'Commentary'), A(1, 'jpn', 'Japanese'), A(2, 'eng')]
        self.assertEqual(logic.pick_audio(audios)[0]['index'], 1)

    def test_prefers_surround_japanese(self):
        audios = [A(0, 'jpn', ch=2), A(1, 'jpn', ch=6), A(2, 'eng', ch=6)]
        self.assertEqual(logic.pick_audio(audios)[0]['index'], 1)

    def test_naruto_untagged_beside_english(self):
        audios = [A(0, 'eng', 'English', 'ac3'), A(1, '', '', 'ac3')]
        track, why = logic.pick_audio(audios)
        self.assertEqual(track['index'], 1)
        self.assertEqual(why, 'untagged-beside-english')

    def test_untagged_but_named_japanese(self):
        audios = [A(0, 'und', 'English Dub'), A(1, 'und', 'Japanese 2.0')]
        self.assertEqual(logic.pick_audio(audios)[0]['index'], 1)

    def test_undead_unluck_jpn_por(self):
        audios = [A(0, 'por', 'Portuguese', 'opus'), A(1, 'jpn', '', 'opus')]
        subs = [S(0, 'por'), S(1, 'eng')]
        d = logic.decide(audios, subs)
        self.assertEqual(d['audio']['index'], 1)
        self.assertEqual(d['sub']['index'], 1)

    def test_single_japanese_audio_release(self):
        audios = [A(0, 'jpn')]
        subs = [S(0, 'eng', 'English')]
        d = logic.decide(audios, subs)
        self.assertEqual((d['audio']['index'], d['sub']['index']), (0, 0))

    def test_single_untagged_sub_with_japanese_audio(self):
        d = logic.decide([A(0, 'jpn')], [S(0, '')])
        self.assertEqual(d['sub']['index'], 0)

    def test_dub_only_uses_signs(self):
        audios = [A(0, 'eng', 'English', 'eac3', 6)]
        subs = [S(0, 'eng', 'Full'), S(1, 'eng', 'Signs/Songs')]
        d = logic.decide(audios, subs, no_jpn_mode='signs')
        self.assertIsNone(d['audio'])
        self.assertEqual(d['sub']['index'], 1)

    def test_dub_only_no_signs_leaves_subs(self):
        d = logic.decide([A(0, 'eng')], [S(0, 'eng', 'Full')], no_jpn_mode='signs')
        self.assertIsNone(d['sub'])
        self.assertIsNone(d['sub_enabled'])

    def test_no_english_subs_leaves_subs(self):
        d = logic.decide([A(0, 'jpn')], [S(0, 'spa'), S(1, 'por')])
        self.assertEqual(d['audio']['index'], 0)
        self.assertIsNone(d['sub'])

    def test_two_letter_codes(self):
        d = logic.decide([A(0, 'en'), A(1, 'ja')], [S(0, 'en')])
        self.assertEqual((d['audio']['index'], d['sub']['index']), (1, 0))


class Remembered(unittest.TestCase):
    def test_english_dub_choice_carries_across_reordered_files(self):
        first = [A(0, 'jpn', 'Japanese'), A(1, 'eng', 'English')]
        pref = {'audio': logic.audio_sig(first[1]),
                'sub': logic.sub_sig(S(2, 'eng', 'Signs & Songs'), True)}
        # next episode orders tracks differently
        audios = [A(0, 'eng', 'English'), A(1, 'jpn', 'Japanese')]
        subs = [S(0, 'eng', 'Full'), S(1, 'eng', 'Signs & Songs'), S(2, 'spa')]
        d = logic.decide(audios, subs, pref)
        self.assertEqual(d['audio']['index'], 0)
        self.assertEqual(d['sub']['index'], 1)
        self.assertEqual(d['reason'], 'remembered')

    def test_subs_off_is_remembered(self):
        pref = {'audio': logic.audio_sig(A(1, 'jpn')), 'sub': logic.sub_sig(None, False)}
        d = logic.decide([A(0, 'eng'), A(1, 'jpn')], [S(0, 'eng')], pref)
        self.assertEqual(d['audio']['index'], 1)
        self.assertFalse(d['sub_enabled'])

    def test_japanese_choice_falls_back_when_names_change(self):
        pref = {'audio': logic.audio_sig(A(0, 'jpn', 'Japanese FLAC', 'flac')),
                'sub': logic.sub_sig(S(0, 'eng', 'English Full [Honorifics]'), True)}
        audios = [A(0, 'eng', 'Eng', 'aac'), A(1, '', 'JP', 'aac')]
        subs = [S(0, 'eng', 'Signs'), S(1, 'eng', 'Dialogue')]
        d = logic.decide(audios, subs, pref)
        self.assertEqual(d['audio']['index'], 1)
        self.assertEqual(d['sub']['index'], 1)

    def test_other_language_sub_choice(self):
        pref = {'audio': logic.audio_sig(A(1, 'jpn')), 'sub': logic.sub_sig(S(3, 'spa', 'Spanish'), True)}
        d = logic.decide([A(0, 'eng'), A(1, 'jpn')],
                         [S(0, 'eng'), S(1, 'spa', 'Spanish')], pref)
        self.assertEqual(d['sub']['index'], 1)


class Paths(unittest.TestCase):
    ROOTS = ['Anime']

    def test_scope_and_keys(self):
        p = 'nfs://192.0.2.65/media/share/Anime/[Judas] Bleach 168-195/Bleach - 170.mkv'
        folder = logic.folder_of(p)
        root = logic.anime_root(folder, self.ROOTS)
        self.assertEqual(root, 'nfs://192.0.2.65/media/share/Anime/')
        self.assertEqual(logic.pref_key(folder, root, 0), 'nfs://192.0.2.65/media/share/Anime/[Judas] Bleach 168-195/')
        self.assertEqual(logic.pref_key(folder, root, 1), 'nfs://192.0.2.65/media/share/Anime/[Judas] Bleach 168-195/')

    def test_show_scope_spans_season_subfolders(self):
        root = 'nfs://192.0.2.65/media/share/Anime/'
        f1 = root + 'One Punch Man/OPM/'
        f2 = root + 'One Punch Man/OPM S2/'
        self.assertEqual(logic.pref_key(f1, root, 1), logic.pref_key(f2, root, 1))
        self.assertNotEqual(logic.pref_key(f1, root, 0), logic.pref_key(f2, root, 0))

    def test_second_export_path_and_case(self):
        folder = logic.folder_of('nfs://192.0.2.65/srv/nfs/media/anime/Ao Ashi/ep01.mkv')
        self.assertEqual(logic.anime_root(folder, self.ROOTS), 'nfs://192.0.2.65/srv/nfs/media/anime/')

    def test_out_of_scope(self):
        folder = logic.folder_of('nfs://192.0.2.65/media/share/TV/Your Honor/ep1.mkv')
        self.assertIsNone(logic.anime_root(folder, self.ROOTS))

    def test_segment_must_match_whole_name(self):
        folder = logic.folder_of('nfs://x/media/share/TV/Animeniacs/ep1.mkv')
        self.assertIsNone(logic.anime_root(folder, self.ROOTS))

    def test_path_fragment_root(self):
        folder = logic.folder_of('nfs://x/media/share/Anime/Beck/ep1.mkv')
        self.assertEqual(logic.anime_root(folder, ['media/share/Anime']), 'nfs://x/media/share/Anime/')

    def test_loose_files_in_root_keyed_by_series(self):
        root = 'nfs://x/media/share/Anime/'
        a = root + 'Medalist.S02E09.1080p.DSNP.WEB-DL.JPN.AAC2.0.H.264.MSubs-ToonsHub.mkv'
        b = root + 'Medalist.S02E06.Intensive.Training.1080p.DSNP.WEB-DL.AAC2.0.H.264.mkv'
        c = root + '[SubsPlease] Dandadan - 05 (1080p) [ABCD1234].mkv'
        ka = logic.pref_key(logic.folder_of(a), root, 0, a)
        kb = logic.pref_key(logic.folder_of(b), root, 0, b)
        kc = logic.pref_key(logic.folder_of(c), root, 0, c)
        self.assertEqual(ka, root + '#medalist')
        self.assertEqual(ka, kb)
        self.assertEqual(kc, root + '#dandadan')

    def test_series_name_variants(self):
        self.assertEqual(logic.series_name('[Judas] Bleach - 194.mkv'), 'bleach')
        self.assertEqual(logic.series_name('One.Punch.Man.S02E03.1080p.mkv'), 'one punch man')
        self.assertEqual(logic.series_name('Frieren E12 [1080p].mkv'), 'frieren')

    def test_stack_path(self):
        p = 'stack://nfs://x/Anime/Movie/part1.mkv , nfs://x/Anime/Movie/part2.mkv'
        self.assertEqual(logic.folder_of(p), 'nfs://x/Anime/Movie/')


if __name__ == '__main__':
    unittest.main(verbosity=1)
