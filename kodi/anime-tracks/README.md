# Anime Tracks (Kodi service add-on)

Installed on the Shield's Kodi 21.2 as `service.animetracks`.

For anything under a folder named `Anime` it picks **Japanese audio** and the **full English
subtitle track** at play time. New files are covered with no rescan, because nothing depends
on the library. If you change tracks while watching, that choice becomes the default for the
rest of that folder.

## How it picks

**Audio.** It ranks tracks by language tag (`jpn`, `ja`, …), then by track name ("Japanese",
"JP"). It skips commentary and prefers surround when there's a tie. When only the English dub
is tagged, the one untagged track is treated as Japanese.

**Subtitles.** It only considers English tracks, by tag or name, and picks
Full/Dialogue over plain over SDH over Signs & Songs/forced. If a file has no Japanese audio
(a dub-only file), the default turns on Signs & Songs only, and leaves subtitles alone if
there aren't any.

**Remembered choices.** When you change audio or subtitles (including turning subs off) and
the new choice holds for 2 seconds, it saves a *fingerprint* of what you picked: language,
subtitle kind and name. It doesn't save the track number. The next file in the folder gets
the closest match, so it still works when episodes order their tracks differently.

The choice is stored per folder. Files sitting loose in `Anime/` are keyed by the series name
in the filename (`Medalist.S02E05…` → `medalist`), so unrelated loose shows don't share one.

## Settings (Add-ons → My add-ons → Services → Anime Tracks → Configure)

| Setting | Default |
|---|---|
| Anime folder names | `Anime` (comma-separated; add a path fragment like `media/share/Anime` to be stricter) |
| Remember my track changes for | The file's folder (or: the whole show, spanning season subfolders) |
| If a file has no Japanese audio | Signs & Songs subtitles only |
| Show a notification | On |
| Forget all remembered folder choices | button |

To forget just one folder, play a file from it and run `RunScript(service.animetracks,forget)`.

Saved choices live in `.kodi/userdata/addon_data/service.animetracks/prefs.json`.

## Reinstall / install elsewhere

Either install from zip in Kodi (`service.animetracks-1.0.0.zip`; you'll need "Unknown sources"
turned on), or push it over adb:

```bash
KODI=/storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi
adb push service.animetracks "$KODI/addons/"
adb forward tcp:9090 tcp:9090
python3 tests/kodi_rpc.py Addons.SetAddonEnabled '{"addonid":"service.animetracks","enabled":true}'
```

## Tests

- `python3 tests/test_logic.py`: unit tests for the selection logic (28).
- `tests/live_test.py`: end-to-end test against the Shield (needs `adb forward tcp:9090 tcp:9090`). It plays
  real files, so point it at episodes you've already watched that have no resume point. It
  deletes `prefs.json` when it starts; clear that file again when you're done.
