# vibe-codes

Homebrew odds and ends for an LG webOS TV, an NVIDIA Shield, and Kodi. Everything here was
written for my own hardware; it's shared in case the approach is useful to someone else.

## What's here

### `lg-webos/` — LG 75NANO90UPA (webOS 6.5.3)
- **`input-selector/`** — a transparent overlay app that replaces the TV's input picker with a
  custom HDMI/AVR selector (Python, driven through luna-send).
- **`input-app/`** — a small HTML webOS app version of the selector.
- **`scripts/`** — `10-debloat.sh` (disable unwanted system apps) and `70-boot-hdmi3`
  (boot straight to an HDMI input).
- **`boot-logo-tools/`** — `lz4p.py` (the LZ4-variant codec webOS uses for the boot-logo
  partition) and `make_logo.py` (generate a replacement logo image).
- **`docs/`** — setup, reverse-engineering notes, and recovery notes.

### `kodi/anime-tracks/` — Kodi service add-on
For files under an `Anime` folder, selects Japanese audio and full English subtitles, and
remembers per-folder track changes. Robust to mistagged tracks. See its own README.

### `shield-dolby-vision/`
EDID fix to get Dolby Vision out of an NVIDIA Shield through an AV receiver that mangles the
Dolby Vision EDID block.

## Not included, on purpose

No device firmware, partition images, stock boot logos, vendor binaries, or reverse-engineered
third-party code — only things written here. IP addresses and the TV's MAC in the docs are
placeholders (`192.0.2.x`, RFC 5737). The boot-logo and recovery material touches a firmware
partition (`mmcblk0p25`); read the recovery notes before trying any of it.

## Disclaimer

Modifying a TV's firmware can brick it. Everything here is provided as-is, with no warranty, for
educational purposes. You are responsible for your own hardware.

## License

MIT — see [LICENSE](LICENSE).
